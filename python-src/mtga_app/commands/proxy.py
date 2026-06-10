from __future__ import annotations

import threading
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, Literal, cast

from pydantic import BaseModel
from pytauri import Commands

from modules.cert.ca_metadata import load_ca_info
from modules.network.network_environment import check_network_environment
from modules.runtime.log_bus import push_log as default_push_log
from modules.runtime.operation_result import OperationResult
from modules.runtime.proxy_status_bus import push_status as push_proxy_status
from modules.runtime.proxy_step_bus import push_step as push_proxy_step
from modules.runtime.resource_manager import ResourceManager
from modules.runtime.thread_manager import ThreadManager
from modules.services import proxy_orchestration
from modules.services.app_metadata import DEFAULT_METADATA
from modules.services.cert_service import (
    check_existing_ca_cert,
    clear_ca_cert_result,
    generate_certificates_result,
    install_ca_cert_result,
)
from modules.services.config_service import ConfigStore
from modules.services.hosts_service import modify_hosts_file_result
from modules.services.trae_native_route import (
    TraeNativeRouteConfig,
    TraeNativeRouteManager,
)
from modules.services.trae_official_base_url_route import (
    TraeOfficialBaseUrlRouteConfig,
    TraeOfficialBaseUrlRouteManager,
)

from .common import build_result_payload, collect_logs

type LogFunc = Callable[[str], None]

_proxy_status_poll_interval_seconds = 0.5
_proxy_status_watcher_start_lock = threading.Lock()
_proxy_status_payload_lock = threading.Lock()


@dataclass
class _ProxyStatusWatcherState:
    started: bool = False
    last_payload: str | None = None


_proxy_status_state = _ProxyStatusWatcherState()


class ProxyStartPayload(BaseModel):
    debug_mode: bool = False
    disable_ssl_strict_mode: bool = False
    force_stream: bool = False
    stream_mode: str | None = None
    proxy_mode: str | None = None
    trae_path: str | None = None


class ProxyStartStepEvent(BaseModel):
    step: Literal["cert", "hosts", "proxy"]
    status: Literal["ok", "skipped", "failed", "started"]
    message: str | None = None
    panel_target: Literal["model-routing", "settings"] | None = None


class ProxyRuntimeStatusEvent(BaseModel):
    running: bool
    active_mode: Literal["reverse_hosts", "trae_native", "trae_official_base_url"] | None = None
    loopback_port: int | None = None


@dataclass
class ProxyRuntimeState:
    thread_manager: ThreadManager
    proxy_instance: Any | None = None
    trae_route_manager: TraeNativeRouteManager | None = None
    trae_official_route_manager: TraeOfficialBaseUrlRouteManager | None = None


@lru_cache(maxsize=1)
def _get_resource_manager() -> ResourceManager:
    return ResourceManager()


@lru_cache(maxsize=1)
def _get_config_store() -> ConfigStore:
    resource_manager = _get_resource_manager()
    return ConfigStore(resource_manager.get_user_config_file())


@lru_cache(maxsize=1)
def _get_proxy_state() -> ProxyRuntimeState:
    return ProxyRuntimeState(thread_manager=ThreadManager())


def _get_trae_route_manager() -> TraeNativeRouteManager:
    state = _get_proxy_state()
    if state.trae_route_manager is None:
        state.trae_route_manager = TraeNativeRouteManager(
            thread_manager=state.thread_manager,
            resource_manager=_get_resource_manager(),
        )
    return state.trae_route_manager


def _get_trae_official_route_manager() -> TraeOfficialBaseUrlRouteManager:
    state = _get_proxy_state()
    if state.trae_official_route_manager is None:
        state.trae_official_route_manager = TraeOfficialBaseUrlRouteManager(
            thread_manager=state.thread_manager,
            resource_manager=_get_resource_manager(),
        )
    return state.trae_official_route_manager


def _set_proxy_instance(instance: Any | None) -> None:
    state = _get_proxy_state()
    state.proxy_instance = instance


def _get_proxy_instance() -> Any | None:
    return _get_proxy_state().proxy_instance


