"""
Модуль проверки наличия сертификата
Кросс-платформенная проверка, исключающая повторную генерацию или установку.
"""
from __future__ import annotations

from collections.abc import Callable

from modules.cert.ca_store import check_ca_cert
from modules.runtime.operation_result import OperationResult

type LogFunc = Callable[[str], None]


def check_existing_ca_cert(ca_common_name: str, log_func: LogFunc = print) -> OperationResult:
    """Возвращает результат проверки; в details есть флаг exists."""
    return check_ca_cert(ca_common_name, log_func=log_func)


def has_existing_ca_cert(ca_common_name: str, log_func: LogFunc = print) -> bool:
    """Кросс-платформенно проверяет, есть ли в системе CA-сертификат с указанным Common Name."""
    result = check_existing_ca_cert(ca_common_name, log_func=log_func)
    if not result.ok:
        return False
    return bool(result.details.get("exists"))


__all__ = ["check_existing_ca_cert", "has_existing_ca_cert"]
