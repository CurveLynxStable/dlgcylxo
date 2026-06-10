from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from modules.runtime.operation_result import OperationResult
from modules.runtime.result_messages import describe_result
from modules.runtime.thread_manager import ThreadManager


@dataclass(frozen=True)
class ProxyTaskDependencies:
    ensure_global_config_ready: Callable[[], bool]
    build_proxy_config: Callable[[], dict[str, Any] | None]
    get_current_config: Callable[[], dict[str, Any]]
    restart_proxy: Callable[..., OperationResult]
    stop_proxy_and_restore: Callable[..., OperationResult]
    has_existing_ca_cert: Callable[..., bool]
    generate_certificates: Callable[..., bool]
    install_ca_cert: Callable[..., bool]
    modify_hosts_file: Callable[..., OperationResult]
    ca_common_name: str


class ProxyTaskRunner:
    def __init__(
        self,
        *,
        log_func: Callable[[str], None],
        thread_manager: ThreadManager,
        deps: ProxyTaskDependencies,
    ) -> None:
        self._log = log_func
        self._thread_manager = thread_manager
        self._deps = deps
        self.proxy_start_task_id = None
        self.proxy_stop_task_id = None

    def start_proxy(self) -> str | None:
        if not self._deps.ensure_global_config_ready():
            return None

        def task() -> None:
            config = self._deps.build_proxy_config()
            if not config:
                return
            self._deps.restart_proxy(config)

        wait_targets = [self.proxy_stop_task_id] if self.proxy_stop_task_id else None
        self.proxy_start_task_id = self._thread_manager.run(
            "proxy_start",
            task,
            wait_for=wait_targets,
        )
        return self.proxy_start_task_id

    def stop_proxy(self) -> str | None:
        def task() -> None:
            self._deps.stop_proxy_and_restore(show_idle_message=True)

        wait_targets = [self.proxy_start_task_id] if self.proxy_start_task_id else None
        self.proxy_stop_task_id = self._thread_manager.run(
            "proxy_stop",
            task,
            wait_for=wait_targets,
        )
        return self.proxy_stop_task_id

    def start_all(self) -> str | None:
        if not self._deps.ensure_global_config_ready():
            return None

        def task() -> None:
            self._thread_manager.wait(self.proxy_start_task_id)
            self._thread_manager.wait(self.proxy_stop_task_id)

            current_config = self._deps.get_current_config()
            if not current_config:
                self._log("❌ Ошибка: Нет доступных групп конфигурации")
                return

            self._log("=== Запуск всех сервисов одной кнопкой ===")

            self._log("Шаг 1/4: генерация сертификатов")
            has_existing_ca = self._deps.has_existing_ca_cert(
                self._deps.ca_common_name,
                log_func=self._log,
            )
            if has_existing_ca:
                self._log(
                    
                        f"Обнаружен существующий системный CA-сертификат "
                        f"({self._deps.ca_common_name}), пропускаем генерацию и установку "
                        f"сертификатов"
                    
                )
                self._log("ℹ️ При необходимости выполните генерацию и установку вручную")
                self._log("Шаг 2/4: установка CA-сертификата (пропущено)")
            else:
                if not self._deps.generate_certificates(
                    log_func=self._log,
                    ca_common_name=self._deps.ca_common_name,
                ):
                    self._log("❌ Не удалось сгенерировать сертификаты, продолжение невозможно")
                    return

                self._log("Шаг 2/4: установка CA-сертификата")
                if not self._deps.install_ca_cert(log_func=self._log):
                    self._log("❌ Не удалось установить CA-сертификат, продолжение невозможно")
                    return

            self._log("Шаг 3/4: изменение файла hosts")
            modify_result = self._deps.modify_hosts_file(log_func=self._log)
            if not modify_result.ok:
                message = describe_result(modify_result, "Не удалось изменить файл hosts, "
                    "продолжение невозможно")
                self._log(f"❌ {message}")
                return

            self._log("Шаг 4/4: запуск прокси-сервера")
            config = self._deps.build_proxy_config()
            if not config:
                return
            restart_result = self._deps.restart_proxy(
                config,
                success_message="✅ Все сервисы успешно запущены",
                hosts_modified=modify_result.ok,
            )
            if restart_result.ok:
                return
            self._log("❌ Не удалось запустить все сервисы: прокси-сервер не запустился")

        return self._thread_manager.run("start_all", task)
