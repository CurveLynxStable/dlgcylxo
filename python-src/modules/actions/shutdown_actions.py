from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from modules.runtime.operation_result import OperationResult


@dataclass
class ShutdownState:
    shutdown_task_id: Any | None = None


@dataclass(frozen=True)
class ShutdownDeps:
    window: Any
    log: Callable[[str], None]
    thread_manager: Any
    stop_proxy_and_restore: Callable[..., OperationResult]
    proxy_runner: Any


def handle_window_close(
    *,
    deps: ShutdownDeps,
    state: ShutdownState,
) -> None:
    if state.shutdown_task_id:
        deps.log("⌛ Завершаем работу программы, подождите...")
        return

    deps.log("Завершаем работу программы, подождите...")

    def cleanup():
        try:
            deps.thread_manager.wait(deps.proxy_runner.proxy_start_task_id, timeout=5)
            deps.thread_manager.wait(deps.proxy_runner.proxy_stop_task_id, timeout=5)
            result = deps.stop_proxy_and_restore(block_hosts_cleanup=True)
            if result.ok:
                deps.log("Прокси-сервер остановлен, программа сейчас завершится")
        finally:
            state.shutdown_task_id = None
            deps.window.after(0, deps.window.destroy)

    state.shutdown_task_id = deps.thread_manager.run(
        "app_shutdown",
        cleanup,
        allow_parallel=False,
    )
