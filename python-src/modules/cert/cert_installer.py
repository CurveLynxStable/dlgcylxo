"""
Модуль установки сертификатов
Устанавливает CA-сертификат в систему и настраивает доверие
"""

from __future__ import annotations

import os
from collections.abc import Callable

from modules.cert.ca_store import install_ca_cert_file
from modules.runtime.operation_result import OperationResult
from modules.runtime.resource_manager import ResourceManager

type LogFunc = Callable[[str], None]


def install_ca_cert_result(log_func: LogFunc = print) -> OperationResult:
    """Устанавливает CA-сертификат в зависимости от ОС и возвращает объект результата."""
    log_func("Начинаем установку CA-сертификата...")

    resource_manager = ResourceManager()
    possible_cert_files = [
        resource_manager.get_ca_cert_file(),
        os.path.join(resource_manager.ca_path, "rootCA.crt"),
        os.path.join(resource_manager.ca_path, "ca.cer"),
        os.path.join(resource_manager.ca_path, "rootCA.cer"),
    ]

    ca_cert_file = None
    for cert_file in possible_cert_files:
        if os.path.exists(cert_file):
            ca_cert_file = cert_file
            log_func(f"Найден файл CA-сертификата: {ca_cert_file}")
            break

    if ca_cert_file is None:
        log_func(f"Ошибка: файл CA-сертификата не найден, проверены пути: "
            f"{', '.join(possible_cert_files)}")
        return OperationResult.failure("Файл CA-сертификата не найден")

    try:
        return install_ca_cert_file(ca_cert_file, log_func=log_func)
    except Exception as exc:  # noqa: BLE001
        log_func(f"Не удалось установить CA-сертификат: {exc}")
        return OperationResult.failure("Не удалось установить CA-сертификат")


def install_ca_cert(log_func: LogFunc = print) -> bool:
    """Устанавливает CA-сертификат в зависимости от ОС и возвращает признак успеха."""
    return install_ca_cert_result(log_func=log_func).ok


__all__ = ["install_ca_cert", "install_ca_cert_result"]
