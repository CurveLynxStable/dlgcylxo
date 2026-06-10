from __future__ import annotations

from collections.abc import Callable

from modules.runtime.result_messages import describe_result
from modules.runtime.thread_manager import ThreadManager
from modules.services import cert_service


def run_generate_certificates(
    *,
    ca_common_name: str,
    log_func: Callable[[str], None],
    thread_manager: ThreadManager,
) -> None:
    def task():
        log_func("Начинаем генерацию сертификатов...")
        result = cert_service.generate_certificates_result(
            log_func=log_func,
            ca_common_name=ca_common_name,
        )
        if result.ok:
            log_func("✅ Генерация сертификатов завершена")
        else:
            message = describe_result(result, "Не удалось сгенерировать сертификаты")
            log_func(f"❌ {message}")

    thread_manager.run("cert_generate", task)


def run_install_ca_cert(
    *,
    log_func: Callable[[str], None],
    thread_manager: ThreadManager,
) -> None:
    def task():
        log_func("Начинаем установку CA-сертификата...")
        result = cert_service.install_ca_cert_result(log_func=log_func)
        if result.ok:
            log_func("✅ Установка CA-сертификата завершена")
        else:
            message = describe_result(result, "Не удалось установить CA-сертификат")
            log_func(f"❌ {message}")

    thread_manager.run("cert_install", task)


def run_clear_ca_cert(
    *,
    ca_common_name: str,
    log_func: Callable[[str], None],
    thread_manager: ThreadManager,
) -> None:
    def task():
        log_func("Начинаем удаление CA-сертификата...")
        result = cert_service.clear_ca_cert_result(
            ca_common_name=ca_common_name,
            log_func=log_func,
        )
        if result.ok:
            log_func("✅ Удаление CA-сертификата завершено")
        else:
            message = describe_result(result, "Не удалось удалить CA-сертификат")
            log_func(f"❌ {message}")

    thread_manager.run("cert_clear", task)