def _build_proxy_runtime_status() -> ProxyRuntimeStatusEvent:
    state = _get_proxy_state()

    trae_manager = state.trae_route_manager
    if trae_manager is not None and trae_manager.is_running():
        return ProxyRuntimeStatusEvent(
            running=True,
            active_mode="trae_native",
            loopback_port=trae_manager.current_loopback_port(),
        )

    trae_official_manager = state.trae_official_route_manager
    if trae_official_manager is not None and trae_official_manager.is_running():
        return ProxyRuntimeStatusEvent(
            running=True,
            active_mode="trae_official_base_url",
            loopback_port=trae_official_manager.current_loopback_port(),
        )

    instance = state.proxy_instance
    if instance is not None and instance.is_running():
        return ProxyRuntimeStatusEvent(running=True, active_mode="reverse_hosts")

    return ProxyRuntimeStatusEvent(running=False, active_mode=None)


def _publish_proxy_runtime_status(*, force: bool = False) -> ProxyRuntimeStatusEvent:
    status = _build_proxy_runtime_status()
    payload = status.model_dump_json()
    with _proxy_status_payload_lock:
        if force or payload != _proxy_status_state.last_payload:
            push_proxy_status(payload)
            _proxy_status_state.last_payload = payload
    return status


def _proxy_status_watch_loop() -> None:
    while True:
        with suppress(Exception):
            _publish_proxy_runtime_status()
        time.sleep(_proxy_status_poll_interval_seconds)


def ensure_proxy_status_watcher_started() -> None:
    with _proxy_status_watcher_start_lock:
        if _proxy_status_state.started:
            return
        _proxy_status_state.started = True
        _publish_proxy_runtime_status(force=True)
        watcher = threading.Thread(
            target=_proxy_status_watch_loop,
            name="proxy-status-watcher",
            daemon=True,
        )
        watcher.start()


def stop_proxy_for_shutdown(*, log_func: LogFunc | None = None) -> OperationResult:
    ensure_proxy_status_watcher_started()
    effective_log: LogFunc
    if log_func is None:
        def _default_log(message: str) -> None:
            default_push_log(message)

        effective_log = _default_log
    else:
        effective_log = log_func

    def _log(message: str) -> None:
        with suppress(Exception):
            effective_log(message)

    _log("Получен сигнал выхода, останавливаем прокси-сервер...")
    trae_result = _stop_all_trae_routes_result(log_func=_log)
    result = proxy_orchestration.stop_proxy_instance_result(
        get_proxy_instance=_get_proxy_instance,
        set_proxy_instance=_set_proxy_instance,
        log=_log,
        reason="shutdown",
        show_idle_message=True,
    )
    hosts_result = modify_hosts_file_result(action="remove", log_func=_log)
    if not hosts_result.ok:
        _log(f"⚠️ {hosts_result.message or 'Не удалось очистить записи hosts'}")
    if not trae_result.ok:
        _publish_proxy_runtime_status(force=True)
        return trae_result
    _publish_proxy_runtime_status(force=True)
    return result


def _stop_proxy_instance_result(
    *,
    log_func: LogFunc,
    reason: str = "stop",
    show_idle_message: bool = False,
) -> OperationResult:
    return proxy_orchestration.stop_proxy_instance_result(
        get_proxy_instance=_get_proxy_instance,
        set_proxy_instance=_set_proxy_instance,
        log=log_func,
        reason=reason,
        show_idle_message=show_idle_message,
    )


def _stop_trae_native_route_result(
    *,
    log_func: LogFunc,
    show_idle_message: bool = False,
) -> OperationResult:
    return _get_trae_route_manager().stop(
        log_func=log_func,
        show_idle_message=show_idle_message,
    )


def _stop_trae_official_route_result(
    *,
    log_func: LogFunc,
    show_idle_message: bool = False,
) -> OperationResult:
    return _get_trae_official_route_manager().stop(
        log_func=log_func,
        show_idle_message=show_idle_message,
    )


def _stop_all_trae_routes_result(
    *,
    log_func: LogFunc,
    show_idle_message: bool = False,
) -> OperationResult:
    native_result = _stop_trae_native_route_result(
        log_func=log_func,
        show_idle_message=False,
    )
    official_result = _stop_trae_official_route_result(
        log_func=log_func,
        show_idle_message=False,
    )
    if not native_result.ok:
        return native_result
    if not official_result.ok:
        return official_result
    if show_idle_message:
        log_func("Маршруты Trae остановлены")
    return OperationResult.success()


