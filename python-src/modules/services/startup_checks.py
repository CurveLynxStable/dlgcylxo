from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass

from modules.hosts.file_operability import FileOperabilityReport, check_file_operability
from modules.hosts.hosts_manager import get_hosts_file_path
from modules.hosts.hosts_state import (
    ALLOW_UNSAFE_HOSTS_FLAG,
    configure_hosts_modify_block,
    get_hosts_modify_block_report,
    is_hosts_modify_blocked,
)
from modules.network.network_environment import NetworkEnvironmentReport, check_network_environment
from modules.platform.system import is_windows


@dataclass(frozen=True)
class StartupReport:
    env_ok: bool
    env_message: str


def run_hosts_preflight() -> FileOperabilityReport | None:
    """При запуске проверяет файл hosts и при необходимости включает ограниченный режим hosts."""
    if not is_windows():
        return None
    logger = logging.getLogger("mtga_gui")

    def warn(message: str) -> None:
        logger.warning(message)

    hosts_file = get_hosts_file_path(log_func=print)
    report = check_file_operability(hosts_file, log_func=warn)

    if report.ok:
        return report

    if ALLOW_UNSAFE_HOSTS_FLAG in sys.argv:
        warn(
            f"⚠️ Предварительная проверка hosts не пройдена (status={report.status.value}), но "
            f"применён параметр запуска "
            f"{ALLOW_UNSAFE_HOSTS_FLAG}; последующие автоматические изменения могут не удаться."
        )
        return report

    configure_hosts_modify_block(
        True,
        reason=report.status.value,
        report=report,
    )
    warn(
        f"⚠️ Предварительная проверка hosts не пройдена (status={report.status.value}), "
        f"включён ограниченный режим hosts: "
        "добавление будет выполняться в режиме дозаписи (без гарантии атомарного "
        "добавления/удаления/дедупликации), автоматическое удаление/восстановление будет "
        "отключено."
    )
    return report


def run_network_environment_preflight() -> NetworkEnvironmentReport:
    """При запуске проверяет сетевое окружение (явный прокси), чтобы предупредить о возможном
    обходе перенаправления через hosts."""
    logger = logging.getLogger("mtga_gui")

    def warn(message: str) -> None:
        logger.warning(message)

    return check_network_environment(log_func=warn, emit_logs=True)


def emit_startup_logs(
    *,
    log: Callable[[str], None],
    check_environment: Callable[[], tuple[bool, str]],
    is_packaged: Callable[[], bool],
    hosts_preflight_report: FileOperabilityReport | None,
    network_env_report: NetworkEnvironmentReport | None,
) -> StartupReport:
    env_ok, env_msg = check_environment()
    if env_ok:
        log(f"✅ {env_msg}")
        if is_packaged():
            log("📦 Запущено в упакованном окружении")
        else:
            log("🔧 Запущено в среде разработки")
    else:
        log(f"❌ {env_msg}")

    if is_hosts_modify_blocked():
        report = get_hosts_modify_block_report()
        status = report.status.value if report else "unknown"
        log(
            f"⚠️ Обнаружено ограничение записи в файл hosts (status={status}), включён "
            f"ограниченный режим hosts: "
            "добавление будет выполняться в режиме дозаписи (без гарантии атомарного "
            "добавления/удаления/дедупликации), автоматическое удаление/восстановление будет "
            "отключено."
        )
        log(
            "⚠️ Вы можете нажать «Открыть файл hosts» и изменить его вручную; либо "
            "использовать параметр запуска "
            f"{ALLOW_UNSAFE_HOSTS_FLAG}, чтобы обойти эту проверку и принудительно попробовать "
            f"атомарную запись (на свой риск)."
        )
    elif hosts_preflight_report is not None and not hosts_preflight_report.ok:
        log(
            f"⚠️ Предварительная проверка hosts не пройдена "
            f"(status={hosts_preflight_report.status.value}), "
            f"но применён параметр запуска {ALLOW_UNSAFE_HOSTS_FLAG}; последующие "
            f"автоматические изменения могут не удаться."
        )

    if network_env_report is not None and network_env_report.explicit_proxy_detected:
        log("⚠️" * 21 + "\nОбнаружена явная настройка прокси: часть приложений может идти через "
            "прокси и обходить перенаправление через hosts.")
        log("Рекомендации: 1. Отключите явный прокси (например системный прокси clash) или "
            "используйте TUN/VPN")
        log("      2. Проверьте настройки прокси в Trae.\n" + "⚠️" * 21)

    return StartupReport(env_ok=env_ok, env_message=env_msg)
