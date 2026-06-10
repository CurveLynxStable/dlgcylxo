import { useMtgaApi } from "./useMtgaApi";
import { listen } from "@tauri-apps/api/event";
import { isBundledRuntime, isTauriRuntime } from "./runtime";
import type {
  AppInfo,
  ConfigPayload,
  FailoverPool,
  InvokeResult,
  LogEventPayload,
  LogPullResult,
  MainTabKey,
  ModelRoutingTarget,
  PublishedModel,
  ProxyMode,
  ProxyRuntimeStatusPayload,
  ProxyStartStepEvent,
  ProxyTrace,
  ProxyTraceSummary,
  SystemPromptItem,
  TargetModelsResult,
} from "./mtgaTypes";

type RuntimeOptions = {
  debugMode: boolean;
  disableSslStrict: boolean;
  forceStream: boolean;
  streamMode: "true" | "false";
};

type PanelTarget = "model-routing" | "main-tabs" | "proxy-logs" | "system-prompts" | "settings";

const DEFAULT_APP_INFO: AppInfo = {
  display_name: "MTGA",
  version: "v0.0.0",
  github_repo: "",
  ca_common_name: "MTGA_CA",
  api_key_visible_chars: 4,
  user_data_dir: "",
  default_user_data_dir: "",
};

const DEFAULT_RUNTIME_OPTIONS: RuntimeOptions = {
  debugMode: false,
  disableSslStrict: false,
  forceStream: false,
  streamMode: "true",
};

const DEFAULT_PROXY_MODE: ProxyMode = "trae_official_base_url";
const DEFAULT_TRAE_PATH = "";
const DEFAULT_MINIMIZE_TO_TRAY_ON_CLOSE = false;
const WINDOWS_TRAE_DIALOG_PATH = "%LOCALAPPDATA%\\Programs\\Trae\\Trae.exe";
const MACOS_TRAE_DIALOG_PATH = "/Applications/Trae.app";

const FRONTEND_LOG_LIMIT = 2000;
const PROXY_REQUEST_LOG_PATTERN = /^\d{2}:\d{2}:\d{2}\.\d{3} \[[0-9a-f]{6}\] /;
const PROXY_REQUEST_SUMMARY_MARKERS = [
  "Получен запрос Chat Completions",
  "Возвращён потоковый ответ",
  "Возвращён непотоковый JSON-ответ",
  "Прокси-сервис не готов",
  "Не удалось разобрать JSON",
  "Ошибка авторизации",
  "Ответ апстрима не является JSON-объектом",
  "HTTP-ошибка целевого API",
  "Ошибка при подключении к целевому API",
  "Произошла непредвиденная ошибка",
];
const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const isMainTabKey = (value: unknown): value is MainTabKey =>
  value === "cert" || value === "hosts" || value === "proxy";

const isProxyStepStatus = (value: unknown): value is ProxyStartStepEvent["status"] =>
  value === "ok" || value === "skipped" || value === "failed" || value === "started";

const isPanelTarget = (value: unknown): value is PanelTarget =>
  value === "model-routing" ||
  value === "main-tabs" ||
  value === "proxy-logs" ||
  value === "system-prompts" ||
  value === "settings";

const isProxyStartStepEvent = (value: unknown): value is ProxyStartStepEvent => {
  if (!isRecord(value)) {
    return false;
  }
  return isMainTabKey(value.step) && isProxyStepStatus(value.status);
};

const isProxyMode = (value: unknown): value is ProxyMode =>
  value === "reverse_hosts" || value === "trae_native" || value === "trae_official_base_url";

const normalizeOptionalPort = (value: unknown): number | null => {
  if (typeof value === "undefined" || value === null || value === "") {
    return null;
  }
  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    return null;
  }
  return port;
};

const isProxyRuntimeStatusPayload = (value: unknown): value is ProxyRuntimeStatusPayload => {
  if (!isRecord(value) || typeof value.running !== "boolean") {
    return false;
  }
  const activeMode = value.active_mode;
  const loopbackPort = normalizeOptionalPort(value.loopback_port);
  if (activeMode !== null && typeof activeMode !== "undefined" && !isProxyMode(activeMode)) {
    return false;
  }
  return (
    typeof value.loopback_port === "undefined" ||
    value.loopback_port === null ||
    loopbackPort !== null
  );
};

const normalizeProxyStepPayload = (payload: unknown): ProxyStartStepEvent | null => {
  if (isProxyStartStepEvent(payload)) {
    return payload;
  }
  if (typeof payload === "string") {
    try {
      const parsed = JSON.parse(payload);
      if (isProxyStartStepEvent(parsed)) {
        return parsed;
      }
    } catch {
      return null;
    }
  }
  return null;
};

const normalizeProxyRuntimeStatusPayload = (payload: unknown): ProxyRuntimeStatusPayload | null => {
  if (isProxyRuntimeStatusPayload(payload)) {
    return {
      running: payload.running,
      active_mode: payload.active_mode ?? null,
      loopback_port: normalizeOptionalPort(payload.loopback_port),
    };
  }
  if (typeof payload === "string") {
    try {
      const parsed = JSON.parse(payload);
      if (isProxyRuntimeStatusPayload(parsed)) {
        return {
          running: parsed.running,
          active_mode: parsed.active_mode ?? null,
          loopback_port: normalizeOptionalPort(parsed.loopback_port),
        };
      }
    } catch {
      return null;
    }
  }
  return null;
};

const coerceText = (value: unknown) => {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number") {
    return String(value);
  }
  if (isRecord(value)) {
    const candidates = [value["id"], value["value"], value["model_id"]];
    for (const candidate of candidates) {
      if (typeof candidate === "string") {
        return candidate;
      }
    }
  }
  return "";
};

const formatUnknownError = (error: unknown) => {
  if (error instanceof Error) {
    return error.message.trim();
  }
  if (typeof error === "string") {
    return error.trim();
  }
  if (isRecord(error)) {
    try {
      return JSON.stringify(error);
    } catch {
      return "";
    }
  }
  return "";
};

const shouldKeepRuntimeLog = (message: string) => {
  if (!PROXY_REQUEST_LOG_PATTERN.test(message)) {
    return true;
  }
  return PROXY_REQUEST_SUMMARY_MARKERS.some((marker) => message.includes(marker));
};

const getDefaultTraeDialogPath = () => {
  if (typeof navigator !== "undefined" && /Mac/i.test(navigator.platform)) {
    return MACOS_TRAE_DIALOG_PATH;
  }
  return WINDOWS_TRAE_DIALOG_PATH;
};