def _start_proxy_instance_result(
    config: dict[str, Any],
    *,
    log_func: LogFunc,
    success_message: str = "✅ Прокси-сервер успешно запущен",
    hosts_modified: bool = False,
) -> OperationResult:
    state = _get_proxy_state()
    return proxy_orchestration.start_proxy_instance_result(
        config=config,
        deps=proxy_orchestration.StartProxyDeps(
            log=log_func,
            thread_manager=state.thread_manager,
            check_network_environment=check_network_environment,
            set_proxy_instance=_set_proxy_instance,
            modify_hosts_file=_modify_hosts_file,
            network_env_precheck_enabled=False,
        ),
        success_message=success_message,
        hosts_modified=hosts_modified,
    )


def _restart_proxy_result(
    *,
    config: dict[str, Any],
    log_func: LogFunc,
    success_message: str = "✅ Прокси-сервер успешно запущен",
    hosts_modified: bool = False,
) -> OperationResult:
    def _stop(**kwargs: Any) -> OperationResult:
        return _stop_proxy_instance_result(log_func=log_func, **kwargs)

    def _start(cfg: dict[str, Any], **kwargs: Any) -> OperationResult:
        return _start_proxy_instance_result(cfg, log_func=log_func, **kwargs)

    return proxy_orchestration.restart_proxy_result(
        config=config,
        deps=proxy_orchestration.RestartProxyDeps(
            log=log_func,
            stop_proxy_instance=_stop,
            start_proxy_instance=_start,
        ),
        success_message=success_message,
        hosts_modified=hosts_modified,
    )


def _build_proxy_config(
    payload: ProxyStartPayload, *, log_func: LogFunc
) -> dict[str, Any] | None:
    config_store = _get_config_store()
    stream_mode = payload.stream_mode if payload.force_stream else None
    config = proxy_orchestration.build_model_routing_runtime_config(
        load_model_routing_config=config_store.load_model_routing_config,
        debug_mode=payload.debug_mode,
        disable_ssl_strict_mode=payload.disable_ssl_strict_mode,
        stream_mode=stream_mode,
    )
    if not config:
        log_func("❌ Ошибка: Маршрутизация моделей: нет доступных публикуемых моделей или целей")
        return None
    return config


def _resolve_proxy_mode(payload: ProxyStartPayload) -> str:
    if payload.proxy_mode == "trae_native":
        return "trae_native"
    if payload.proxy_mode == "trae_official_base_url":
        return "trae_official_base_url"
    if payload.proxy_mode == "reverse_hosts":
        return "reverse_hosts"
    config_store = _get_config_store()
    proxy_mode, _trae_path = config_store.load_proxy_settings()
    if proxy_mode == "trae_native":
        return "trae_native"
    if proxy_mode == "trae_official_base_url":
        return "trae_official_base_url"
    return "reverse_hosts"


def _resolve_trae_path(payload: ProxyStartPayload) -> str:
    if payload.trae_path is not None:
        return payload.trae_path.strip()
    config_store = _get_config_store()
    _proxy_mode, trae_path = config_store.load_proxy_settings()
    return trae_path.strip()


def _attach_route_mode(config: dict[str, Any], proxy_mode: str) -> dict[str, Any]:
    next_config = dict(config)
    next_config["route_mode"] = proxy_mode
    return next_config


def _build_proxy_config_silent(payload: ProxyStartPayload) -> dict[str, Any] | None:
    config_store = _get_config_store()
    stream_mode = payload.stream_mode if payload.force_stream else None
    return proxy_orchestration.build_model_routing_runtime_config(
        load_model_routing_config=config_store.load_model_routing_config,
        debug_mode=payload.debug_mode,
        disable_ssl_strict_mode=payload.disable_ssl_strict_mode,
        stream_mode=stream_mode,
    )


def _modify_hosts_file(*, log_func: LogFunc, **kwargs: Any) -> OperationResult:
    return modify_hosts_file_result(log_func=log_func, **kwargs)


