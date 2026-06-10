from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from modules.network.network_utils import is_port_in_use
from modules.proxy.model_routing import build_model_routing_config
from modules.proxy.proxy_server import ProxyServer
from modules.runtime.error_codes import ErrorCode
from modules.runtime.operation_result import OperationResult


@dataclass(frozen=True)
class RestartProxyDeps:
    log: Callable[[str], None]
    stop_proxy_instance: Callable[..., OperationResult]
    start_proxy_instance: Callable[..., OperationResult]


@dataclass(frozen=True)
class StartProxyDeps:
    log: Callable[[str], None]
    thread_manager: Any
    check_network_environment: Callable[..., Any]
    set_proxy_instance: Callable[[Any | None], None]
    modify_hosts_file: Callable[..., OperationResult]
    network_env_precheck_enabled: bool


@dataclass(frozen=True)
class GlobalConfigCheckResult:
    ok: bool
    missing_fields: list[str]


def ensure_global_config_ready(
    *,
    load_global_config: Callable[[], tuple[str, str]],
) -> GlobalConfigCheckResult:
    mapped_model_id, mtga_auth_key = load_global_config()
    mapped_model_id = (mapped_model_id or "").strip()
    mtga_auth_key = (mtga_auth_key or "").strip()

    missing_fields: list[str] = []
    if not mapped_model_id:
        missing_fields.append("ID сопоставленной модели")

    return GlobalConfigCheckResult(ok=not missing_fields, missing_fields=missing_fields)


def build_proxy_config(
    *,
    get_current_config: Callable[[], dict[str, Any]],
    debug_mode: bool,
    disable_ssl_strict_mode: bool,
    stream_mode: str | None,
) -> dict[str, Any] | None:
    current_config = get_current_config()
    if not current_config:
        return None
    config = current_config.copy()
    config["debug_mode"] = debug_mode
    config["disable_ssl_strict_mode"] = disable_ssl_strict_mode
    config["stream_mode"] = stream_mode
    return config


def build_model_routing_runtime_config(
    *,
    load_model_routing_config: Callable[[], dict[str, Any]],
    debug_mode: bool,
    disable_ssl_strict_mode: bool,
    stream_mode: str | None,
) -> dict[str, Any] | None:
    routing_config = build_model_routing_config(load_model_routing_config())
    if not routing_config.targets or not routing_config.enabled_published_models():
        return None
    return {
        "model_routing": routing_config,
        "debug_mode": debug_mode,
        "disable_ssl_strict_mode": disable_ssl_strict_mode,
        "stream_mode": stream_mode,
    }


def restart_proxy_result(
    *,
    config: dict[str, Any],
    deps: RestartProxyDeps,
    success_message: str = "✅ Прокси-сервер успешно запущен",
    hosts_modified: bool = False,
) -> OperationResult:
    stream_mode_value = config.get("stream_mode")
    if stream_mode_value is not None:
        deps.log(f"Включён принудительный потоковый режим: {stream_mode_value}")
    stop_result = deps.stop_proxy_instance(reason="restart")
    if not stop_result.ok:
        message = stop_result.message or "Не удалось остановить старый экземпляр прокси"
        deps.log(f"❌ {message}, перезапуск отменён")
        return OperationResult.failure(message, code=stop_result.code)
    start_result = deps.start_proxy_instance(
        config,
        success_message=success_message,
        hosts_modified=hosts_modified,
    )
    if start_result.ok:
        return OperationResult.success()
    return OperationResult.failure(
        start_result.message or "Не удалось запустить прокси-сервер",
        code=start_result.code,
    )


def restart_proxy(
    *,
    config: dict[str, Any],
    deps: RestartProxyDeps,
    success_message: str = "✅ Прокси-сервер успешно запущен",
    hosts_modified: bool = False,
) -> bool:
    return restart_proxy_result(
        config=config,
        deps=deps,
        success_message=success_message,
        hosts_modified=hosts_modified,
    ).ok


