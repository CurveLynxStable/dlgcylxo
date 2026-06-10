from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from modules.hosts.file_operability import FileOperabilityReport

ALLOW_UNSAFE_HOSTS_FLAG = "--allow-unsafe-hosts"
type LogFunc = Callable[[str], None]


@dataclass
class HostsModifyBlockState:
    blocked: bool = False
    reason: str | None = None
    report: FileOperabilityReport | None = None


_HOSTS_MODIFY_BLOCK_STATE = HostsModifyBlockState()


def configure_hosts_modify_block(
    blocked: bool,
    *,
    reason: str | None = None,
    report: FileOperabilityReport | None = None,
) -> None:
    """Настраивает блокировку автоматического изменения hosts (задаётся предварительной проверкой
    при запуске GUI)."""
    state = _HOSTS_MODIFY_BLOCK_STATE
    state.blocked = bool(blocked)
    state.reason = reason
    state.report = report


def is_hosts_modify_blocked() -> bool:
    return _HOSTS_MODIFY_BLOCK_STATE.blocked


def get_hosts_modify_block_report() -> FileOperabilityReport | None:
    return _HOSTS_MODIFY_BLOCK_STATE.report


def get_hosts_modify_block_state() -> HostsModifyBlockState:
    return _HOSTS_MODIFY_BLOCK_STATE


def should_block_hosts_action(action: str) -> bool:
    return action in {"remove", "restore"}


def guard_hosts_modify(action: str, log_func: LogFunc = print) -> bool:
    """Если операция заблокирована — выводит подсказку и возвращает False; иначе True."""
    state = _HOSTS_MODIFY_BLOCK_STATE
    if not state.blocked:
        return True
    if not should_block_hosts_action(action):
        return True
    report = state.report
    reason = state.reason or (report.status.value if report else "unknown")
    allow_flag = ALLOW_UNSAFE_HOSTS_FLAG
    log_func(f"⚠️ В текущем окружении запись в hosts ограничена (reason={reason}).")
    log_func("⚠️ Автоматическое удаление/восстановление требует атомарной перезаписи и в этом "
        "окружении отключено; управляйте hosts вручную.")
    log_func("⚠️ Вы можете нажать «Открыть файл hosts», изменить его вручную и повторить попытку.")
    log_func(f"⚠️ Если всё же нужно автоматическое изменение, используйте параметр запуска "
        f"{allow_flag}, чтобы обойти эту проверку (на свой риск).")
    return False


__all__ = [
    "ALLOW_UNSAFE_HOSTS_FLAG",
    "HostsModifyBlockState",
    "configure_hosts_modify_block",
    "get_hosts_modify_block_report",
    "get_hosts_modify_block_state",
    "guard_hosts_modify",
    "is_hosts_modify_blocked",
    "should_block_hosts_action",
]