const normalizeModelList = (value: unknown) => {
  if (!Array.isArray(value)) {
    return [];
  }
  const unique = new Set<string>();
  value.forEach((item) => {
    const text = coerceText(item).trim();
    if (text) {
      unique.add(text);
    }
  });
  return Array.from(unique).sort((a, b) => a.localeCompare(b));
};

const normalizeRequestBodyPatch = (value: unknown): Record<string, unknown>[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isRecord).map((operation) => ({ ...operation }));
};

const normalizeProvider = (value: unknown): ModelRoutingTarget["provider"] => {
  if (
    value === "openai_chat_completion" ||
    value === "openai_response" ||
    value === "anthropic" ||
    value === "gemini"
  ) {
    return value;
  }
  return "openai_chat_completion";
};

const normalizeTextList = (value: unknown) => {
  const rawItems = Array.isArray(value) ? value : [value];
  const unique = new Set<string>();
  rawItems.forEach((item) => {
    const text = coerceText(item).trim();
    if (text) {
      unique.add(text);
    }
  });
  return Array.from(unique);
};

const normalizeTargetId = (value: unknown, index: number, used: Set<string>) => {
  const base = coerceText(value).trim() || `target-${index + 1}`;
  let candidate = base;
  let suffix = 2;
  while (used.has(candidate)) {
    candidate = `${base}-${suffix}`;
    suffix += 1;
  }
  used.add(candidate);
  return candidate;
};

const normalizeTargets = (value: unknown): ModelRoutingTarget[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  const used = new Set<string>();
  return value
    .filter(isRecord)
    .map((item, index) => {
      const apiBase = coerceText(item.api_base ?? item.api_url)
        .trim()
        .replace(/\/+$/, "");
      let upstreamModels = normalizeTextList(item.upstream_models);
      if (!upstreamModels.length) {
        upstreamModels = normalizeTextList(item.upstream_model ?? item.model_id);
      }
      if (!apiBase || !upstreamModels.length) {
        return null;
      }
      const target: ModelRoutingTarget = {
        id: normalizeTargetId(item.id, index, used),
        display_name: coerceText(item.display_name ?? item.name).trim(),
        provider: normalizeProvider(item.provider),
        api_base: apiBase,
        upstream_models: upstreamModels,
        upstream_model: upstreamModels[0] || "",
        api_key: coerceText(item.api_key).trim(),
        middle_route: coerceText(item.middle_route).trim(),
        prompt_cache_enabled: item.prompt_cache_enabled === true,
      };
      const strategy = coerceText(item.model_discovery_strategy).trim();
      if (strategy) {
        target.model_discovery_strategy = strategy;
      }
      const requestBodyPatch = normalizeRequestBodyPatch(item.request_body_patch);
      if (requestBodyPatch.length) {
        target.request_body_patch = requestBodyPatch;
      }
      return target;
    })
    .filter((item): item is ModelRoutingTarget => item !== null);
};

const normalizeFailoverPools = (value: unknown, targets: ModelRoutingTarget[]): FailoverPool[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  const targetById = new Map(targets.map((target) => [target.id, target]));
  const usedPoolIds = new Set<string>();
  return value.filter(isRecord).map((item, index) => {
    const idBase = coerceText(item.id).trim() || `failover-pool-${index + 1}`;
    let id = idBase;
    let suffix = 2;
    while (usedPoolIds.has(id)) {
      id = `${idBase}-${suffix}`;
      suffix += 1;
    }
    usedPoolIds.add(id);
    const statuses = Array.isArray(item.trigger_statuses)
      ? item.trigger_statuses
          .map((status) => Number(status))
          .filter((status) => Number.isInteger(status) && status > 0)
      : [429];
    const memberItems = Array.isArray(item.members) ? item.members : [];
    const seenMembers = new Set<string>();
    const members = memberItems
      .map((member) => {
        const targetId = isRecord(member)
          ? coerceText(member.target_id).trim()
          : coerceText(member).trim();
        const target = targetById.get(targetId);
        const upstreamModel = isRecord(member)
          ? coerceText(member.upstream_model).trim() || target?.upstream_model || ""
          : target?.upstream_model || "";
        return { target_id: targetId, upstream_model: upstreamModel };
      })
      .filter((member) => {
        const target = targetById.get(member.target_id);
        const memberKey = `${member.target_id}\u0000${member.upstream_model}`;
        if (
          !target ||
          !member.upstream_model ||
          !target.upstream_models.includes(member.upstream_model) ||
          seenMembers.has(memberKey)
        ) {
          return false;
        }
        seenMembers.add(memberKey);
        return true;
      });
    const cooldownSeconds = Number(item.cooldown_seconds);
    return {
      id,
      trigger_statuses: statuses.length ? Array.from(new Set(statuses)) : [429],
      cooldown_seconds:
        Number.isInteger(cooldownSeconds) && cooldownSeconds > 0 ? cooldownSeconds : 10,
      members,
    };
  });
};

const normalizePublishedModels = (
  value: unknown,
  targets: ModelRoutingTarget[],
  pools: FailoverPool[],
): PublishedModel[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  const targetById = new Map(targets.map((target) => [target.id, target]));
  const poolIds = new Set(pools.map((pool) => pool.id));
  const usedNames = new Set<string>();
  return value
    .filter(isRecord)
    .map((item): PublishedModel | null => {
      const name = coerceText(item.name).trim();
      const primaryTargetId = coerceText(item.primary_target_id).trim();
      const primaryTarget = targetById.get(primaryTargetId);
      const primaryUpstreamModel =
        coerceText(item.primary_upstream_model).trim() || primaryTarget?.upstream_model || "";
      if (
        !name ||
        usedNames.has(name) ||
        !primaryTarget ||
        !primaryUpstreamModel ||
        !primaryTarget.upstream_models.includes(primaryUpstreamModel)
      ) {
        return null;
      }
      usedNames.add(name);
      const failoverPoolId = coerceText(item.failover_pool_id).trim();
      return {
        name,
        enabled: item.enabled !== false,
        primary_target_id: primaryTargetId,
        primary_upstream_model: primaryUpstreamModel,
        failover_pool_id: failoverPoolId && poolIds.has(failoverPoolId) ? failoverPoolId : null,
      };
    })
    .filter((item): item is PublishedModel => item !== null);
};

