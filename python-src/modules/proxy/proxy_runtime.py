from __future__ import annotations

import contextlib
import io
import os
import socket
import ssl
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from werkzeug.serving import ThreadedWSGIServer, WSGIRequestHandler

from modules.runtime.error_codes import ErrorCode
from modules.runtime.operation_result import OperationResult
from modules.runtime.resource_manager import ResourceManager
from modules.runtime.thread_manager import ThreadManager

type LogFunc = Callable[[str], None]


class StoppableWSGIServer(ThreadedWSGIServer):
    """Останавливаемый WSGI-сервер"""

    def __init__(
        self,
        *args: Any,
        dual_stack: bool = False,
        **kwargs: Any,
    ) -> None:
        self._stop_event = threading.Event()
        self._dual_stack_requested = dual_stack
        self._dual_stack_enabled = False
        super().__init__(*args, **kwargs)

    def server_bind(self) -> None:
        if self._dual_stack_requested and self.address_family == socket.AF_INET6:
            if not (
                hasattr(socket, "IPPROTO_IPV6")
                and hasattr(socket, "IPV6_V6ONLY")
            ):
                raise RuntimeError("Текущая среда не поддерживает настройку dual-stack IPv6 socket")
            try:
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except OSError as exc:
                raise RuntimeError(f"Не удалось настроить dual-stack socket: {exc}") from exc
            self._dual_stack_enabled = True
        super().server_bind()

    def server_close(self) -> None:
        stop_event = getattr(self, "_stop_event", None)
        if stop_event:
            stop_event.set()
        super().server_close()

    def serve_forever(self, poll_interval: float = 0.5) -> None:
        self.timeout = poll_interval
        while not self._stop_event.is_set():
            try:
                self.handle_request()
            except OSError:
                break


@dataclass
class RuntimeState:
    server: StoppableWSGIServer | None = None
    server_thread: threading.Thread | None = None
    server_task_id: str | None = None
    running: bool = False
    listen_mode: str | None = None


@dataclass(frozen=True)
class ListenerSetupResult:
    server: StoppableWSGIServer
    host: str
    mode: str
    fallback_reason: str | None = None


