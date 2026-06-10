from __future__ import annotations

import json
import os
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


_APP_STATE: dict[str, str | None] = {"version": None}


def set_app_version(value: str | None) -> None:
    """Версия внедряется хостом (Tauri), чтобы не читать файлы этапа сборки."""

    def normalize_version(raw_value: str | None) -> str | None:
        if not raw_value:
            return None
        raw_value = raw_value.strip()
        if not raw_value:
            return None
        return raw_value if raw_value.startswith("v") else f"v{raw_value}"

    _APP_STATE["version"] = normalize_version(value)


def resolve_app_version(*, project_root: Path) -> str:
    """Определяет версию приложения из внедрения хоста/переменных окружения/pyproject.toml."""

    def normalize_version(raw_value: str | None) -> str | None:
        if not raw_value:
            return None
        raw_value = raw_value.strip()
        if not raw_value:
            return None
        return raw_value if raw_value.startswith("v") else f"v{raw_value}"

    version = normalize_version(os.getenv("MTGA_VERSION"))
    if not version:
        version = normalize_version(_APP_STATE.get("version"))

    if not version:
        tauri_conf_path = project_root / "src-tauri" / "tauri.conf.json"
        try:
            with tauri_conf_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            version = normalize_version(data.get("version"))
        except Exception:
            version = None

    if not version and tomllib is not None:
        pyproject_path = project_root / "python-src" / "pyproject.toml"
        try:
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
            version = normalize_version(data.get("project", {}).get("version"))
        except Exception:
            version = None

    return version or "v0.0.0"
