"""
Проверка сетевого окружения (по возможности без привязки к конкретному прокси-ПО)

Цель: не выполняя сетевых запросов, на основе системной конфигурации предупредить
о возможном обходе перенаправления через hosts.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

try:
    import winreg  # type: ignore
except Exception:  # pragma: no cover
    winreg = None  # type: ignore

try:
    import ctypes as _ctypes
    from ctypes import wintypes as _wintypes
except Exception:  # pragma: no cover
    _ctypes = None  # type: ignore
    _wintypes = None  # type: ignore


@dataclass(frozen=True)
class NetworkEnvironmentReport:
    explicit_proxy_detected: bool
    wininet_proxy_enabled: bool | None = None
    wininet_proxy_server: str | None = None
    wininet_auto_config_url: str | None = None
    wininet_proxy_override: str | None = None
    winhttp_proxy: str | None = None
    winhttp_proxy_bypass: str | None = None
    env_http_proxy: str | None = None
    env_https_proxy: str | None = None
    env_all_proxy: str | None = None
    env_no_proxy: str | None = None
type LogFunc = Callable[[str], None]


def _read_env_proxy_settings() -> dict[str, str | None]:
    def get_any(*names: str) -> str | None:
        for name in names:
            value = os.environ.get(name)
            if value:
                return value
        return None

    return {
        "env_http_proxy": get_any("HTTP_PROXY", "http_proxy"),
        "env_https_proxy": get_any("HTTPS_PROXY", "https_proxy"),
        "env_all_proxy": get_any("ALL_PROXY", "all_proxy"),
        "env_no_proxy": get_any("NO_PROXY", "no_proxy"),
    }


def _read_wininet_proxy_settings(log_func: LogFunc) -> dict[str, object | None]:
    if os.name != "nt":
        return {
            "wininet_proxy_enabled": None,
            "wininet_proxy_server": None,
            "wininet_auto_config_url": None,
            "wininet_proxy_override": None,
    }

    if winreg is None:
        return {
            "wininet_proxy_enabled": None,
            "wininet_proxy_server": None,
            "wininet_auto_config_url": None,
            "wininet_proxy_override": None,
        }

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    values: dict[str, object | None] = {
        "wininet_proxy_enabled": None,
        "wininet_proxy_server": None,
        "wininet_auto_config_url": None,
        "wininet_proxy_override": None,
    }

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            try:
                values["wininet_proxy_enabled"] = bool(winreg.QueryValueEx(key, "ProxyEnable")[0])
            except OSError:
                values["wininet_proxy_enabled"] = False

            try:
                values["wininet_proxy_server"] = winreg.QueryValueEx(key, "ProxyServer")[0] or None
            except OSError:
                values["wininet_proxy_server"] = None

            try:
                values["wininet_auto_config_url"] = (
                    winreg.QueryValueEx(key, "AutoConfigURL")[0] or None
                )
            except OSError:
                values["wininet_auto_config_url"] = None

            try:
                values["wininet_proxy_override"] = (
                    winreg.QueryValueEx(key, "ProxyOverride")[0] or None
                )
            except OSError:
                values["wininet_proxy_override"] = None
    except OSError as e:
        log_func(f"⚠️ Не удалось прочитать системный прокси (WinINET): {e}")

    return values


def _read_winhttp_proxy_settings(log_func: LogFunc) -> dict[str, str | None]:
    if os.name != "nt":
        return {"winhttp_proxy": None, "winhttp_proxy_bypass": None}

    if _ctypes is None or _wintypes is None:
        return {"winhttp_proxy": None, "winhttp_proxy_bypass": None}

    ctypes = _ctypes
    wintypes = _wintypes

    winhttp = ctypes.WinDLL("winhttp", use_last_error=True)

    class WINHTTP_CURRENT_USER_IE_PROXY_CONFIG(ctypes.Structure):
        _fields_ = [
            ("fAutoDetect", wintypes.BOOL),
            ("lpszAutoConfigUrl", wintypes.LPVOID),
            ("lpszProxy", wintypes.LPVOID),
            ("lpszProxyBypass", wintypes.LPVOID),
        ]

    winhttp.WinHttpGetIEProxyConfigForCurrentUser.argtypes = [
        ctypes.POINTER(WINHTTP_CURRENT_USER_IE_PROXY_CONFIG)
    ]
    winhttp.WinHttpGetIEProxyConfigForCurrentUser.restype = wintypes.BOOL

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL

    config = WINHTTP_CURRENT_USER_IE_PROXY_CONFIG()
    if not winhttp.WinHttpGetIEProxyConfigForCurrentUser(ctypes.byref(config)):
        err = ctypes.get_last_error()
        log_func(f"⚠️ Не удалось прочитать системный прокси (WinHTTP): winerror={err}")
        return {"winhttp_proxy": None, "winhttp_proxy_bypass": None}

    def _consume(ptr: Any) -> str | None:
        if not ptr:
            return None
        try:
            value = ctypes.wstring_at(ptr)
            return value or None
        finally:
            with suppress(Exception):
                kernel32.GlobalFree(ptr)

    proxy = _consume(config.lpszProxy)
    bypass = _consume(config.lpszProxyBypass)
    _consume(config.lpszAutoConfigUrl)

    return {"winhttp_proxy": proxy, "winhttp_proxy_bypass": bypass}


def check_network_environment(
    *,
    log_func: LogFunc = print,
    emit_logs: bool = False,
) -> NetworkEnvironmentReport:
    """
    Проверяет сетевое окружение и предупреждает, что явный прокси может обойти
    перенаправление через hosts.

    Примечание: проверка определяет только явную настройку прокси на уровне
    системы/переменных окружения и не гарантирует, что сторонние приложения ей следуют.
    """
    env = _read_env_proxy_settings()
    wininet = _read_wininet_proxy_settings(log_func)
    winhttp = _read_winhttp_proxy_settings(log_func)

    if wininet.get("wininet_proxy_enabled") is not None:
        wininet_proxy_enabled = bool(wininet.get("wininet_proxy_enabled"))
    else:
        wininet_proxy_enabled = None
    def _as_str(value: object | None) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return None

    wininet_proxy_server = _as_str(wininet.get("wininet_proxy_server"))
    wininet_auto_config_url = _as_str(wininet.get("wininet_auto_config_url"))
    wininet_proxy_override = _as_str(wininet.get("wininet_proxy_override"))

    winhttp_proxy = winhttp.get("winhttp_proxy") or None
    winhttp_proxy_bypass = winhttp.get("winhttp_proxy_bypass") or None

    env_http_proxy = env.get("env_http_proxy")
    env_https_proxy = env.get("env_https_proxy")
    env_all_proxy = env.get("env_all_proxy")
    env_no_proxy = env.get("env_no_proxy")

    explicit_proxy_detected = False
    if wininet_proxy_enabled and wininet_proxy_server:
        explicit_proxy_detected = True
    if wininet_auto_config_url:
        explicit_proxy_detected = True
    if winhttp_proxy:
        explicit_proxy_detected = True
    if env_http_proxy or env_https_proxy or env_all_proxy:
        explicit_proxy_detected = True

    report = NetworkEnvironmentReport(
        explicit_proxy_detected=explicit_proxy_detected,
        wininet_proxy_enabled=wininet_proxy_enabled,
        wininet_proxy_server=wininet_proxy_server,
        wininet_auto_config_url=wininet_auto_config_url,
        wininet_proxy_override=wininet_proxy_override,
        winhttp_proxy=winhttp_proxy,
        winhttp_proxy_bypass=winhttp_proxy_bypass,
        env_http_proxy=env_http_proxy,
        env_https_proxy=env_https_proxy,
        env_all_proxy=env_all_proxy,
        env_no_proxy=env_no_proxy,
    )

    if emit_logs and explicit_proxy_detected:
        _emit_proxy_warnings(report, log_func)

    return report


def _emit_proxy_warnings(report: NetworkEnvironmentReport, log_func: LogFunc) -> None:
    log_func("⚠️" * 21 + "\nОбнаружена явная настройка прокси: часть приложений может идти через "
        "прокси и обходить перенаправление через hosts.")
    if report.wininet_proxy_enabled:
        server = report.wininet_proxy_server or "none"
        log_func(f"ℹ️ Системный прокси (WinINET): enabled=True, server={server}")
    if report.wininet_auto_config_url:
        log_func(f"ℹ️ Системный прокси (PAC): {report.wininet_auto_config_url}")
    if report.winhttp_proxy:
        log_func(f"ℹ️ Прокси WinHTTP: {report.winhttp_proxy}")
    if report.env_http_proxy or report.env_https_proxy or report.env_all_proxy:
        http_proxy = report.env_http_proxy or "none"
        https_proxy = report.env_https_proxy or "none"
        all_proxy = report.env_all_proxy or "none"
        log_func(
            "ℹ️ Прокси из переменных окружения: "
            f"HTTP_PROXY={http_proxy}, "
            f"HTTPS_PROXY={https_proxy}, "
            f"ALL_PROXY={all_proxy}"
        )
    log_func("Рекомендации: 1. Отключите явный прокси (например системный прокси clash) или "
        "используйте TUN/VPN")
    log_func("      2. Проверьте настройки прокси в Trae.\n")
    log_func("⚠️ Внимание: TUN обычно не влияет на hosts, но если прокси настроен внутри "
        "приложения, hosts всё равно может быть обойдён.")