class ProxyRuntime:
    """Рантайм прокси: отвечает за сертификаты/прослушивание/жизненный цикл потоков."""

    def __init__(
        self,
        app: Any,
        log_func: LogFunc,
        *,
        resource_manager: ResourceManager,
        thread_manager: ThreadManager,
    ) -> None:
        self._app = app
        self._log = log_func
        self._resource_manager = resource_manager
        self._thread_manager = thread_manager
        self._state = RuntimeState()

    def is_running(self) -> bool:
        return self._state.running

    def _log_task_diagnostics(self, prefix: str) -> None:
        task_id = self._state.server_task_id
        if task_id:
            status = self._thread_manager.get_status(task_id=task_id)
            if status:
                self._log(f"{prefix} task_status={status}")
            else:
                self._log(f"{prefix} task_status=<missing task_id={task_id}>")
        active_tasks = self._thread_manager.get_active_tasks()
        if active_tasks:
            self._log(f"{prefix} active_tasks={active_tasks}")

    @staticmethod
    def _format_listener_endpoint(host: str, port: int) -> str:
        if ":" in host:
            return f"[{host}]:{port}"
        return f"{host}:{port}"

    def _create_server_instance(
        self,
        *,
        host: str,
        port: int,
        ssl_context: ssl.SSLContext,
        dual_stack: bool = False,
    ) -> StoppableWSGIServer:
        stderr_buffer = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr_buffer):
                server = StoppableWSGIServer(
                    host,
                    port,
                    self._app,
                    ssl_context=ssl_context,
                    dual_stack=dual_stack,
                )
        except SystemExit as exc:
            detail = stderr_buffer.getvalue().strip()
            reason = detail or f"SystemExit({exc.code})"
            endpoint = self._format_listener_endpoint(host, port)
            raise RuntimeError(f"Не удалось начать прослушивание {endpoint}: {reason}") from exc

        server.RequestHandlerClass = WSGIRequestHandler
        return server

    def _create_server_with_fallback(
        self,
        *,
        host: str,
        port: int,
        ssl_context: ssl.SSLContext,
    ) -> ListenerSetupResult:
        if host == "0.0.0.0" and socket.has_ipv6:
            try:
                server = self._create_server_instance(
                    host="::",
                    port=port,
                    ssl_context=ssl_context,
                    dual_stack=True,
                )
            except Exception as exc:
                fallback_reason = str(exc)
                self._log(f"dual-stack прослушивание недоступно, откатываемся на IPv4: "
                    f"{fallback_reason}")
            else:
                return ListenerSetupResult(
                    server=server,
                    host="::",
                    mode="dual_stack",
                )
        else:
            fallback_reason = None

        listen_mode = "ipv6_only" if ":" in host else "ipv4_only"
        server = self._create_server_instance(
            host=host,
            port=port,
            ssl_context=ssl_context,
        )
        return ListenerSetupResult(
            server=server,
            host=host,
            mode=listen_mode,
            fallback_reason=fallback_reason,
        )

    def start(  # noqa: PLR0911, PLR0912, PLR0913, PLR0915
        self,
        *,
        host: str,
        port: int,
        target_api_base_url: str,
        custom_model_id: str,
        target_model_id: str,
        stream_mode: str | None,
    ) -> OperationResult:
        if self._state.running:
            self._log("Прокси-сервер уже запущен")
            return OperationResult.success()

        if not self._app:
            self._log("Приложение Flask не инициализировано")
            return OperationResult.failure("Приложение Flask не инициализировано")

        cert_file = self._resource_manager.get_cert_file()
        key_file = self._resource_manager.get_key_file()

        if not cert_file or not key_file:
            self._log("Пустой путь к сертификату")
            return OperationResult.failure(
                "Пустой путь к сертификату", code=ErrorCode.CONFIG_INVALID
            )

        if not (os.path.exists(cert_file) and os.path.exists(key_file)):
            self._log(f"Файл сертификата не найден: {cert_file} или {key_file}")
            return OperationResult.failure(
                "Файл сертификата не найден", code=ErrorCode.FILE_NOT_FOUND
            )

        try:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(cert_file, key_file)

            endpoint = self._format_listener_endpoint(host, port)
            self._log(f"Запускаем прокси-сервер, целевой адрес прослушивания https://{endpoint}")
            self._log(f"Адрес целевого API: {target_api_base_url}")
            self._log(f"Пользовательский ID модели: {custom_model_id}")
            self._log(f"Фактический ID модели: {target_model_id}")
            if stream_mode:
                self._log(f"Принудительный потоковый режим: {stream_mode}")

            if self._state.server_task_id:
                previous_finished = self._thread_manager.wait(
                    self._state.server_task_id,
                    timeout=5,
                )
                if not previous_finished:
                    self._log("Старый поток сервера ещё завершается, пока нельзя запустить новый "
                        "экземпляр")
                    self._log_task_diagnostics("Диагностика тайм-аута ожидания старого потока "
                        "перед запуском:")
                    return OperationResult.failure(
                        "Старый поток сервера ещё завершается",
                        code=ErrorCode.UNKNOWN,
                    )

            try:
                listener_setup = self._create_server_with_fallback(
                    host=host,
                    port=port,
                    ssl_context=ssl_context,
                )
                self._state.server = listener_setup.server
                self._state.listen_mode = listener_setup.mode
                if listener_setup.mode == "dual_stack":
                    self._log(f"Режим прослушивания: dual_stack (https://[::]:{port}, принимает "
                        f"IPv4 и IPv6)")
                else:
                    fallback_endpoint = self._format_listener_endpoint(
                        listener_setup.host,
                        port,
                    )
                    self._log(f"Режим прослушивания: {listener_setup.mode} (https://{fallback_endpoint})")
                self._log("Экземпляр сервера успешно создан")
            except Exception as exc:
                self._state.listen_mode = None
                self._log(f"Не удалось создать экземпляр сервера: {exc}")
                return OperationResult.failure(
                    "Не удалось создать экземпляр сервера", code=ErrorCode.UNKNOWN
                )

            server_ready_event = threading.Event()

            def run_server():
                self._state.server_thread = threading.current_thread()
                try:
                    if not self._state.server:
                        server_ready_event.set()
                        self._log("Экземпляр сервера пуст, запуск невозможен")
                        return
                    server_ready_event.set()
                    self._state.server.serve_forever()
                except Exception as exc:
                    self._log(f"Ошибка во время работы сервера: {exc}")
                finally:
                    self._state.running = False
                    self._state.server_task_id = None
                    self._state.server_thread = None
                    self._log("Поток сервера завершился")

            self._state.server_task_id = self._thread_manager.run(
                "proxy_server",
                run_server,
                allow_parallel=False,
            )
            self._state.running = True

            if not server_ready_event.wait(timeout=5):
                self._log("Истекло время запуска прокси-сервера")
                self._log_task_diagnostics("Диагностика тайм-аута запуска:")
                return OperationResult.failure(
                    "Истекло время запуска прокси-сервера", code=ErrorCode.UNKNOWN
                )

            if self._state.running:
                self._log("Прокси-сервер успешно запущен")
                return OperationResult.success()

            self._log("Не удалось запустить прокси-сервер")
            return OperationResult.failure(
                "Не удалось запустить прокси-сервер", code=ErrorCode.UNKNOWN
            )

        except PermissionError:
            self._log(f"Недостаточно прав, невозможно прослушивать порт {port}. Запустите от имени "
                f"администратора.")
            return OperationResult.failure("Недостаточно прав", code=ErrorCode.PERMISSION_DENIED)
        except OSError as exc:
            if "address already in use" in str(exc).lower():
                self._log(f"Порт {port} уже занят. Проверьте, не занимает ли его другой сервис.")
                return OperationResult.failure("Порт уже занят", code=ErrorCode.PORT_IN_USE)
            self._log(f"Ошибка ОС при запуске сервера: {exc}")
            return OperationResult.failure("Ошибка ОС при запуске сервера", code=ErrorCode.UNKNOWN)
        except Exception as exc:
            self._log(f"Произошла непредвиденная ошибка при запуске прокси-сервера: {exc}")
            return OperationResult.failure("Произошла непредвиденная ошибка при запуске "
                "прокси-сервера", code=ErrorCode.UNKNOWN)

    def stop(self) -> OperationResult:
        has_pending_task = bool(self._state.server_task_id)
        if not self._state.running and not has_pending_task:
            self._log("Прокси-сервер не запущен")
            return OperationResult.success()

        self._log("Останавливаем прокси-сервер...")
        self._state.running = False

        stop_requested = False
        if self._state.server:
            try:
                self._state.server.server_close()
                stop_requested = True
                self._log("Команда остановки сервера отправлена")
            except Exception as exc:
                self._log(f"Ошибка при остановке сервера: {exc}")
        else:
            self._log("Не обнаружен экземпляр сервера, который можно остановить")

        clean_stop = True
        wait_finished = True
        if self._state.server_task_id:
            try:
                finished = self._thread_manager.wait(self._state.server_task_id, timeout=5)
                wait_finished = finished
                if finished:
                    self._log("Поток сервера безопасно остановлен")
                    self._state.server_task_id = None
                else:
                    clean_stop = False
                    self._log("Поток сервера не остановился за 5 секунд")
                    self._log_task_diagnostics("Диагностика тайм-аута остановки:")
            except Exception as exc:
                wait_finished = False
                clean_stop = False
                self._log(f"Ошибка при ожидании завершения потока: {exc}")
                self._log_task_diagnostics("Диагностика исключения при остановке:")

        if wait_finished:
            self._state.server = None
            self._state.server_thread = None
            self._state.listen_mode = None

        if clean_stop:
            self._log("Прокси-сервер полностью остановлен")
            return OperationResult.success()

        if not stop_requested:
            self._log("Команда остановки не отправлена, поток прокси, возможно, всё ещё работает")
        self._log("Прокси-сервер ещё завершает очистку в фоне, следите за логами")
        return OperationResult.failure(
            "Прокси-сервер остановлен не полностью", code=ErrorCode.UNKNOWN
        )


__all__ = ["ProxyRuntime"]
