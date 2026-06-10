"""
Вспомогательный модуль персистентных прав администратора macOS.

При первой необходимости повышения прав модуль через osascript запускает работающий от root
Python helper, далее общается с ним через Unix Socket и освобождает его при закрытии GUI.
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

try:
    from modules.runtime.resource_manager import get_packaging_runtime
except ImportError:
    # При запуске как скрипт нет контекста пакета — дополняем пути поиска модулей
    import sys

    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from modules.runtime.resource_manager import get_packaging_runtime

JsonDict = dict[str, Any]
JsonMapping = Mapping[str, Any]
type LogFunc = Callable[[str], None]

REQUEST_TERMINATOR = b"\n"
CONNECT_TIMEOUT = 12.0
RETRY_DELAY = 0.15
HELPER_FLAG = "--run-macos-helper"
_SOCKET_FAMILY_UNIX = getattr(socket, "AF_UNIX", None)


def _as_json_dict(value: Any) -> JsonDict:
    if not isinstance(value, dict):
        return {}
    source = cast(dict[object, Any], value)
    return {str(key): item for key, item in source.items()}


class MacPrivilegeSessionError(RuntimeError):
    """Ошибка при коммуникации персистентного повышения прав."""


class MacPrivilegeSession:
    """Клиент для общения с root helper: запись файлов, копирование, запуск команд."""

    def __init__(self) -> None:
        self.owner_uid = getattr(os, "getuid", lambda: 0)()
        self.owner_gid = getattr(os, "getgid", lambda: 0)()
        base_dir = Path("/tmp/mtga_privileged") / str(self.owner_uid)
        base_dir.mkdir(parents=True, exist_ok=True)
        base_dir.chmod(0o700)
        unique = f"{os.getpid()}_{uuid.uuid4().hex}"
        self.base_dir = base_dir
        self.socket_path = str(base_dir / f"hosts_helper_{unique}.sock")
        self.helper_log_path = str(base_dir / f"hosts_helper_{uuid.uuid4().hex}.log")
        self._connection: socket.socket | None = None
        self._recv_buffer = b""
        self._helper_started = False
        self._lock = threading.Lock()
        self._atexit_registered = False
        self._connect_logged_wait = False
        self._security_session = os.environ.get("SECURITYSESSIONID")

    def ensure_ready(self, log_func: LogFunc = print) -> bool:
        """Гарантирует, что helper запущен и socket-соединение установлено."""
        if sys.platform != "darwin":
            log_func("⚠️ Персистентное повышение прав macOS работает только на платформе macOS")
            return False

        if self._connection:
            return True

        if self._helper_started and not os.path.exists(self.socket_path):
            # helper аварийно завершился, требуется перезапуск
            self._helper_started = False

        if not self._helper_started:
            if not self._start_helper(log_func):
                return False
            self._helper_started = True

        return self._connect(log_func)

    def write_file(
        self, path: str, content: str, encoding: str, log_func: LogFunc = print
    ) -> bool:
        """Записывает текстовый файл с правами администратора."""
        payload = {
            "action": "write_file",
            "path": path,
            "content": content,
            "encoding": encoding,
        }
        response = self._send_payload(payload, log_func)
        if not response:
            return False
        if response.get("ok"):
            return True
        log_func(f"⚠️ Не удалось записать {path}: {response.get('error')}")
        return False

    def copy_file(self, src: str, dst: str, log_func: LogFunc = print) -> bool:
        """Копирует файл, например для резервного копирования/восстановления hosts."""
        payload = {"action": "copy_file", "src": src, "dst": dst}
        response = self._send_payload(payload, log_func)
        if not response:
            return False
        if response.get("ok"):
            return True
        log_func(f"⚠️ Не удалось скопировать {src} -> {dst}: {response.get('error')}")
        return False

    def run_command(self, cmd: list[str], log_func: LogFunc = print) -> tuple[bool, JsonDict]:
        """Выполняет команду (например, open -t /etc/hosts), возвращает (success, data)."""
        payload = {"action": "run_command", "cmd": cmd}
        response = self._send_payload(payload, log_func)
        if not response:
            return False, {"error": "Сбой связи"}
        if response.get("ok"):
            data = _as_json_dict(response.get("data", {}))
            return True, data
        data = _as_json_dict(response.get("data"))
        data.setdefault("error", response.get("error", "Неизвестная ошибка"))
        return False, data

    def install_trusted_cert(
        self,
        cert_path: str,
        *,
        keychain: str = "/Library/Keychains/System.keychain",
        log_func: LogFunc = print,
    ) -> tuple[bool, JsonDict]:
        """Устанавливает и делает доверенным CA-сертификат с правами администратора, возвращает
        (success, data)."""
        if not cert_path:
            return False, {"error": "Путь к сертификату пуст"}

        base_cmd: list[str] = [
            "security",
            "add-trusted-cert",
            "-d",
            "-r",
            "trustRoot",
            "-k",
            keychain,
            cert_path,
        ]
        cmd = base_cmd
        if sys.platform == "darwin" and self.owner_uid:
            cmd = ["launchctl", "asuser", str(self.owner_uid)]
            if self._security_session:
                cmd.extend(["env", f"SECURITYSESSIONID={self._security_session}"])
            cmd.extend(base_cmd)
        success, data = self.run_command(cmd, log_func=log_func)
        if success or cmd == base_cmd:
            return success, data

        # Откат на прямую команду security, чтобы не падать при недоступном launchctl
        return self.run_command(base_cmd, log_func=log_func)

    def shutdown(self) -> None:
        """Закрывает helper при выходе из GUI."""
        if not self._helper_started:
            return
        payload = {"action": "shutdown"}
        def _quiet_log(_message: str) -> None:
            return None
        try:
            self._send_payload(payload, log_func=_quiet_log, allow_retry=False)
        except MacPrivilegeSessionError:
            pass
        finally:
            self._cleanup_connection()
            self._helper_started = False

    def _start_helper(self, log_func: LogFunc) -> bool:
        runtime = get_packaging_runtime()
        if runtime == "nuitka":
            launcher = self._locate_packaged_launcher()
            if not launcher:
                log_func("⚠️ Не найден упакованный исполняемый файл, невозможно запросить права "
                    "администратора")
                return False
            cmd_parts = [
                shlex.quote(str(launcher)),
                HELPER_FLAG,
                "--socket",
                shlex.quote(self.socket_path),
                "--owner-uid",
                str(self.owner_uid),
                "--owner-gid",
                str(self.owner_gid),
            ]
        else:
            python_exec = self._locate_python_executable()
            if not python_exec:
                log_func(f"⚠️ Не удалось найти интерпретатор Python: {sys.executable}")
                return False
            helper_path = Path(__file__).resolve()
            cmd_parts = [
                shlex.quote(str(python_exec)),
                shlex.quote(str(helper_path)),
                HELPER_FLAG,
                "--socket",
                shlex.quote(self.socket_path),
                "--owner-uid",
                str(self.owner_uid),
                "--owner-gid",
                str(self.owner_gid),
            ]

        log_func("🔐 Запрашиваем права администратора, введите пароль в диалоговом окне...")
        helper_cmd = " ".join(cmd_parts)
        if self._security_session:
            helper_cmd = f"SECURITYSESSIONID={shlex.quote(self._security_session)} " + helper_cmd
        helper_cmd += f" >> {shlex.quote(self.helper_log_path)} 2>&1 &"
        script = f'do shell script "{helper_cmd}" with administrator privileges'
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "Неизвестная ошибка"
            log_func(f"⚠️ Не удалось получить права администратора: {message}")
            return False
        log_func("✅ Права администратора получены, устанавливаем канал связи...")
        return True

    def _locate_packaged_launcher(self) -> Path | None:
        argv0 = Path(sys.argv[0]).resolve()
        if argv0.is_file():
            return argv0

        exec_path = Path(sys.executable)
        exec_dir = exec_path.parent if exec_path.exists() else Path.cwd()
        candidates = sorted(exec_dir.glob("MTGA_GUI-*"))
        for candidate in candidates:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate
        return None

    def _locate_python_executable(self) -> Path | None:
        candidates: list[Path] = []
        exec_path = Path(sys.executable)
        if exec_path.is_file():
            if exec_path.name.startswith("python"):
                candidates.append(exec_path)
            else:
                exe_dir = exec_path.parent
                contents_dir = exe_dir.parent
                resources_bin = contents_dir / "Resources" / "bin"
                for bin_name in ("python3", "python3.13", "python"):
                    candidate = resources_bin / bin_name
                    if candidate.is_file():
                        candidates.append(candidate)
                        break
        python_home = os.environ.get("PYTHONHOME")
        if python_home:
            bin_dir = Path(python_home) / "bin"
            for bin_name in ("python3", "python"):
                candidate = bin_dir / bin_name
                if candidate.is_file():
                    candidates.append(candidate)
                    break
        for bin_name in ("python3", "python"):
            found = shutil.which(bin_name)
            if found:
                candidates.append(Path(found))
        for candidate in candidates:
            if candidate and candidate.is_file():
                return candidate
        return None

    def _connect(self, log_func: LogFunc) -> bool:
        if not self._connect_logged_wait:
            log_func("⌛ Инициализируем канал связи администратора, подождите...")
            self._connect_logged_wait = True
        deadline = time.time() + CONNECT_TIMEOUT
        while time.time() < deadline:
            try:
                if _SOCKET_FAMILY_UNIX is None:
                    log_func("Текущая система не поддерживает Unix Socket, соединение невозможно")
                    break
                conn = socket.socket(_SOCKET_FAMILY_UNIX, socket.SOCK_STREAM)
                conn.connect(self.socket_path)
                self._connection = conn
                self._recv_buffer = b""
                self._register_atexit()
                self._connect_logged_wait = False
                log_func("🔗 Канал связи администратора готов")
                return True
            except FileNotFoundError:
                time.sleep(RETRY_DELAY)
            except ConnectionRefusedError:
                time.sleep(RETRY_DELAY)
            except OSError:
                time.sleep(RETRY_DELAY)

        self._connect_logged_wait = False
        log_func(f"⚠️ Не удалось инициализировать канал прав администратора, повторите попытку "
            f"(лог: {self.helper_log_path}）")
        self._cleanup_connection()
        return False

    def _send_payload(
        self,
        payload: JsonMapping,
        log_func: LogFunc,
        *,
        allow_retry: bool = True,
    ) -> JsonDict | None:
        with self._lock:
            attempts = 2 if allow_retry else 1
            payload_json = dict(payload)
            data = json.dumps(payload_json, ensure_ascii=False).encode("utf-8") + REQUEST_TERMINATOR
            for _ in range(attempts):
                if not self.ensure_ready(log_func):
                    return None
                try:
                    assert self._connection is not None
                    self._connection.sendall(data)
                    line = self._readline()
                    return _as_json_dict(json.loads(line.decode("utf-8")))
                except (OSError, ConnectionError, json.JSONDecodeError):
                    self._cleanup_connection()
                    time.sleep(RETRY_DELAY)

        raise MacPrivilegeSessionError("Не удаётся связаться с helper прав администратора")

    def _readline(self) -> bytes:
        if not self._connection:
            raise ConnectionError("Соединение ещё не установлено")

        while True:
            if REQUEST_TERMINATOR in self._recv_buffer:
                line, self._recv_buffer = self._recv_buffer.split(REQUEST_TERMINATOR, 1)
                return line
            chunk = self._connection.recv(4096)
            if not chunk:
                raise ConnectionError("helper закрыл соединение")
            self._recv_buffer += chunk

    def _cleanup_connection(self) -> None:
        if self._connection:
            with suppress(OSError):
                self._connection.close()
        self._connection = None
        self._recv_buffer = b""
        self._connect_logged_wait = False

    def _register_atexit(self) -> None:
        if self._atexit_registered:
            return
        self._atexit_registered = True
        atexit.register(self.shutdown)


_mac_session_holder: dict[str, MacPrivilegeSession | None] = {"session": None}
_mac_session_lock = threading.Lock()


def get_mac_privileged_session(log_func: LogFunc = print) -> MacPrivilegeSession | None:
    """Возвращает доступную MacPrivilegeSession или None при отсутствии прав."""
    if sys.platform != "darwin":
        return None

    with _mac_session_lock:
        session = _mac_session_holder["session"]
        if session is None:
            session = MacPrivilegeSession()
            _mac_session_holder["session"] = session

    if session.ensure_ready(log_func):
        return session
    return None


class _PrivilegeHelperServer:
    """Работающий под root helper, выполняющий привилегированные операции."""

    def __init__(self, socket_path: str, owner_uid: int, owner_gid: int) -> None:
        self.socket_path = socket_path
        self.owner_uid = owner_uid
        self.owner_gid = owner_gid
        self._stop = False

    def run(self) -> None:
        with suppress(FileNotFoundError):
            os.remove(self.socket_path)

        if _SOCKET_FAMILY_UNIX is None:
            return

        server_socket = socket.socket(_SOCKET_FAMILY_UNIX, socket.SOCK_STREAM)
        server_socket.bind(self.socket_path)
        chown_fn = getattr(os, "chown", None)
        if callable(chown_fn):
            chown_fn(self.socket_path, self.owner_uid, self.owner_gid)
        os.chmod(self.socket_path, 0o600)
        server_socket.listen(1)

        try:
            while not self._stop:
                conn, _ = server_socket.accept()
                try:
                    self._handle_connection(conn)
                finally:
                    with suppress(OSError):
                        conn.close()
        finally:
            with suppress(FileNotFoundError):
                os.remove(self.socket_path)
            with suppress(OSError):
                server_socket.close()

    def _handle_connection(self, conn: socket.socket) -> None:
        buffer = b""
        while not self._stop:
            data = conn.recv(4096)
            if not data:
                break
            buffer += data
            while REQUEST_TERMINATOR in buffer:
                line, buffer = buffer.split(REQUEST_TERMINATOR, 1)
                if not line:
                    continue
                response = self._process_request(line)
                conn.sendall(response + REQUEST_TERMINATOR)
                if self._stop:
                    return

    def _process_request(self, line: bytes) -> bytes:  # noqa: PLR0912
        try:
            payload_obj = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError:
            return json.dumps({"ok": False, "error": "Некорректный JSON-запрос"}).encode("utf-8")
        if not isinstance(payload_obj, dict):
            return json.dumps({"ok": False, "error": "Запрос должен быть JSON-объектом"}).encode(
                "utf-8")
        payload = _as_json_dict(payload_obj)

        action_obj = payload.get("action")
        action = action_obj if isinstance(action_obj, str) else ""
        try:
            if action == "write_file":
                path_obj = payload.get("path")
                if not isinstance(path_obj, str):
                    raise ValueError("path должен быть строкой")
                encoding_obj = payload.get("encoding", "utf-8")
                encoding = encoding_obj if isinstance(encoding_obj, str) else "utf-8"
                content_obj = payload.get("content")
                if not isinstance(content_obj, str):
                    raise ValueError("content должен быть строкой")
                with open(path_obj, "w", encoding=encoding) as fh:
                    fh.write(content_obj)
                result = {"ok": True}
            elif action == "copy_file":
                src_obj = payload.get("src")
                dst_obj = payload.get("dst")
                if not isinstance(src_obj, str) or not isinstance(dst_obj, str):
                    raise ValueError("src/dst должны быть строками")
                shutil.copy2(src_obj, dst_obj)
                result = {"ok": True}
            elif action == "run_command":
                cmd_obj = payload.get("cmd")
                if not isinstance(cmd_obj, list):
                    raise ValueError("cmd должен быть списком строк")
                cmd_list = cast(list[object], cmd_obj)
                if not all(isinstance(item, str) for item in cmd_list):
                    raise ValueError("cmd должен быть списком строк")
                cmd = cast(list[str], cmd_list)
                completed = subprocess.run(
                    cmd, capture_output=True, text=True, check=False
                )
                result = {
                    "ok": completed.returncode == 0,
                    "data": {
                        "returncode": completed.returncode,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    },
                }
            elif action == "shutdown":
                self._stop = True
                result = {"ok": True}
            else:
                result = {"ok": False, "error": f"Неизвестный action: {action}"}
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}

        return json.dumps(result, ensure_ascii=False).encode("utf-8")


def _parse_server_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="macOS privileged helper")
    parser.add_argument(
        HELPER_FLAG,
        "--run-server",
        action="store_true",
        dest="run_helper",
        help="Запустить helper",
    )
    parser.add_argument("--socket", dest="socket_path", required=True, help="Путь к socket")
    parser.add_argument("--owner-uid", type=int, required=True, help="UID исходного пользователя")
    parser.add_argument("--owner-gid", type=int, required=True, help="GID исходного пользователя")
    return parser.parse_args()


def main() -> None:
    """При запуске как скрипт запускает root helper."""
    args = _parse_server_args()
    if not getattr(args, "run_helper", False):
        return

    server = _PrivilegeHelperServer(
        socket_path=args.socket_path, owner_uid=args.owner_uid, owner_gid=args.owner_gid
    )
    server.run()


if __name__ == "__main__":
    main()