def stop_proxy_instance_result(
    *,
    get_proxy_instance: Callable[[], Any | None],
    set_proxy_instance: Callable[[Any | None], None],
    log: Callable[[str], None],
    reason: str = "stop",
    show_idle_message: bool = False,
) -> OperationResult:
    instance = get_proxy_instance()
    if instance:
        if reason == "restart":
            if instance.is_running():
                log("Обнаружен работающий прокси-сервер, останавливаем старый экземпляр...")
            else:
                log("Обнаружен оставшийся экземпляр прокси, пытаемся очистить...")
        else:
            log("Останавливаем прокси-сервер...")
        stop_result = _stop_instance_result(instance=instance, log=log)
        if stop_result.ok:
            set_proxy_instance(None)
        return stop_result
    if show_idle_message:
        log("Прокси-сервер не запущен")
    return OperationResult.success()


def _stop_instance_result(
    *,
    instance: Any,
    log: Callable[[str], None],
) -> OperationResult:
    try:
        raw_stop_result = instance.stop()
    except Exception as exc:  # noqa: BLE001
        log(f"Ошибка при остановке прокси-сервера: {exc}")
        return OperationResult.failure("Ошибка при остановке прокси-сервера")

    if not isinstance(raw_stop_result, OperationResult):
        return OperationResult.failure("Остановка прокси-сервера вернула некорректный результат")

    if raw_stop_result.ok:
        log("✅ Прокси-сервер остановлен")
    else:
        log(f"⚠️ {raw_stop_result.message or 'Прокси-сервер остановлен не полностью'}")
    return raw_stop_result


def stop_proxy_instance(
    *,
    get_proxy_instance: Callable[[], Any | None],
    set_proxy_instance: Callable[[Any | None], None],
    log: Callable[[str], None],
    reason: str = "stop",
    show_idle_message: bool = False,
) -> bool:
    return stop_proxy_instance_result(
        get_proxy_instance=get_proxy_instance,
        set_proxy_instance=set_proxy_instance,
        log=log,
        reason=reason,
        show_idle_message=show_idle_message,
    ).ok


def start_proxy_instance_result(
    *,
    config: dict[str, Any],
    deps: StartProxyDeps,
    success_message: str = "✅ Прокси-сервер успешно запущен",
    hosts_modified: bool = False,
) -> OperationResult:
    if deps.network_env_precheck_enabled:
        deps.check_network_environment(log_func=deps.log, emit_logs=True)

    if is_port_in_use(443):
        deps.log("⚠️ Порт 443 занят другим процессом, прокси-сервер не запущен. Освободите порт и "
            "повторите попытку.")
        return OperationResult.failure("Порт уже занят", code=ErrorCode.PORT_IN_USE)

    if not hosts_modified:
        deps.log("Изменяем файл hosts...")
        modify_result = deps.modify_hosts_file(log_func=deps.log)
        if not modify_result.ok:
            deps.log("❌ Не удалось изменить файл hosts, прокси-сервер не запущен")
            return OperationResult.failure(
                modify_result.message or "Не удалось изменить файл hosts",
                code=modify_result.code,
            )
    deps.log("Начинаем запуск прокси-сервера...")
    instance = ProxyServer(config, log_func=deps.log, thread_manager=deps.thread_manager)
    deps.set_proxy_instance(instance)
    if instance.start():
        deps.log(success_message)
        return OperationResult.success()
    deps.log("❌ Не удалось запустить прокси-сервер")
    deps.set_proxy_instance(None)
    return OperationResult.failure("Не удалось запустить прокси-сервер", code=ErrorCode.UNKNOWN)


def start_proxy_instance(
    *,
    config: dict[str, Any],
    deps: StartProxyDeps,
    success_message: str = "✅ Прокси-сервер успешно запущен",
    hosts_modified: bool = False,
) -> bool:
    return start_proxy_instance_result(
        config=config,
        deps=deps,
        success_message=success_message,
        hosts_modified=hosts_modified,
    ).ok
