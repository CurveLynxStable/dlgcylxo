"""
Модуль управления файлом hosts
Резервное копирование, изменение и восстановление файла hosts
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable

from modules.hosts.file_operability import (
    FileOperabilityReport,
    check_file_operability,
    ensure_windows_file_writable,
)
from modules.hosts.hosts_state import get_hosts_modify_block_state, guard_hosts_modify
from modules.hosts.hosts_text import (
    DEFAULT_HOSTS_IPS,
    append_hosts_block,
    build_hosts_block,
    normalize_ip_list,
    remove_hosts_block_from_content,
)
from modules.platform.macos_privileged_helper import get_mac_privileged_session
from modules.platform.privileges import is_windows_admin
from modules.runtime.resource_manager import ResourceManager

_HOSTS_PATH_FALLBACK_STATE = {"warned": False}
type LogFunc = Callable[[str], None]


def _append_hosts_block_fallback(
    hosts_file: str, hosts_block: str, encoding: str, *, log_func: LogFunc = print
) -> bool:
    """Резервный режим дозаписи (без дедупликации/удаления/атомарной записи)."""
    if not hosts_block:
        return False
    try:
        try:
            with open(hosts_file, encoding=encoding, errors="replace") as f:
                content = f.read()
        except OSError:
            content = ""

        if (
            hosts_block in content
            or f"\n{hosts_block}" in content
            or f"\n\n{hosts_block}" in content
        ):
            log_func("Файл hosts уже содержит целевые записи (обнаружен идентичный блок текста), "
                "дозапись пропущена")
            return True

        if not content or content.endswith("\n\n"):
            prefix = ""
        elif content.endswith("\n"):
            prefix = "\n"
        else:
            prefix = "\n\n"

        with open(hosts_file, "a", encoding=encoding) as f:
            f.write(prefix)
            f.write(hosts_block)
        log_func("⚠️ Выполнен откат к режиму дозаписи: атомарное добавление/удаление/дедупликация "
            "не гарантируются, управляйте записями hosts вручную.")
        return True
    except PermissionError as e:
        log_func(f"❌ Не удалось дописать в файл hosts: {e}")
        return False
    except OSError as e:
        log_func(f"❌ Не удалось дописать в файл hosts: {e}")
        return False


def _fallback_to_append(  # noqa: PLR0913
    *,
    hosts_file: str,
    hosts_block: str,
    encoding: str,
    log_func: LogFunc,
    reason: str,
    removed_entries: int = 0,
) -> bool:
    log_func(f"⚠️ {reason}")
    log_func("⚠️ Режим дозаписи не выполняет атомарное удаление/дедупликацию; для очистки "
        "отредактируйте hosts вручную.")
    if removed_entries:
        log_func("⚠️ Обнаружены старые дублирующиеся записи: дозапись не очищает старые записи, "
            "отредактируйте hosts вручную.")
    return _append_hosts_block_fallback(
        hosts_file,
        hosts_block,
        encoding,
        log_func=log_func,
    )


def check_hosts_file_operability(
    hosts_file: str, *, log_func: LogFunc = print
) -> FileOperabilityReport:
    """Предварительная проверка возможности записи в hosts (только проверка, глобальный блокирующий
    флаг не меняется)."""
    return check_file_operability(hosts_file, log_func=log_func)


def get_hosts_file_path(log_func: LogFunc = print) -> str:
    """Получить путь к файлу hosts"""
    if os.name == "nt":  # Windows
        warned = _HOSTS_PATH_FALLBACK_STATE
        system_root = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR")
        if not system_root:
            if not warned["warned"] and callable(log_func):
                log_func(
                    
                        "⚠️ Переменные окружения SYSTEMROOT/WINDIR не заданы, попробуем получить "
                        "каталог Windows через WinAPI."
                    
                )
            try:
                buffer = ctypes.create_unicode_buffer(260)
                size = ctypes.windll.kernel32.GetWindowsDirectoryW(buffer, len(buffer))
                if size:
                    system_root = buffer.value
            except Exception:
                if not warned["warned"] and callable(log_func):
                    log_func("⚠️ Вызов GetWindowsDirectoryW не удался, будет использован путь по "
                        "умолчанию.")
                system_root = None

        if not system_root and not warned["warned"]:
            if callable(log_func):
                log_func("⚠️ Не удалось определить каталог Windows, путь к hosts откатится к "
                    "C:\\Windows\\System32\\...")
            warned["warned"] = True

        system_root = system_root or r"C:\Windows"
        log_func(f"[hosts] system_root={system_root}")
        return os.path.join(system_root, "System32", "drivers", "etc", "hosts")
    else:  # Unix/Linux/macOS
        return "/etc/hosts"


def get_backup_file_path() -> str:
    """Получить путь к файлу резервной копии (хранится в каталоге пользовательских данных)"""
    resource_manager = ResourceManager()
    return resource_manager.get_hosts_backup_file()


def detect_file_encoding(file_path: str) -> str:
    """Определить кодировку файла"""
    encodings = ["utf-8", "gbk", "gb2312", "latin1", "utf-16"]
    for enc in encodings:
        try:
            with open(file_path, encoding=enc) as f:
                f.read()
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"  # кодировка по умолчанию


def backup_hosts_file(log_func: LogFunc = print) -> bool:
    """
    Создать резервную копию файла hosts

    Параметры:
        log_func: функция вывода логов

    Возвращает:
        True при успехе, False при ошибке
    """
    hosts_file = get_hosts_file_path(log_func)
    backup_file = get_backup_file_path()

    log_func("Начинаем резервное копирование файла hosts...")

    if not os.path.exists(hosts_file):
        log_func(f"Ошибка: файл hosts не найден: {hosts_file}")
        return False

    try:
        shutil.copy2(hosts_file, backup_file)
        log_func(f"Резервная копия файла hosts сохранена в: {backup_file}")
        return True
    except Exception as e:
        log_func(f"Не удалось создать резервную копию файла hosts: {e}")
        return False


def restore_hosts_file(log_func: LogFunc = print) -> bool:  # noqa: PLR0911
    """
    Восстановить файл hosts из резервной копии

    Параметры:
        log_func: функция вывода логов

    Возвращает:
        True при успехе, False при ошибке
    """
    hosts_file = get_hosts_file_path(log_func)
    backup_file = get_backup_file_path()

    log_func("Начинаем восстановление файла hosts...")
    if not guard_hosts_modify("restore", log_func=log_func):
        return False

    if not os.path.exists(backup_file):
        log_func(f"Ошибка: файл резервной копии не найден: {backup_file}")
        return False

    try:
        if sys.platform == "darwin":
            session = get_mac_privileged_session(log_func=log_func)
            if not session:
                return False
            if session.copy_file(backup_file, hosts_file, log_func=log_func):
                log_func("Файл hosts восстановлен")
                return True
            return False

        shutil.copy2(backup_file, hosts_file)
        log_func("Файл hosts восстановлен")
        return True
    except Exception as e:
        log_func(f"Не удалось восстановить файл hosts: {e}")
        return False


def write_hosts_file_with_permission(
    hosts_file: str, content: str, encoding: str, log_func: LogFunc = print
) -> bool:
    """
    Записать файл hosts с соответствующими правами

    Параметры:
        hosts_file: путь к файлу hosts
        content: записываемое содержимое
        encoding: кодировка файла
        log_func: функция вывода логов

    Возвращает:
        True при успехе, False при ошибке
    """
    if sys.platform == "darwin":
        session = get_mac_privileged_session(log_func=log_func)
        if not session:
            return False
        if session.write_file(hosts_file, content, encoding, log_func=log_func):
            log_func("✅ Файл hosts успешно записан")
            return True
        return False
    else:
        # Windows и прочие системы: прямая запись
        try:
            if os.name == "nt":
                check_file_operability(hosts_file, log_func=log_func)
                ensure_windows_file_writable(hosts_file, log_func=log_func)
            with open(hosts_file, "w", encoding=encoding) as f:
                f.write(content)
            return True
        except PermissionError as e:
            if os.name == "nt":
                is_admin = is_windows_admin()
                winerror = getattr(e, "winerror", None)
                log_func(
                    f"❌ Недостаточно прав, запустите от имени администратора "
                    f"(is_admin={is_admin}, winerror={winerror})"
                )
                log_func("⚠️ Если вы уже администратор, возможно, hosts заблокирован антивирусом "
                    "или атрибутом «только чтение» — снимите блокировку и повторите")
            else:
                log_func("❌ Недостаточно прав, запустите от имени администратора или через sudo")
            return False
        except OSError as e:
            log_func(f"❌ Не удалось записать файл hosts: {e}")
            return False


def add_hosts_entry(  # noqa: PLR0911
    domain: str,
    ip: str | Iterable[object] | object | None = DEFAULT_HOSTS_IPS,
    log_func: LogFunc = print,
) -> bool:
    """
    Добавить запись в hosts

    Параметры:
        domain: домен
        ip: один IP строкой или итерируемый набор IP
        log_func: функция вывода логов

    Возвращает:
        True при успехе, False при ошибке
    """
    ip_list = normalize_ip_list(ip)
    if not ip_list:
        log_func("Не указаны корректные IP, изменение hosts отменено")
        return False

    hosts_file = get_hosts_file_path(log_func)
    backup_file = get_backup_file_path()

    ip_text = ", ".join(f"{addr} {domain}" for addr in ip_list)
    log_func(f"Начинаем добавление записей hosts: {ip_text}")

    if not os.path.exists(hosts_file):
        log_func(f"Ошибка: файл hosts не найден: {hosts_file}")
        return False

    try:
        # Сначала резервная копия (если её ещё нет)
        if not os.path.exists(backup_file):
            shutil.copy2(hosts_file, backup_file)
            log_func(f"Резервная копия файла hosts автоматически сохранена в: {backup_file}")

        # Определяем кодировку файла
        encoding = detect_file_encoding(hosts_file)
        log_func(f"Определена кодировка файла hosts: {encoding}")

        # Читаем содержимое файла hosts
        with open(hosts_file, encoding=encoding, errors="replace") as f:
            content = f.read()

        hosts_block = build_hosts_block(domain, ip_list)
        if not hosts_block:
            log_func("Не удалось сформировать данные для записи в hosts, операция отменена")
            return False

        if (
            hosts_block in content
            or f"\n{hosts_block}" in content
            or f"\n\n{hosts_block}" in content
        ):
            log_func("Файл hosts уже содержит целевые записи, изменения не требуются")
            return True

        state = get_hosts_modify_block_state()
        if state.blocked:
            reason = state.reason or (state.report.status.value if state.report else "unknown")
            return _fallback_to_append(
                hosts_file=hosts_file,
                hosts_block=hosts_block,
                encoding=encoding,
                log_func=log_func,
                reason=(
                    f"Запись в hosts в текущем окружении ограничена (reason={reason}), переходим в "
                    f"режим дозаписи."
                ),
            )

        # Удаляем старые записи, чтобы запись была атомарным блоком
        content, removed_entries = remove_hosts_block_from_content(content, domain, ip_list)
        if removed_entries:
            log_func(
                f"Обнаружены дублирующиеся записи, удалено записей {domain}: {removed_entries}"
            )

        # Добавляем единый текстовый блок, сохраняя пустую строку
        content = append_hosts_block(content, hosts_block)

        # Запись с учётом прав
        write_success = write_hosts_file_with_permission(hosts_file, content, encoding, log_func)
        if write_success:
            log_func("Файл hosts успешно изменён!")
            return True

        if os.name == "nt":
            return _fallback_to_append(
                hosts_file=hosts_file,
                hosts_block=hosts_block,
                encoding=encoding,
                log_func=log_func,
                reason=(
                    "Атомарная запись в hosts не удалась, пробуем режим дозаписи (без гарантии "
                    "атомарного добавления/удаления/дедупликации)."
                ),
                removed_entries=removed_entries,
            )

        return False

    except Exception as e:
        log_func(f"Не удалось изменить файл hosts: {e}")
        return False


def remove_hosts_entry(
    domain: str, log_func: LogFunc = print, *, ip: str | Iterable[object] | object | None = None
) -> bool:
    """
    Удалить запись из hosts

    Параметры:
        domain: удаляемый домен
        ip: список IP для удаления (по умолчанию два адреса, записанные модулем)
        log_func: функция вывода логов

    Возвращает:
        True при успехе, False при ошибке
    """
    if not guard_hosts_modify("remove", log_func=log_func):
        return False
    ip_list = normalize_ip_list(ip)

    hosts_file = get_hosts_file_path(log_func)

    log_func(f"Начинаем удаление записей hosts: {domain}")

    if not os.path.exists(hosts_file):
        log_func(f"Ошибка: файл hosts не найден: {hosts_file}")
        return False

    try:
        # Определяем кодировку файла
        encoding = detect_file_encoding(hosts_file)
        log_func(f"Определена кодировка файла hosts: {encoding}")

        with open(hosts_file, encoding=encoding, errors="replace") as f:
            content = f.read()

        new_content, removed_count = remove_hosts_block_from_content(content, domain, ip_list)

        if removed_count > 0:
            if write_hosts_file_with_permission(hosts_file, new_content, encoding, log_func):
                log_func(f"Файл hosts обновлён, удалено записей {domain}: {removed_count}")
            else:
                return False
        else:
            log_func(f"Записи {domain} в файле hosts не найдены")

        return True

    except Exception as e:
        log_func(f"Не удалось удалить записи hosts: {e}")
        return False


def open_hosts_file(log_func: LogFunc = print) -> bool:
    """
    Открыть файл hosts с учётом платформы

    Параметры:
        log_func: функция вывода логов

    Возвращает:
        True при успехе, False при ошибке
    """
    hosts_file = get_hosts_file_path(log_func)
    result = False

    try:
        if os.name == "nt":  # Windows
            subprocess.run(["notepad", hosts_file], check=True)
            log_func("Файл hosts открыт в Блокноте")
            result = True
        elif sys.platform == "darwin":  # macOS
            session = get_mac_privileged_session(log_func=log_func)
            if session:
                success, data = session.run_command(["open", "-t", hosts_file], log_func=log_func)
                data_dict = data
                if success:
                    log_func("Файл hosts открыт в текстовом редакторе по умолчанию")
                    result = True
                else:
                    error_msg = (
                        data_dict.get("stderr")
                        or data_dict.get("error")
                        or data_dict.get("stdout")
                        or ""
                    )
                    log_func(f"Не удалось открыть файл hosts: {error_msg or 'Неизвестная ошибка'}")
            else:
                log_func("⚠️ Для открытия файла hosts нужны права администратора, операция отменена")
        else:  # Linux
            editors = ["gedit", "nano", "vim"]
            for editor in editors:
                try:
                    subprocess.run([editor, hosts_file], check=True)
                    log_func(f"Файл hosts открыт в {editor}")
                    result = True
                    break
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue
            if not result:
                log_func("Подходящий текстовый редактор не найден")

        return result

    except Exception as e:
        log_func(f"Не удалось открыть файл hosts: {e}")
        return False


def modify_hosts_file(
    domain: str = "api.openai.com",
    action: str = "add",
    ip: str | Iterable[object] | object | None = DEFAULT_HOSTS_IPS,
    log_func: LogFunc = print,
) -> bool:
    """
    Основная функция изменения файла hosts

    Параметры:
        domain: домен
        action: тип операции ("add", "remove", "backup", "restore")
        ip: один IP строкой или итерируемый набор IP (только при action="add")
        log_func: функция вывода логов

    Возвращает:
        True при успехе, False при ошибке
    """
    action_names = {
        "add": "добавление записей",
        "remove": "удаление записей",
        "backup": "резервное копирование файла",
        "restore": "восстановление файла",
    }

    log_func(f"Начинаем операцию с файлом hosts: {action_names.get(action, action)}")

    if action == "backup":
        return backup_hosts_file(log_func)
    elif action == "restore":
        return restore_hosts_file(log_func)
    elif action == "add":
        return add_hosts_entry(domain, ip=ip, log_func=log_func)
    elif action == "remove":
        return remove_hosts_entry(domain, log_func=log_func, ip=ip)
    else:
        log_func(f"Ошибка: неподдерживаемый тип операции: {action}")
        return False
