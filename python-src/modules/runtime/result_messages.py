from __future__ import annotations

from modules.runtime.error_codes import ErrorCode
from modules.runtime.operation_result import OperationResult

_DEFAULT_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.NETWORK_ERROR: "Сетевая ошибка",
    ErrorCode.REMOTE_ERROR: "Ошибка удалённого сервиса",
    ErrorCode.NO_VERSION: "Не удалось разобрать номер версии",
    ErrorCode.BACKUP_DIR_MISSING: "Каталог резервных копий не найден",
    ErrorCode.NO_BACKUPS: "Резервные копии не найдены",
    ErrorCode.CONFIG_INVALID: "Некорректная конфигурация",
    ErrorCode.FILE_NOT_FOUND: "Файл не найден",
    ErrorCode.PERMISSION_DENIED: "Недостаточно прав",
    ErrorCode.PORT_IN_USE: "Порт уже занят",
    ErrorCode.UNKNOWN: "Произошла неизвестная ошибка",
}


def describe_result(result: OperationResult, default_message: str) -> str:
    if result.message:
        return result.message
    if result.code and result.code in _DEFAULT_MESSAGES:
        return _DEFAULT_MESSAGES[result.code]
    return default_message


__all__ = ["describe_result"]
