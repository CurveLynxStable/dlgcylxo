from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from types import TracebackType
from typing import Any


def setup_error_logging(
    *,
    get_log_path: Callable[[str], str],
    error_log_filename: str,
    logger_name: str = "mtga_gui",
) -> str:
    """Настраивает глобальное логирование: уровень ERROR пишется в пользовательский каталог логов с
    меткой времени."""
    log_path = get_log_path(error_log_filename)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if not any(
        isinstance(handler, logging.FileHandler)
        and getattr(handler, "baseFilename", None) == os.path.abspath(log_path)
        for handler in root_logger.handlers
    ):
        root_logger.addHandler(file_handler)

    logging.getLogger(logger_name)

    return log_path


def log_error(message: str, exc_info: Any = None, *, logger_name: str = "mtga_gui") -> None:
    """Единая точка логирования ошибок: запись в файл с меткой времени."""
    logging.getLogger(logger_name).error(message, exc_info=exc_info)


def install_global_exception_hook(*, log_error: Callable[..., None]) -> None:
    """Записывает неперехваченные исключения в лог ошибок."""

    def handle_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        log_error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