def _push_proxy_step(
    log_func: LogFunc,
    *,
    step: Literal["cert", "hosts", "proxy"],
    status: Literal["ok", "skipped", "failed", "started"],
    message: str | None = None,
) -> None:
    panel_target: Literal["model-routing", "settings"] | None = None
    if status == "failed":
        normalized = (message or "").strip()
        if "Путь к Trae" in normalized or normalized.startswith("trae_path_"):
            panel_target = "settings"
        elif (
            "аршрутизаци" in normalized
            or "убликуем" in normalized
            or "цел" in normalized
        ):
            panel_target = "model-routing"

    if message:
        log_func(f"[proxy-step] step={step} status={status} message={message}")
    else:
        log_func(f"[proxy-step] step={step} status={status}")
    try:
        payload = ProxyStartStepEvent(
            step=step,
            status=status,
            message=message,
            panel_target=panel_target,
        )
        push_proxy_step(payload.model_dump_json())
    except Exception as exc:
        with suppress(Exception):
            log_func(f"⚠️ Не удалось записать событие proxy-step: {exc}")


def _decide_ca_action(
    check_result: OperationResult,
    *,
    log_func: LogFunc,
) -> tuple[str, str]:
    if not check_result.ok:
        log_func("⚠️ Проверка CA-сертификата не удалась, по правилам очищаем и генерируем новый "
            "сертификат")
        return "clear_and_generate", "Проверка CA-сертификата не удалась"

    match_count = check_result.details.get("match_count")
    if isinstance(match_count, int) and match_count > 1:
        return "clear_and_generate", "Обнаружено несколько подходящих сертификатов"

    installed_certs_obj = cast(object, check_result.details.get("certs") or [])
    installed_certs: list[dict[str, object]] = []
    if isinstance(installed_certs_obj, list):
        installed_certs_list = cast(list[object], installed_certs_obj)
        for item in installed_certs_list:
            if isinstance(item, dict):
                installed_certs.append(cast(dict[str, object], item))
    if not installed_certs:
        return "clear_and_generate", "Системный CA-сертификат не обнаружен"

    return _decide_ca_action_with_certs(installed_certs, log_func=log_func)


def _decide_ca_action_with_certs(
    installed_certs: list[dict[str, object]],
    *,
    log_func: LogFunc,
) -> tuple[str, str]:
    resource_manager = _get_resource_manager()
    ca_info = load_ca_info(resource_manager, log_func=log_func)
    if not ca_info:
        return "clear_and_generate", "Действительные метаданные CA не найдены"

    target_fingerprint = ca_info.get("fingerprint_sha1")
    matched_cert = next(
        (
            cert
            for cert in installed_certs
            if cert.get("fingerprint_sha1") == target_fingerprint
        ),
        None,
    )
    if not matched_cert:
        return "clear_and_generate", "Системный CA-сертификат не совпадает с локальной записью"

    not_after_unix = matched_cert.get("not_after_unix") or ca_info.get("not_after_unix")
    if not isinstance(not_after_unix, int):
        return "clear_and_generate", "Не удалось прочитать срок действия CA-сертификата"

    now_unix = int(datetime.now(UTC).timestamp())
    if not_after_unix <= now_unix:
        return "clear_and_generate", "Системный CA-сертификат истёк"

    return "skip", ""


def _proxy_start_all_precheck(
    body: ProxyStartPayload,
    log_func: LogFunc,
) -> tuple[OperationResult | None, dict[str, Any] | None]:
    config = _build_proxy_config(body, log_func=log_func)
    if not config:
        _push_proxy_step(
            log_func,
            step="proxy",
            status="failed",
            message="Маршрутизация моделей: нет доступных публикуемых моделей или целей",
        )
        return OperationResult.failure("model_routing_missing"), None

    return None, config


