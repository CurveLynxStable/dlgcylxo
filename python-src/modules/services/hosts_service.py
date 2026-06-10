from __future__ import annotations

from collections.abc import Callable, Iterable

from modules.hosts.hosts_manager import (
    backup_hosts_file,
    modify_hosts_file,
    open_hosts_file,
    remove_hosts_entry,
    restore_hosts_file,
)
from modules.runtime.operation_result import OperationResult

type LogFunc = Callable[[str], None]


def backup_hosts_file_result(*, log_func: LogFunc = print) -> OperationResult:
    if backup_hosts_file(log_func=log_func):
        return OperationResult.success()
    return OperationResult.failure("Не удалось создать резервную копию файла hosts")


def restore_hosts_file_result(*, log_func: LogFunc = print) -> OperationResult:
    if restore_hosts_file(log_func=log_func):
        return OperationResult.success()
    return OperationResult.failure("Не удалось восстановить файл hosts")


def remove_hosts_entry_result(
    *, domain: str, log_func: LogFunc = print, ip: str | Iterable[object] | object | None = None
) -> OperationResult:
    if remove_hosts_entry(domain, log_func=log_func, ip=ip):
        return OperationResult.success()
    return OperationResult.failure("Не удалось удалить записи hosts")


def modify_hosts_file_result(
    *,
    domain: str = "api.openai.com",
    action: str = "add",
    ip: str | Iterable[object] | object | None = None,
    log_func: LogFunc = print,
) -> OperationResult:
    if modify_hosts_file(domain=domain, action=action, ip=ip, log_func=log_func):
        return OperationResult.success()
    return OperationResult.failure("Не удалось изменить файл hosts")


def open_hosts_file_result(*, log_func: LogFunc = print) -> OperationResult:
    if open_hosts_file(log_func=log_func):
        return OperationResult.success()
    return OperationResult.failure("Не удалось открыть файл hosts")

__all__ = [
    "backup_hosts_file",
    "backup_hosts_file_result",
    "modify_hosts_file",
    "modify_hosts_file_result",
    "open_hosts_file",
    "open_hosts_file_result",
    "remove_hosts_entry",
    "remove_hosts_entry_result",
    "restore_hosts_file",
    "restore_hosts_file_result",
]
