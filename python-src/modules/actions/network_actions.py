from __future__ import annotations

from collections.abc import Callable

from modules.network.network_environment import check_network_environment
from modules.runtime.thread_manager import ThreadManager


def run_network_environment_check(
    *,
    log_func: Callable[[str], None],
    thread_manager: ThreadManager,
) -> None:
    def task() -> None:
        log_func("Начинаем проверку сетевого окружения...")
        report = check_network_environment(
            log_func=log_func,
            emit_logs=True,
        )
        if report.explicit_proxy_detected:
            log_func("⚠️ Обнаружена явная настройка прокси: перенаправление через hosts может быть "
                "обойдено.\n" + "⚠️" * 21)
            return
        log_func("✅ Явная настройка прокси на уровне системы/переменных окружения не обнаружена.")
        log_func(
            "ℹ️ Если подключения по-прежнему нет, проверьте настройки прокси в Trae "
            "или включённые TUN/VPN/средства сетевой защиты."
        )

    thread_manager.run("network_env_check", task)
