from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ProxyState:
    instance: Any | None = None


_STATE = ProxyState()


def get_proxy_instance() -> Any | None:
    """Возвращает текущий экземпляр прокси"""
    return _STATE.instance


def set_proxy_instance(instance: Any | None) -> None:
    """Обновляет текущий экземпляр прокси"""
    _STATE.instance = instance