def _proxy_start_all_cert(log_func: LogFunc) -> OperationResult | None:
    _push_proxy_step(log_func, step="cert", status="started")
    def _generate_and_install() -> OperationResult | None:
        log_func("Шаг 1/4: генерация сертификатов")
        gen_result = generate_certificates_result(
            log_func=log_func,
            ca_common_name=DEFAULT_METADATA.ca_common_name,
        )
        if not gen_result.ok:
            _push_proxy_step(
                log_func,
                step="cert",
                status="failed",
                message=gen_result.message,
            )
            return gen_result

        log_func("Шаг 2/4: установка CA-сертификата")
        install_result = install_ca_cert_result(log_func=log_func)
        if not install_result.ok:
            _push_proxy_step(
                log_func,
                step="cert",
                status="failed",
                message=install_result.message,
            )
            return install_result

        _push_proxy_step(log_func, step="cert", status="ok")
        return None

    check_result = check_existing_ca_cert(
        DEFAULT_METADATA.ca_common_name,
        log_func=log_func,
    )
    action, reason = _decide_ca_action(check_result, log_func=log_func)

    if action == "skip":
        log_func(
            f"Обнаружен действующий системный CA-сертификат ({DEFAULT_METADATA.ca_common_name}), "
            "пропускаем генерацию и установку сертификатов"
        )
        _push_proxy_step(log_func, step="cert", status="skipped")
        return None

    if action == "clear_and_generate":
        log_func(f"{reason} — очищаем и генерируем заново")
        clear_result = clear_ca_cert_result(
            DEFAULT_METADATA.ca_common_name,
            log_func=log_func,
        )
        if not clear_result.ok:
            _push_proxy_step(
                log_func,
                step="cert",
                status="failed",
                message=clear_result.message,
            )
            return clear_result

    return _generate_and_install()


def _proxy_start_all_hosts(log_func: LogFunc) -> OperationResult | None:
    _push_proxy_step(log_func, step="hosts", status="started")
    log_func("Шаг 3/4: изменение файла hosts")
    hosts_result = modify_hosts_file_result(log_func=log_func)
    if not hosts_result.ok:
        _push_proxy_step(
            log_func,
            step="hosts",
            status="failed",
            message=hosts_result.message,
        )
        return hosts_result
    _push_proxy_step(log_func, step="hosts", status="ok")
    return None


def _proxy_start_all_proxy(config: dict[str, Any], log_func: LogFunc) -> OperationResult:
    _push_proxy_step(log_func, step="proxy", status="started")
    log_func("Шаг 4/4: запуск прокси-сервера")
    trae_stop_result = _stop_all_trae_routes_result(log_func=log_func)
    if not trae_stop_result.ok:
        _push_proxy_step(
            log_func,
            step="proxy",
            status="failed",
            message=trae_stop_result.message,
        )
        return trae_stop_result
    start_result = _restart_proxy_result(
        config=config,
        log_func=log_func,
        success_message="✅ Все сервисы успешно запущены",
        hosts_modified=True,
    )
    _push_proxy_step(
        log_func,
        step="proxy",
        status="ok" if start_result.ok else "failed",
        message=start_result.message,
    )
    return start_result


def _proxy_start_all_trae(
    body: ProxyStartPayload,
    config: dict[str, Any],
    log_func: LogFunc,
) -> OperationResult:
    _push_proxy_step(log_func, step="proxy", status="started")
    log_func("Маршрут Trae native: пропускаем сертификаты и hosts, запускаем локальный loopback + "
        "native rewriter")

    reverse_stop_result = _stop_proxy_instance_result(
        log_func=log_func,
        reason="restart",
        show_idle_message=False,
    )
    if not reverse_stop_result.ok:
        _push_proxy_step(
            log_func,
            step="proxy",
            status="failed",
            message=reverse_stop_result.message,
        )
        return reverse_stop_result

    official_stop_result = _stop_trae_official_route_result(log_func=log_func)
    if not official_stop_result.ok:
        _push_proxy_step(
            log_func,
            step="proxy",
            status="failed",
            message=official_stop_result.message,
        )
        return official_stop_result

    hosts_result = modify_hosts_file_result(action="remove", log_func=log_func)
    if not hosts_result.ok:
        log_func(f"⚠️ {hosts_result.message or 'Не удалось очистить записи hosts'}")

    trae_path = _resolve_trae_path(body)
    start_result = _get_trae_route_manager().start(
        TraeNativeRouteConfig(
            runtime_config=config,
            trae_path=trae_path,
            debug_mode=body.debug_mode,
            disable_ssl_strict_mode=body.disable_ssl_strict_mode,
        ),
        log_func=log_func,
    )
    _push_proxy_step(
        log_func,
        step="proxy",
        status="ok" if start_result.ok else "failed",
        message=start_result.message,
    )
    return start_result


