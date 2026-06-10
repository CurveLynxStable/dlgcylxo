"""
Модуль очистки сертификатов
Кросс-платформенное удаление CA-сертификатов без встраивания платформенных скриптов в GUI.
"""

from __future__ import annotations

from collections.abc import Callable

from modules.cert.ca_store import clear_ca_cert_store
from modules.runtime.operation_result import OperationResult

type LogFunc = Callable[[str], None]


def clear_ca_cert_result(ca_common_name: str, log_func: LogFunc = print) -> OperationResult:
    """Возвращает результат очистки."""
    return clear_ca_cert_store(ca_common_name, log_func=log_func)


def clear_ca_cert(ca_common_name: str, log_func: LogFunc = print) -> bool:
    """Удаляет CA-сертификат из системного хранилища доверия в зависимости от ОС."""
    return clear_ca_cert_result(ca_common_name, log_func=log_func).ok


__all__ = ["clear_ca_cert", "clear_ca_cert_result"]
