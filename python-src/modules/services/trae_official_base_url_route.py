from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from modules.runtime.error_codes import ErrorCode
from modules.runtime.operation_result import OperationResult
from modules.runtime.resource_manager import ResourceManager
from modules.runtime.thread_manager import ThreadManager
from modules.services.trae_loopback import (
    DEFAULT_TRAE_LOOPBACK_HOST,
    DEFAULT_TRAE_LOOPBACK_PORT,
    TraeLoopbackConfig,
    TraeLoopbackManager,
)

type LogFunc = Callable[[str], None]


@dataclass(frozen=True)
class TraeOfficialBaseUrlRouteConfig:
    runtime_config: dict[str, Any]
    loopback_host: str = DEFAULT_TRAE_LOOPBACK_HOST
    loopback_port: int = DEFAULT_TRAE_LOOPBACK_PORT


class TraeOfficialBaseUrlRouteManager:
    def __init__(
        self,
        *,
        thread_manager: ThreadManager,
        resource_manager: ResourceManager,
    ) -> None:
        self._loopback = TraeLoopbackManager(
            thread_manager=thread_manager,
            resource_manager=resource_manager,
        )
        self._running = False
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        with self._lock:
            if self._running and not self._loopback.is_running():
                self._running = False
            return self._running

    def current_loopback_port(self) -> int | None:
        return self._loopback.current_selected_port()

    def apply_runtime_config(self, raw_config: dict[str, Any] | None) -> OperationResult:
        with self._lock:
            if self._running and not self._loopback.is_running():
                self._running = False
            if not self._running:
                return OperationResult.failure("Маршрут официального base_url Trae не запущен")
        return self._loopback.apply_runtime_config(raw_config)

    def start(
        self,
        config: TraeOfficialBaseUrlRouteConfig,
        *,
        log_func: LogFunc,
    ) -> OperationResult:
        with self._lock:
            stop_result = self._stop_locked(log_func=log_func, show_idle_message=False)
            if not stop_result.ok:
                return stop_result

            log_func(
                "Маршрут официального base_url Trae: "
                "запускаем только локальный custom model loopback, без запуска Trae и без patch"
            )
            loopback_result = self._loopback.start(
                TraeLoopbackConfig(
                    runtime_config=config.runtime_config,
                    loopback_host=config.loopback_host,
                    loopback_port=config.loopback_port,
                ),
                log_func=log_func,
                task_name="trae_official_base_url_loopback",
            )
            if not loopback_result.ok:
                return loopback_result

            self._running = True
            api_base_url = str(loopback_result.details.get("base_url") or "")
            loopback_url = str(loopback_result.details.get("loopback_url") or "")
            selected_port = loopback_result.details.get("selected_port")
            log_func(f"Укажите этот base_url для пользовательской модели в Trae: {api_base_url}")
            if loopback_result.details.get("port_shifted") is True:
                log_func(
                    "⚠️ Маршрут официального base_url Trae: порт был смещён: "
                    f"preferred={config.loopback_port} selected={selected_port}"
                )
            log_func("✅ Маршрут официального base_url Trae готов")
            return OperationResult.success(
                "Маршрут официального base_url Trae готов",
                base_url=api_base_url,
                loopback_url=loopback_url,
                preferred_port=config.loopback_port,
                selected_port=selected_port,
                port_shifted=loopback_result.details.get("port_shifted"),
            )

    def stop(
        self,
        *,
        log_func: LogFunc,
        show_idle_message: bool = False,
    ) -> OperationResult:
        with self._lock:
            return self._stop_locked(
                log_func=log_func,
                show_idle_message=show_idle_message,
            )

    def _stop_locked(
        self,
        *,
        log_func: LogFunc,
        show_idle_message: bool,
    ) -> OperationResult:
        had_runtime = self._running or self._loopback.is_running()
        if not had_runtime:
            if show_idle_message:
                log_func("Маршрут официального base_url Trae не запущен")
            return OperationResult.success()

        log_func("Останавливаем маршрут официального base_url Trae...")
        clean = self._loopback.stop()
        self._running = False
        log_func("Маршрут официального base_url Trae остановлен")
        if clean:
            return OperationResult.success()
        return OperationResult.failure(
            "Маршрут официального base_url Trae остановлен не полностью",
            code=ErrorCode.UNKNOWN,
        )