def _proxy_start_all_trae_official_base_url(
    config: dict[str, Any],
    log_func: LogFunc,
) -> OperationResult:
    _push_proxy_step(log_func, step="proxy", status="started")
    log_func(
        "Маршрут официального base_url Trae: "
        "пропускаем сертификаты, hosts и patch, запускаем только локальный loopback"
    )

    reverse_stop_result = _stop_proxy_instance_result(
        log_func=log_func,
        reason="restart",
        show_idle_message=False,
    )
    if not reverse_stop_result.ok:
        _push_proxy_step(
            log_func,
            step="proxy",
            status="failed",
            message=reverse_stop_result.message,
        )
        return reverse_stop_result

    native_stop_result = _stop_trae_native_route_result(log_func=log_func)
    if not native_stop_result.ok:
        _push_proxy_step(
            log_func,
            step="proxy",
            status="failed",
            message=native_stop_result.message,
        )
        return native_stop_result

    hosts_result = modify_hosts_file_result(action="remove", log_func=log_func)
    if not hosts_result.ok:
        log_func(f"⚠️ {hosts_result.message or 'Не удалось очистить записи hosts'}")

    start_result = _get_trae_official_route_manager().start(
        TraeOfficialBaseUrlRouteConfig(runtime_config=config),
        log_func=log_func,
    )
    _push_proxy_step(
        log_func,
        step="proxy",
        status="ok" if start_result.ok else "failed",
        message=start_result.message,
    )
    return start_result


async def proxy_start(body: ProxyStartPayload) -> dict[str, Any]:
    ensure_proxy_status_watcher_started()
    logs, log_func = collect_logs()
    try:
        config = _build_proxy_config(body, log_func=log_func)
        if not config:
            _push_proxy_step(
                log_func,
                step="proxy",
                status="failed",
                message="Маршрутизация моделей: нет доступных публикуемых моделей или целей",
            )
            return build_result_payload(
                OperationResult.failure("model_routing_missing"),
                logs,
                "Не удалось запустить прокси-сервер",
            )

        proxy_mode = _resolve_proxy_mode(body)
        log_func(f"Текущий режим прокси: {proxy_mode}")
        config = _attach_route_mode(config, proxy_mode)
        if proxy_mode == "trae_native":
            result = _proxy_start_all_trae(body, config, log_func)
            return build_result_payload(result, logs, "Запуск прокси-сервера завершён")
        if proxy_mode == "trae_official_base_url":
            result = _proxy_start_all_trae_official_base_url(config, log_func)
            return build_result_payload(result, logs, "Запуск прокси-сервера завершён")

        trae_stop_result = _stop_all_trae_routes_result(log_func=log_func)
        if not trae_stop_result.ok:
            return build_result_payload(
                trae_stop_result, logs, "Не удалось запустить прокси-сервер"
            )

        result = _restart_proxy_result(
            config=config,
            log_func=log_func,
            success_message="✅ Прокси-сервер успешно запущен",
        )
        return build_result_payload(result, logs, "Запуск прокси-сервера завершён")
    finally:
        _publish_proxy_runtime_status(force=True)


async def proxy_runtime_status() -> dict[str, Any]:
    ensure_proxy_status_watcher_started()
    logs: list[str] = []
    status = _build_proxy_runtime_status()
    result = OperationResult.success(
        running=status.running,
        active_mode=status.active_mode,
        loopback_port=status.loopback_port,
    )
    return build_result_payload(result, logs, "Чтение состояния прокси завершено")


async def proxy_apply_current_config(body: ProxyStartPayload) -> dict[str, Any]:
    ensure_proxy_status_watcher_started()
    logs: list[str] = []
    config = _build_proxy_config_silent(body)
    if not config:
        return build_result_payload(
            OperationResult.failure("model_routing_missing"),
            logs,
            "Не удалось применить конфигурацию прокси",
        )

    trae_manager = _get_trae_route_manager()
    if trae_manager.is_running():
        result = trae_manager.apply_runtime_config(
            _attach_route_mode(config, "trae_native")
        )
        return build_result_payload(result, logs, "Применение конфигурации прокси завершено")

    trae_official_manager = _get_trae_official_route_manager()
    if trae_official_manager.is_running():
        result = trae_official_manager.apply_runtime_config(
            _attach_route_mode(config, "trae_official_base_url")
        )
        return build_result_payload(result, logs, "Применение конфигурации прокси завершено")

    instance = _get_proxy_instance()
    if not instance or not instance.is_running():
        return build_result_payload(
            OperationResult.success(
                "proxy_not_running",
                apply_status="deferred",
            ),
            logs,
            "Применение конфигурации прокси завершено",
        )

    result = instance.apply_runtime_config(_attach_route_mode(config, "reverse_hosts"))
    return build_result_payload(result, logs, "Применение конфигурации прокси завершено")