const normalizeSystemPromptList = (value: unknown): SystemPromptItem[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  const normalized: SystemPromptItem[] = [];
  value.forEach((item) => {
    if (!isRecord(item)) {
      return;
    }
    const hash = coerceText(item["hash"]).trim();
    const originalText = coerceText(item["original_text"]);
    const createdAt = coerceText(item["created_at"]);
    if (!hash || !createdAt) {
      return;
    }

    const nextItem: SystemPromptItem = {
      hash,
      original_text: originalText,
      created_at: createdAt,
    };

    const latestDeltaRaw = item["latest_delta"];
    if (isRecord(latestDeltaRaw)) {
      const editedAt = coerceText(latestDeltaRaw["edited_at"]);
      const editor = coerceText(latestDeltaRaw["editor"]);
      const nextDelta: SystemPromptDelta = {
        edited_at: editedAt,
        ...(editor ? { editor } : {}),
      };
      const hasEditedText = Object.prototype.hasOwnProperty.call(latestDeltaRaw, "edited_text");
      const editedTextRaw = latestDeltaRaw["edited_text"];
      if (hasEditedText && typeof editedTextRaw === "string") {
        nextDelta.edited_text = editedTextRaw;
      }
      nextItem.latest_delta = nextDelta;
    }
    normalized.push(nextItem);
  });
  return normalized;
};

const isProxyTraceStatus = (value: unknown): value is ProxyTraceSummary["status"] =>
  value === "active" || value === "completed" || value === "failed" || value === "cancelled";

const normalizeProxyTraceSummary = (value: unknown): ProxyTraceSummary | null => {
  if (!isRecord(value)) {
    return null;
  }
  const traceId = coerceText(value.trace_id).trim();
  const requestId = coerceText(value.request_id).trim();
  const status = value.status;
  const method = coerceText(value.method).trim();
  const requestPath = coerceText(value.request_path).trim();
  const startedAt = coerceText(value.started_at).trim();
  if (!traceId || !requestId || !isProxyTraceStatus(status) || !method || !requestPath) {
    return null;
  }
  const nextTrace: ProxyTraceSummary = {
    trace_id: traceId,
    request_id: requestId,
    status,
    method,
    request_path: requestPath,
    is_stream: value.is_stream === true,
    started_at: startedAt,
  };
  const textFields = [
    "request_model",
    "published_model",
    "provider",
    "upstream_model",
    "target_id",
    "target_display_name",
    "ended_at",
    "error",
  ] as const;
  textFields.forEach((field) => {
    const text = coerceText(value[field]).trim();
    if (text) {
      nextTrace[field] = text;
    }
  });
  const numberFields = [
    "status_code",
    "duration_ms",
    "chunk_count",
    "events_count",
    "request_body_bytes",
    "response_body_bytes",
  ] as const;
  numberFields.forEach((field) => {
    const numberValue = Number(value[field]);
    if (Number.isFinite(numberValue)) {
      nextTrace[field] = numberValue;
    }
  });
  nextTrace.has_route_attempts = value.has_route_attempts === true;
  nextTrace.has_failover = value.has_failover === true;
  nextTrace.has_cooldown = value.has_cooldown === true;
  nextTrace.request_body_truncated = value.request_body_truncated === true;
  nextTrace.response_body_truncated = value.response_body_truncated === true;
  return nextTrace;
};

const normalizeProxyTraceList = (value: unknown): ProxyTraceSummary[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => normalizeProxyTraceSummary(item))
    .filter((item): item is ProxyTraceSummary => item !== null);
};

const normalizeProxyTraceDetail = (value: unknown): ProxyTrace | null => {
  const summary = normalizeProxyTraceSummary(value);
  if (!summary || !isRecord(value)) {
    return null;
  }
  const detail: ProxyTrace = {
    ...summary,
    events: [],
  };
  const routeMode = value.route_mode;
  if (isProxyMode(routeMode)) {
    detail.route_mode = routeMode;
  }
  const textFields = [
    "request_api",
    "client_model",
    "resolved_target_label",
    "failover_pool_id",
    "target_api_base_url",
    "target_model",
    "first_chunk_at",
    "finish_reason",
  ] as const;
  textFields.forEach((field) => {
    const text = coerceText(value[field]).trim();
    if (text) {
      (detail as Record<string, unknown>)[field] = text;
    }
  });
  if (isRecord(value.request_body)) {
    detail.request_body = value.request_body;
  }
  if (isRecord(value.response_body)) {
    detail.response_body = value.response_body;
  }
  if (Array.isArray(value.events)) {
    detail.events = value.events
      .filter(isRecord)
      .map((event) => ({
        at: coerceText(event.at),
        kind: coerceText(event.kind),
        message: coerceText(event.message) || undefined,
        data: isRecord(event.data) ? event.data : undefined,
      }))
      .filter((event) => event.at && event.kind);
  }
  return detail;
};

