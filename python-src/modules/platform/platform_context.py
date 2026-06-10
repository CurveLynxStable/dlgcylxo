from __future__ import annotations

import os

_SUPPORTED = {"tauri", "legacy"}


def get_platform() -> str:
    value = os.environ.get("MTGA_PLATFORM", "").strip().lower()
    if value in _SUPPORTED:
        return value
    raise RuntimeError(
        
            "MTGA_PLATFORM не задана или некорректна (поддерживаются только tauri/legacy); задайте "
            "её в точке входа."
        
    )


__all__ = ["get_platform"]