async def proxy_stop() -> dict[str, Any]:
    ensure_proxy_status_watcher_started()
    logs, log_func = collect_logs()
    trae_result = _stop_all_trae_routes_result(
        log_func=log_func,
    )
    result = proxy_orchestration.stop_proxy_instance_result(
        get_proxy_instance=_get_proxy_instance,
        set_proxy_instance=_set_proxy_instance,
        log=log_func,
        show_idle_message=True,
    )
    hosts_result = modify_hosts_file_result(action="remove", log_func=log_func)
    if not hosts_result.ok:
        log_func(f"⚠️ {hosts_result.message or 'Не удалось очистить записи hosts'}")
    if not trae_result.ok:
        result = trae_result
    _publish_proxy_runtime_status(force=True)
    return build_result_payload(result, logs, "Остановка прокси-сервера завершена")


async def proxy_check_network() -> dict[str, Any]:
    ensure_proxy_status_watcher_started()
    logs, log_func = collect_logs()
    report = check_network_environment(log_func=log_func, emit_logs=True)
    if not report.explicit_proxy_detected:
        log_func("✅ Явная настройка прокси на уровне системы/переменных окружения не обнаружена.")
        log_func(
            "ℹ️ Если подключения по-прежнему нет, проверьте настройки прокси в Trae "
            "или включённые TUN/VPN/средства сетевой защиты."
        )
    result = OperationResult.success(report=report)
    return build_result_payload(result, logs, "Проверка сетевого окружения завершена")


async def proxy_start_all(body: ProxyStartPayload) -> dict[str, Any]:
    ensure_proxy_status_watcher_started()
    logs, log_func = collect_logs()
    result: OperationResult | None
    summary = "Запуск одной кнопкой не удался"
    try:
        result, config = _proxy_start_all_precheck(body, log_func)
        if result is None and config is not None:
            log_func("=== Запуск всех сервисов одной кнопкой ===")
            proxy_mode = _resolve_proxy_mode(body)
            log_func(f"Текущий режим прокси: {proxy_mode}")
            config = _attach_route_mode(config, proxy_mode)
            if proxy_mode == "trae_native":
                result = _proxy_start_all_trae(body, config, log_func)
            elif proxy_mode == "trae_official_base_url":
                result = _proxy_start_all_trae_official_base_url(config, log_func)
            else:
                result = _proxy_start_all_cert(log_func)
        if result is None:
            result = _proxy_start_all_hosts(log_func)
        if result is None and config is not None:
            result = _proxy_start_all_proxy(config, log_func)
            summary = "Запуск одной кнопкой завершён"
        elif result is not None and result.ok:
            summary = "Запуск одной кнопкой завершён"
    except Exception as exc:
        with suppress(Exception):
            log_func(f"⚠️ Исключение при запуске одной кнопкой: {exc}")
        message = str(exc) or "Исключение при запуске одной кнопкой"
        _push_proxy_step(
            log_func,
            step="proxy",
            status="failed",
            message=message,
        )
        result = OperationResult.failure("Исключение при запуске одной кнопкой")

    if result is None:
        result = OperationResult.failure("Запуск одной кнопкой не удался")
    _publish_proxy_runtime_status(force=True)
    return build_result_payload(result, logs, summary)


def register_proxy_commands(commands: Commands) -> None:
    ensure_proxy_status_watcher_started()
    commands.set_command("proxy_start", proxy_start)
    commands.set_command("proxy_runtime_status", proxy_runtime_status)
    commands.set_command("proxy_apply_current_config", proxy_apply_current_config)
    commands.set_command("proxy_stop", proxy_stop)
    commands.set_command("proxy_check_network", proxy_check_network)
    commands.set_command("proxy_start_all", proxy_start_all)