export const useMtgaStore = () => {
  const api = useMtgaApi();

  const mtgaAuthKey = useState<string>("mtga-auth-key", () => "");
  const routingTargets = useState<ModelRoutingTarget[]>("mtga-routing-targets", () => []);
  const failoverPools = useState<FailoverPool[]>("mtga-failover-pools", () => []);
  const publishedModels = useState<PublishedModel[]>("mtga-published-models", () => []);
  const promptCacheBucketId = useState<string>("mtga-prompt-cache-bucket-id", () => "");
  const proxyMode = useState<ProxyMode>("mtga-proxy-mode", () => DEFAULT_PROXY_MODE);
  const savedProxyMode = useState<ProxyMode>("mtga-saved-proxy-mode", () => DEFAULT_PROXY_MODE);
  const traePath = useState<string>("mtga-trae-path", () => DEFAULT_TRAE_PATH);
  const savedTraePath = useState<string>("mtga-saved-trae-path", () => DEFAULT_TRAE_PATH);
  const minimizeToTrayOnClose = useState<boolean>(
    "mtga-minimize-to-tray-on-close",
    () => DEFAULT_MINIMIZE_TO_TRAY_ON_CLOSE,
  );
  const savedMinimizeToTrayOnClose = useState<boolean>(
    "mtga-saved-minimize-to-tray-on-close",
    () => DEFAULT_MINIMIZE_TO_TRAY_ON_CLOSE,
  );
  const runtimeOptions = useState<RuntimeOptions>("mtga-runtime-options", () => ({
    ...DEFAULT_RUNTIME_OPTIONS,
  }));
  const logs = useState<string[]>("mtga-logs", () => []);
  const systemPrompts = useState<SystemPromptItem[]>("mtga-system-prompts", () => []);
  const proxyTraces = useState<ProxyTraceSummary[]>("mtga-proxy-traces", () => []);
  const selectedProxyTrace = useState<ProxyTrace | null>("mtga-selected-proxy-trace", () => null);
  const logCursor = useState<number>("mtga-log-cursor", () => 0);
  const logStreamActive = useState<boolean>("mtga-log-stream-active", () => false);
  const appInfo = useState<AppInfo>("mtga-app-info", () => ({ ...DEFAULT_APP_INFO }));
  const initialized = useState<boolean>("mtga-initialized", () => false);
  const hasNewVersion = useState<boolean>("mtga-has-new-version", () => false);
  const updateDialogOpen = useState<boolean>("mtga-update-dialog-open", () => false);
  const updateVersionLabel = useState<string>("mtga-update-version-label", () => "");
  const updateNotesHtml = useState<string>("mtga-update-notes-html", () => "");
  const updateReleaseUrl = useState<string>("mtga-update-release-url", () => "");
  const updateAutoChecked = useState<boolean>("mtga-update-auto-checked", () => false);
  const panelNavTarget = useState<string | null>("mtga-panel-nav-target", () => null);
  const panelNavSignal = useState<number>("mtga-panel-nav-signal", () => 0);
  const mainTabTarget = useState<MainTabKey | null>("mtga-main-tab-target", () => null);
  const mainTabSignal = useState<number>("mtga-main-tab-signal", () => 0);
  const proxyStepListenerActive = useState<boolean>("mtga-proxy-step-listener-active", () => false);
  const proxyStepQueue = useState<MainTabKey[]>("mtga-proxy-step-queue", () => []);
  const proxyStepProcessing = useState<boolean>("mtga-proxy-step-processing", () => false);
  const proxyStatusListenerActive = useState<boolean>(
    "mtga-proxy-status-listener-active",
    () => false,
  );
  const proxyRuntimeKnown = useState<boolean>("mtga-proxy-runtime-known", () => false);
  const proxyRuntimeRunning = useState<boolean>("mtga-proxy-runtime-running", () => false);
  const proxyRuntimeActiveMode = useState<ProxyMode | null>(
    "mtga-proxy-runtime-active-mode",
    () => null,
  );
  const proxyRuntimeLoopbackPort = useState<number | null>(
    "mtga-proxy-runtime-loopback-port",
    () => null,
  );
  let logPollTimer: ReturnType<typeof setTimeout> | null = null;
  let proxyStepUnlisten: (() => void) | null = null;

  const drainProxyStepQueue = async () => {
    if (proxyStepProcessing.value) {
      return;
    }
    proxyStepProcessing.value = true;
    while (proxyStepQueue.value.length) {
      const step = proxyStepQueue.value.shift();
      if (!step) {
        continue;
      }
      panelNavTarget.value = "main-tabs";
      panelNavSignal.value += 1;
      mainTabTarget.value = step;
      mainTabSignal.value += 1;
      await nextTick();
      await new Promise((resolve) => setTimeout(resolve, 240));
    }
    proxyStepProcessing.value = false;
  };

  const enqueueProxyStep = (step: MainTabKey) => {
    proxyStepQueue.value.push(step);
    void drainProxyStepQueue();
  };

  const navigateProxyMissingConfigPanel = (message?: string | null) => {
    const normalized = (message || "").trim();
    if (!normalized) {
      return;
    }
    if (normalized.includes("Путь к Trae") || normalized.startsWith("trae_path_")) {
      panelNavTarget.value = "settings";
      panelNavSignal.value += 1;
      return;
    }
    if (
      normalized.includes("Маршрутизация моделей") ||
      normalized.includes("маршрутизации моделей") ||
      normalized.includes("Нет доступных групп конфигурации") ||
      normalized === "model_routing_missing" ||
      normalized === "global_config_missing" ||
      normalized === "config_group_missing"
    ) {
      panelNavTarget.value = "model-routing";
      panelNavSignal.value += 1;
    }
  };

  const appendLog = (message: string) => {
    if (!shouldKeepRuntimeLog(message)) {
      return;
    }
    logs.value.push(message);
    const overflow = logs.value.length - FRONTEND_LOG_LIMIT;
    if (overflow > 0) {
      logs.value.splice(0, overflow);
    }
  };

  const handleProxyStep = (payload: unknown) => {
    const normalized = normalizeProxyStepPayload(payload);
    if (!normalized || !isMainTabKey(normalized.step)) {
      return;
    }
    if (isPanelTarget(normalized.panel_target)) {
      panelNavTarget.value = normalized.panel_target;
      panelNavSignal.value += 1;
    } else {
      navigateProxyMissingConfigPanel(normalized.message);
    }
    if (normalized.status === "started") {
      enqueueProxyStep(normalized.step);
    }
  };

  const applyProxyRuntimeStatus = (payload: ProxyRuntimeStatusPayload) => {
    proxyRuntimeKnown.value = true;
    proxyRuntimeRunning.value = payload.running;
    proxyRuntimeActiveMode.value = payload.active_mode ?? null;
    proxyRuntimeLoopbackPort.value = normalizeOptionalPort(payload.loopback_port);
  };

  const appendLogs = (entries?: string[]) => {
    if (!entries || !entries.length) {
      return;
    }
    entries.forEach((entry) => appendLog(entry));
  };

  const applyInvokeResult = (result: InvokeResult | null, fallbackMessage: string) => {
    if (!result) {
      appendLog(`${fallbackMessage}: сбой — не удалось подключиться к бэкенду`);
      return false;
    }
    if (result.message) {
      appendLog(result.message);
    }
    return result.ok;
  };

  const startLogStream = () => {
    if (logStreamActive.value) {
      return;
    }
    logStreamActive.value = true;
    if (logPollTimer !== null) {
      clearTimeout(logPollTimer);
      logPollTimer = null;
    }

    const applyLogResult = (result: LogPullResult | null) => {
      if (!result) {
        return;
      }
      if (Array.isArray(result.items) && result.items.length) {
        appendLogs(result.items);
      }
      if (typeof result.next_id === "number") {
        logCursor.value = result.next_id;
      }
    };

    const startPolling = () => {
      const loop = async () => {
        if (!logStreamActive.value) {
          return;
        }
        const result = await api.pullLogs({
          after_id: logCursor.value || null,
          timeout_ms: 0,
          max_items: 200,
        });
        if (!logStreamActive.value) {
          return;
        }
        applyLogResult(result);
        logPollTimer = setTimeout(loop, 200);
      };
      void loop();
    };

    const startChannel = async () => {
      if (!isTauriRuntime()) {
        startPolling();
        return;
      }

      const ok = await api.startLogChannel(
        (payload: LogEventPayload) => {
          if (!logStreamActive.value) {
            return;
          }
          applyLogResult(payload);
        },
        {
          afterId: logCursor.value || null,
        },
      );
      if (!ok) {
        startPolling();
      }
    };

    void startChannel();
  };

  const stopLogStream = () => {
    logStreamActive.value = false;
    if (logPollTimer !== null) {
      clearTimeout(logPollTimer);
      logPollTimer = null;
    }
  };

  const startProxyStepListener = () => {
    if (proxyStepListenerActive.value) {
      return;
    }
    proxyStepListenerActive.value = true;
    if (proxyStepUnlisten) {
      try {
        proxyStepUnlisten();
      } catch {
        // ignore cleanup errors
      }
      proxyStepUnlisten = null;
    }

    if (isBundledRuntime()) {
      return;
    }

    const listenProxySteps = async () => {
      try {
        const unlisten = await listen<ProxyStartStepEvent>("mtga:proxy-step", (event) => {
          handleProxyStep(event.payload);
        });
        if (!proxyStepListenerActive.value) {
          try {
            unlisten();
          } catch {
            // ignore cleanup errors
          }
          return;
        }
        proxyStepUnlisten = () => {
          void unlisten();
        };
      } catch (error) {
        console.warn("[mtga] proxy step listen failed", error);
      }
    };

    void listenProxySteps();
  };

  const stopProxyStepListener = () => {
    proxyStepListenerActive.value = false;
    if (proxyStepUnlisten) {
      try {
        proxyStepUnlisten();
      } catch {
        // ignore cleanup errors
      }
      proxyStepUnlisten = null;
    }
  };

  const startProxyStatusListener = async () => {
    if (proxyStatusListenerActive.value) {
      return true;
    }
    proxyStatusListenerActive.value = true;
    const ok = await api.startProxyStatusChannel(
      (payload) => {
        const normalized = normalizeProxyRuntimeStatusPayload(payload);
        if (!proxyStatusListenerActive.value || !normalized) {
          return;
        }
        applyProxyRuntimeStatus(normalized);
      },
      {
        startFromLatest: true,
      },
    );
    if (!ok) {
      proxyStatusListenerActive.value = false;
    }
    return ok;
  };

  const loadConfig = async () => {
    const result = await api.loadConfig();
    if (!result) {
      return false;
    }
    const normalizedTargets = normalizeTargets(result.targets);
    const effectiveTargets = normalizedTargets.length
      ? normalizedTargets
      : normalizeTargets(result.config_groups);
    const normalizedPools = normalizeFailoverPools(result.failover_pools, effectiveTargets);
    const normalizedPublishedModels = normalizePublishedModels(
      result.published_models,
      effectiveTargets,
      normalizedPools,
    );
    const mappedModelName = coerceText(result.mapped_model_id).trim();
    const effectivePublishedModels =
      normalizedPublishedModels.length || !mappedModelName || !effectiveTargets.length
        ? normalizedPublishedModels
        : [
            {
              name: mappedModelName,
              enabled: true,
              primary_target_id: effectiveTargets[0]?.id || "",
              primary_upstream_model: effectiveTargets[0]?.upstream_model || "",
              failover_pool_id: null,
            },
          ];

    routingTargets.value = effectiveTargets;
    failoverPools.value = normalizedPools;
    publishedModels.value = effectivePublishedModels;
    promptCacheBucketId.value = coerceText(result.prompt_cache_bucket_id).trim();
    mtgaAuthKey.value = coerceText(result.mtga_auth_key);
    proxyMode.value = isProxyMode(result.proxy_mode) ? result.proxy_mode : DEFAULT_PROXY_MODE;
    savedProxyMode.value = proxyMode.value;
    traePath.value = coerceText(result.trae_path).trim();
    savedTraePath.value = traePath.value;
    minimizeToTrayOnClose.value =
      typeof result.minimize_to_tray_on_close === "boolean"
        ? result.minimize_to_tray_on_close
        : DEFAULT_MINIMIZE_TO_TRAY_ON_CLOSE;
    savedMinimizeToTrayOnClose.value = minimizeToTrayOnClose.value;
    if (Array.isArray(result.warnings)) {
      result.warnings.forEach((warning) => {
        const text = coerceText(warning).trim();
        if (text) {
          appendLog(text);
        }
      });
    }
    return true;
  };

  const saveConfig = async () => {
    const payload: ConfigPayload = {
      schema_version: 3,
      mtga_auth_key: coerceText(mtgaAuthKey.value),
      targets: routingTargets.value,
      failover_pools: failoverPools.value,
      published_models: publishedModels.value,
      prompt_cache_bucket_id: coerceText(promptCacheBucketId.value),
      proxy_mode: proxyMode.value,
      trae_path: coerceText(traePath.value).trim(),
      minimize_to_tray_on_close: minimizeToTrayOnClose.value,
    };
    const ok = await api.saveConfig(payload);
    if (ok) {
      savedProxyMode.value = payload.proxy_mode;
      savedTraePath.value = payload.trae_path;
      savedMinimizeToTrayOnClose.value = payload.minimize_to_tray_on_close === true;
    }
    return Boolean(ok);
  };

  const saveAppSettings = async () => {
    const payload = {
      minimize_to_tray_on_close: minimizeToTrayOnClose.value,
    };
    const ok = await api.saveAppSettings(payload);
    if (ok) {
      savedMinimizeToTrayOnClose.value = payload.minimize_to_tray_on_close;
    }
    return Boolean(ok);
  };

  const fetchProxyRuntimeStatus = async (): Promise<{
    running: boolean;
    active_mode: ProxyMode | null;
    loopback_port: number | null;
  } | null> => {
    const result = await api.proxyRuntimeStatus();
    if (!result) {
      appendLog("Не удалось получить состояние прокси: нет соединения с бэкендом");
      return null;
    }
    if (!result.ok) {
      appendLog(result.message?.trim() || "Не удалось получить состояние прокси");
      return null;
    }
    if (!isRecord(result.details)) {
      return null;
    }
    const running = result.details["running"];
    const activeMode = result.details["active_mode"];
    const loopbackPort = normalizeOptionalPort(result.details["loopback_port"]);
    if (
      typeof running !== "boolean" ||
      (activeMode !== null && typeof activeMode !== "undefined" && !isProxyMode(activeMode))
    ) {
      return null;
    }
    const normalized = {
      running,
      active_mode: activeMode ?? null,
      loopback_port: loopbackPort,
    };
    applyProxyRuntimeStatus(normalized);
    return normalized;
  };

  const loadAppInfo = async () => {
    const info = await api.getAppInfo();
    if (!info) {
      return false;
    }
    appInfo.value = {
      ...DEFAULT_APP_INFO,
      ...info,
    };
    return true;
  };

  const buildStartupLogs = (details: Record<string, unknown>) => {
    const envOk = details["env_ok"] === true;
    const envMessage = coerceText(details["env_message"]);
    if (envMessage) {
      appendLog(`${envOk ? "✅" : "❌"} ${envMessage}`);
    }
    if (envOk) {
      const runtime = coerceText(details["runtime"]);
      if (runtime === "tauri" || runtime === "nuitka") {
        appendLog("📦 Работает в упакованной среде");
      } else {
        appendLog("🔧 Работает в среде разработки");
      }
    }

    const allowFlag = coerceText(details["allow_unsafe_hosts_flag"]) || "--allow-unsafe-hosts";
    const hostsModifyBlocked = details["hosts_modify_blocked"] === true;
    if (hostsModifyBlocked) {
      const status = coerceText(details["hosts_modify_block_status"]) || "unknown";
      appendLog(
        `⚠️ Обнаружено ограничение записи в файл hosts (status=${status}), включён ограниченный режим hosts: добавление будет выполняться дозаписью (без гарантии атомарности и дедупликации), автоматическое удаление/восстановление отключено.`,
      );
      appendLog(
        `⚠️ Вы можете нажать «Открыть файл hosts» и изменить его вручную, либо использовать параметр запуска ${allowFlag}, чтобы обойти эту проверку и принудительно попытаться выполнить атомарную запись (на свой риск).`,
      );
    } else {
      const preflightOk = details["hosts_preflight_ok"] === true;
      const preflightStatus = coerceText(details["hosts_preflight_status"]);
      if (preflightStatus && !preflightOk) {
        appendLog(
          `⚠️ Предварительная проверка hosts не пройдена (status=${preflightStatus}), но она переопределена параметром запуска ${allowFlag}; последующие автоматические изменения могут завершиться неудачей.`,
        );
      }
    }

    if (details["explicit_proxy_detected"] === true) {
      appendLog(
        "⚠️".repeat(21) +
          "\nОбнаружена явная конфигурация прокси: некоторые приложения могут идти через прокси и обходить перенаправление через hosts.",
      );
      appendLog(
        "Рекомендации: 1. Отключите явный прокси (например, системный прокси clash) или используйте TUN/VPN",
      );
      appendLog("      2. Проверьте настройки прокси в Trae.\n" + "⚠️".repeat(21));
    }

    if (details["legacy_user_data_dir_detected"] === true) {
      const legacyDir = coerceText(details["legacy_user_data_dir"]);
      appendLog(
        `⚠️ Обнаружен каталог пользовательских данных старой версии${legacyDir ? `: ${legacyDir}` : ""}. Текущая версия больше не использует этот каталог; если нужно сохранить старые настройки, сертификаты или резервные копии, перенесите их вручную в новый каталог пользовательских данных.`,
      );
    }

    appendLog("MTGA запущен");
    appendLog("Выберите действие или просто используйте «Запустить всё одной кнопкой»...");
  };

  const loadStartupStatus = async () => {
    const result = await api.getStartupStatus();
    if (!result) {
      appendLog("Не удалось загрузить журнал запуска: нет соединения с бэкендом");
      return false;
    }
    if (isRecord(result.details)) {
      buildStartupLogs(result.details);
    }
    return result.ok;
  };

  const init = async () => {
    if (initialized.value) {
      startLogStream();
      startProxyStepListener();
      return;
    }
    initialized.value = true;
    startLogStream();
    startProxyStepListener();
    await Promise.all([loadAppInfo(), loadConfig(), loadStartupStatus()]);
  };

  const buildProxyPayload = () => ({
    debug_mode: runtimeOptions.value.debugMode,
    disable_ssl_strict_mode: runtimeOptions.value.disableSslStrict,
    force_stream: runtimeOptions.value.forceStream,
    stream_mode: runtimeOptions.value.streamMode,
    proxy_mode: savedProxyMode.value,
    trae_path: coerceText(savedTraePath.value).trim(),
  });

  const runGenerateCertificates = async () => {
    const result = await api.generateCertificates();
    return applyInvokeResult(result, "Генерация сертификатов");
  };

  const runInstallCaCert = async () => {
    const result = await api.installCaCert();
    return applyInvokeResult(result, "Установка CA-сертификата");
  };

  const runClearCaCert = async (caCommonName?: string) => {
    const normalizedCaCommonName = caCommonName?.trim();
    const result = await api.clearCaCert(
      normalizedCaCommonName ? { ca_common_name: normalizedCaCommonName } : {},
    );
    return applyInvokeResult(result, "Удаление CA-сертификата");
  };

  const runHostsModify = async (mode: "add" | "backup" | "restore" | "remove") => {
    const result = await api.hostsModify({ mode });
    return applyInvokeResult(result, "Операция с hosts");
  };

  const runHostsOpen = async () => {
    const result = await api.hostsOpen();
    return applyInvokeResult(result, "Открытие файла hosts");
  };

  const runProxyStart = async () => {
    const result = await api.proxyStart(buildProxyPayload());
    navigateProxyMissingConfigPanel(result?.message);
    const ok = applyInvokeResult(result, "Запуск прокси-сервера");
    if (ok) {
      void fetchProxyRuntimeStatus();
    }
    return ok;
  };

  const runProxyApplyCurrentConfig = async () => {
    const result = await api.proxyApplyCurrentConfig(buildProxyPayload());
    navigateProxyMissingConfigPanel(result?.message);
    if (!result) {
      appendLog("Не удалось применить конфигурацию прокси: нет соединения с бэкендом");
      return false;
    }

    const message = coerceText(result.message).trim();
    const applyStatus = isRecord(result.details) ? coerceText(result.details["apply_status"]) : "";

    if (result.ok) {
      if (applyStatus === "deferred" || message === "proxy_not_running") {
        appendLog("Прокси не запущен, конфигурация вступит в силу при следующем запуске");
      } else {
        appendLog("Маршрутизация моделей применена к работающему прокси");
      }
      return true;
    }

    if (
      message === "model_routing_missing" ||
      message === "global_config_missing" ||
      message === "config_group_missing"
    ) {
      appendLog(
        "Не удалось применить конфигурацию прокси: в маршрутизации моделей нет доступных публикуемых моделей или целей",
      );
      return false;
    }
    if (message === "config_invalid") {
      appendLog(
        "Не удалось применить конфигурацию прокси: текущая маршрутизация моделей недействительна",
      );
      return false;
    }

    appendLog("Не удалось применить конфигурацию прокси");
    return false;
  };

  const runProxyStop = async () => {
    const result = await api.proxyStop();
    const ok = applyInvokeResult(result, "Остановка прокси-сервера");
    if (ok) {
      void fetchProxyRuntimeStatus();
    }
    return ok;
  };

  const runProxyCheckNetwork = async () => {
    const result = await api.proxyCheckNetwork();
    return applyInvokeResult(result, "Проверка сетевого окружения");
  };

  const runProxyStartAll = async () => {
    if (isTauriRuntime()) {
      const ok = await api.startProxyStepChannel(handleProxyStep, {
        reset: true,
        startFromLatest: true,
      });
      if (!ok) {
        appendLog(
          "⚠️ Не удалось запустить proxy-step channel, откат к автонавигации через слушатель событий",
        );
      }
    }
    const result = await api.proxyStartAll(buildProxyPayload());
    navigateProxyMissingConfigPanel(result?.message);
    const ok = applyInvokeResult(result, "Запуск всех сервисов одной кнопкой");
    if (ok) {
      void fetchProxyRuntimeStatus();
    }
    return ok;
  };

  const runTargetTest = async (targetId: string) => {
    const result = await api.modelRoutingTargetTest({ target_id: targetId });
    return applyInvokeResult(result, "Проверка доступности цели");
  };

  const fetchTargetModels = async (payload: {
    provider?: string;
    api_url: string;
    api_key?: string;
    middle_route?: string;
    model_id?: string;
  }): Promise<TargetModelsResult | null> => {
    const result = await api.modelRoutingTargetModels(payload);
    const ok = applyInvokeResult(result, "Получение списка моделей");
    if (!ok || !result) {
      return null;
    }
    const strategyIdRaw = result.details?.["strategy_id"];
    const strategyId =
      typeof strategyIdRaw === "string" && strategyIdRaw.trim() ? strategyIdRaw.trim() : null;
    return {
      models: normalizeModelList(result.details?.["models"]),
      strategyId,
    };
  };

  const runUserDataOpenDir = async () => {
    const result = await api.userDataOpenDir();
    return applyInvokeResult(result, "Открытие каталога пользовательских данных");
  };

  const runUserDataBackup = async () => {
    const result = await api.userDataBackup();
    return applyInvokeResult(result, "Резервное копирование пользовательских данных");
  };

  const runUserDataRestoreLatest = async () => {
    const result = await api.userDataRestoreLatest();
    return applyInvokeResult(result, "Восстановление пользовательских данных");
  };

  const runUserDataClear = async () => {
    const result = await api.userDataClear();
    return applyInvokeResult(result, "Очистка пользовательских данных");
  };

  const runBrowseTraePath = async () => {
    if (!isTauriRuntime()) {
      appendLog(
        "Не удалось выбрать путь к Trae: текущая среда не поддерживает системный выбор файлов",
      );
      return false;
    }

    const currentPath = coerceText(traePath.value).trim();
    const fallbackPath = getDefaultTraeDialogPath();
    const resolveSource = currentPath || fallbackPath;
    const resolvedPathResult = await api.resolveTraeDialogPath({ path: resolveSource });
    const resolvedPath = coerceText(resolvedPathResult?.path).trim();
    const defaultPath = resolvedPath || currentPath || undefined;

    try {
      appendLog("Выбор пути к Trae через Tauri dialog...");
      const { open } = await import("@tauri-apps/plugin-dialog");
      const options = {
        title: "Выберите приложение или исполняемый файл Trae",
        multiple: false,
        directory: false,
        filters: [{ name: "Приложение Trae", extensions: ["app", "exe"] }],
      };
      const selected = await open(defaultPath ? { ...options, defaultPath } : options);
      const selectedPath = typeof selected === "string" ? selected.trim() : "";
      if (!selectedPath) {
        appendLog("Выбор пути к Trae отменён");
        return false;
      }

      traePath.value = selectedPath;
      appendLog(`Выбран путь к Trae: ${selectedPath}`);
      return true;
    } catch (error) {
      console.warn("[mtga] tauri dialog browse trae path failed", error);
      const errorMessage = formatUnknownError(error);
      appendLog(
        errorMessage
          ? `Tauri dialog недоступен, откат к выбору через бэкенд: ${errorMessage}`
          : "Tauri dialog недоступен, откат к выбору через бэкенд",
      );
    }

    const result = await api.browseTraePath({ path: currentPath || fallbackPath });
    if (!result) {
      appendLog("Не удалось выбрать путь к Trae");
      return false;
    }
    const errorMessage = coerceText(result.error).trim();
    if (errorMessage) {
      appendLog(`Не удалось выбрать путь к Trae: ${errorMessage}`);
      return false;
    }
    const selectedPath = coerceText(result.path).trim();
    if (!selectedPath) {
      appendLog("Выбор пути к Trae отменён");
      return false;
    }

    traePath.value = selectedPath;
    appendLog(`Выбран путь к Trae: ${selectedPath}`);
    return true;
  };

  const runCheckUpdates = async () => {
    const result = await api.checkUpdates();
    const ok = applyInvokeResult(result, "Проверка обновлений");
    if (!result || !isRecord(result.details)) {
      return ok;
    }
    const updateResult = isRecord(result.details["update_result"])
      ? result.details["update_result"]
      : result.details;
    const status = coerceText(updateResult["status"]);
    if (status === "new_version") {
      hasNewVersion.value = true;
      updateVersionLabel.value = coerceText(updateResult["latest_version"]);
      updateNotesHtml.value = coerceText(updateResult["release_notes"]);
      updateReleaseUrl.value = coerceText(updateResult["release_url"]);
      updateDialogOpen.value = true;
    } else if (status === "up_to_date") {
      hasNewVersion.value = false;
      const latestVersion = coerceText(updateResult["latest_version"]);
      if (latestVersion) {
        appendLog(`Установлена последняя версия: ${latestVersion}`);
      }
    }
    return ok;
  };

  const loadSystemPrompts = async () => {
    const result = await api.systemPromptsList();
    const ok = applyInvokeResult(result, "Загрузка системных промптов");
    if (!ok) {
      return false;
    }
    if (!result || !isRecord(result.details)) {
      systemPrompts.value = [];
      return true;
    }
    systemPrompts.value = normalizeSystemPromptList(result.details["items"]);
    return true;
  };

  const loadProxyTraces = async () => {
    const result = await api.proxyTracesList({ limit: 300 });
    if (!result) {
      appendLog("Не удалось загрузить журнал прокси: нет соединения с бэкендом");
      return false;
    }
    proxyTraces.value = normalizeProxyTraceList(result.items);
    const selectedTraceId = selectedProxyTrace.value?.trace_id;
    if (selectedTraceId && !proxyTraces.value.some((item) => item.trace_id === selectedTraceId)) {
      selectedProxyTrace.value = null;
    }
    return true;
  };

  const loadProxyTraceDetail = async (traceId: string) => {
    const normalizedTraceId = traceId.trim();
    if (!normalizedTraceId) {
      selectedProxyTrace.value = null;
      return false;
    }
    const result = await api.proxyTraceDetail({ trace_id: normalizedTraceId });
    const detail = normalizeProxyTraceDetail(result);
    if (!detail) {
      appendLog("Не удалось загрузить детали записи журнала прокси: запись не существует");
      selectedProxyTrace.value = null;
      return false;
    }
    selectedProxyTrace.value = detail;
    return true;
  };

  const clearProxyTraces = async () => {
    const result = await api.proxyTracesClear();
    if (!result) {
      appendLog("Не удалось очистить журнал прокси: нет соединения с бэкендом");
      return false;
    }
    const deletedCount = Number(result.deleted_count || 0);
    const keptActiveCount = Number(result.kept_active_count || 0);
    appendLog(
      keptActiveCount > 0
        ? `Удалено записей журнала прокси: ${deletedCount}, сохранено активных: ${keptActiveCount}`
        : `Удалено записей журнала прокси: ${deletedCount}`,
    );
    await loadProxyTraces();
    if (
      selectedProxyTrace.value &&
      !proxyTraces.value.some((item) => item.trace_id === selectedProxyTrace.value?.trace_id)
    ) {
      selectedProxyTrace.value = null;
    }
    return true;
  };

  const updateSystemPrompt = async (payload: { hash: string; edited_text: string }) => {
    const result = await api.systemPromptsUpdate(payload);
    const ok = applyInvokeResult(result, "Обновление системного промпта");
    if (!ok) {
      return false;
    }
    await loadSystemPrompts();
    return true;
  };

  const deleteSystemPrompts = async (payload: { hashes: string[] }) => {
    const normalizedHashes = payload.hashes
      .map((hash) => coerceText(hash).trim())
      .filter((hash) => hash.length > 0);
    if (!normalizedHashes.length) {
      appendLog("Не удалось удалить системные промпты: не передан корректный hash");
      return false;
    }
    const result = await api.systemPromptsDelete({ hashes: normalizedHashes });
    const ok = applyInvokeResult(result, "Удаление системных промптов");
    if (!ok) {
      return false;
    }
    await loadSystemPrompts();
    return true;
  };

  const runCheckUpdatesOnce = async () => {
    if (updateAutoChecked.value) {
      return false;
    }
    updateAutoChecked.value = true;
    return runCheckUpdates();
  };

  const closeUpdateDialog = () => {
    updateDialogOpen.value = false;
  };

  const openUpdateRelease = async () => {
    const url = updateReleaseUrl.value.trim();
    if (!url || typeof window === "undefined") {
      return;
    }
    if (isTauriRuntime()) {
      try {
        const { open } = await import("@tauri-apps/plugin-shell");
        await open(url);
        return;
      } catch (error) {
        console.warn("[mtga] open release url failed", error);
        appendLog("Не удалось открыть страницу релиза, скопируйте ссылку вручную");
        return;
      }
    }
    const opened = window.open(url, "_blank", "noopener,noreferrer");
    if (!opened) {
      window.location.href = url;
    }
  };

  const runPlaceholder = (label: string) => {
    appendLog(`${label} (ожидает подключения к бэкенду)`);
  };

  return {
    mtgaAuthKey,
    routingTargets,
    failoverPools,
    publishedModels,
    promptCacheBucketId,
    proxyMode,
    savedProxyMode,
    proxyRuntimeKnown,
    proxyRuntimeRunning,
    proxyRuntimeActiveMode,
    proxyRuntimeLoopbackPort,
    traePath,
    minimizeToTrayOnClose,
    savedMinimizeToTrayOnClose,
    runtimeOptions,
    logs,
    systemPrompts,
    proxyTraces,
    selectedProxyTrace,
    logCursor,
    appInfo,
    hasNewVersion,
    updateDialogOpen,
    updateVersionLabel,
    updateNotesHtml,
    updateReleaseUrl,
    panelNavTarget,
    panelNavSignal,
    mainTabTarget,
    mainTabSignal,
    appendLog,
    startLogStream,
    stopLogStream,
    startProxyStepListener,
    stopProxyStepListener,
    startProxyStatusListener,
    loadConfig,
    saveConfig,
    saveAppSettings,
    fetchProxyRuntimeStatus,
    init,
    runGenerateCertificates,
    runInstallCaCert,
    runClearCaCert,
    runHostsModify,
    runHostsOpen,
    runProxyStart,
    runProxyApplyCurrentConfig,
    runProxyStop,
    runProxyCheckNetwork,
    runProxyStartAll,
    runTargetTest,
    fetchTargetModels,
    runUserDataOpenDir,
    runUserDataBackup,
    runUserDataRestoreLatest,
    runUserDataClear,
    runBrowseTraePath,
    runCheckUpdates,
    runCheckUpdatesOnce,
    closeUpdateDialog,
    openUpdateRelease,
    loadSystemPrompts,
    loadProxyTraces,
    loadProxyTraceDetail,
    clearProxyTraces,
    updateSystemPrompt,
    deleteSystemPrompts,
    runPlaceholder,
  };
};
