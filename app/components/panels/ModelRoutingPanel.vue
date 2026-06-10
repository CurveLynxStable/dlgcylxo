<script setup lang="ts">
import type {
  FailoverPool,
  ModelRoutingTarget,
  ProviderId,
  PublishedModel,
} from "~/composables/mtgaTypes";

const store = useMtgaStore();

const targets = store.routingTargets;
const failoverPools = store.failoverPools;
const publishedModels = store.publishedModels;

const DEFAULT_MIDDLE_ROUTE = "/v1";
const GEMINI_DEFAULT_MIDDLE_ROUTE = "/v1beta";
const PROVIDER_OPTIONS: { label: string; value: ProviderId }[] = [
  { label: "OpenAI Chat Completion", value: "openai_chat_completion" },
  { label: "OpenAI Response", value: "openai_response" },
  { label: "Anthropic", value: "anthropic" },
  { label: "Gemini", value: "gemini" },
];
const PROVIDER_LABELS: Record<ProviderId, string> = {
  openai_chat_completion: "OpenAI Chat Completion",
  openai_response: "OpenAI Response",
  anthropic: "Anthropic",
  gemini: "Gemini",
};
const MODEL_PREVIEW_CHIP_CLASS =
  "max-w-full wrap-anywhere rounded-md border border-slate-200 bg-white px-1.5 py-0.5 font-mono text-[10px] text-slate-600";
type RouteSectionId = "targets" | "published" | "failover";
type RouteView = "overview" | RouteSectionId;

const selectedTargetId = ref("");
const selectedPublishedName = ref("");
const selectedPoolId = ref("");
const targetDeleteMode = ref(false);
const publishedDeleteMode = ref(false);
const poolDeleteMode = ref(false);
const selectedTargetIds = ref<string[]>([]);
const selectedPublishedNames = ref<string[]>([]);
const selectedPoolIds = ref<string[]>([]);
const editorOpen = ref(false);
const settingsOpen = ref(false);
const editorKind = ref<"target" | "published" | "pool">("target");
const editorMode = ref<"add" | "edit">("add");
const formError = ref("");
const saving = ref(false);
const refreshing = ref(false);
const targetTesting = ref(false);
const modelLoading = ref(false);
const activeView = ref<RouteView>("overview");
const availableModels = ref<string[]>([]);
const selectedUpstreamModels = ref<string[]>([]);
const customUpstreamModelIds = ref<string[]>([]);
const targetCustomUpstreamModelIds = ref<Record<string, string[]>>({});
const modelDiscoveryLoaded = ref(false);
const targetDiscoveryStrategy = ref("");
const targetDiscoveryScope = ref("");
const requestBodyPatchOpen = ref(false);

const targetForm = reactive({
  id: "",
  display_name: "",
  provider: "openai_chat_completion" as ProviderId,
  api_base: "",
  upstream_model: "",
  api_key: "",
  middle_route: "",
  prompt_cache_enabled: false,
  request_body_patch_text: "",
});

const publishedForm = reactive({
  name: "",
  enabled: true,
  primary_route_key: "",
  failover_pool_id: "",
});

const poolForm = reactive({
  id: "",
  trigger_statuses: "429",
  cooldown_seconds: 10,
  member_keys: [] as string[],
});
const settingsForm = reactive({
  mtga_auth_key: "",
  prompt_cache_bucket_id: "",
});

const selectedTarget = computed(() =>
  targets.value.find((target) => target.id === selectedTargetId.value),
);
const selectedPublishedModel = computed(() =>
  publishedModels.value.find((model) => model.name === selectedPublishedName.value),
);
const selectedPool = computed(() =>
  failoverPools.value.find((pool) => pool.id === selectedPoolId.value),
);
const selectedTargetIdSet = computed(() => new Set(selectedTargetIds.value));
const selectedPublishedNameSet = computed(() => new Set(selectedPublishedNames.value));
const selectedPoolIdSet = computed(() => new Set(selectedPoolIds.value));
const allTargetsSelected = computed(() => {
  if (!targets.value.length) {
    return false;
  }
  return targets.value.every((target) => selectedTargetIdSet.value.has(target.id));
});
const allPublishedSelected = computed(() => {
  if (!publishedModels.value.length) {
    return false;
  }
  return publishedModels.value.every((model) => selectedPublishedNameSet.value.has(model.name));
});
const allPoolsSelected = computed(() => {
  if (!failoverPools.value.length) {
    return false;
  }
  return failoverPools.value.every((pool) => selectedPoolIdSet.value.has(pool.id));
});

const makeTargetModelKey = (targetId: string, upstreamModel: string) =>
  `${targetId}\u0000${upstreamModel}`;
const parseTargetModelKey = (key: string) => {
  const [targetId = "", upstreamModel = ""] = key.split("\u0000");
  return { targetId, upstreamModel };
};
const getTargetModels = (target: ModelRoutingTarget) =>
  target.upstream_models?.length ? target.upstream_models : [target.upstream_model].filter(Boolean);
const targetModelOptions = computed(() =>
  targets.value.flatMap((target) =>
    getTargetModels(target).map((model) => ({
      label: `${target.display_name || target.id} · ${model}`,
      value: makeTargetModelKey(target.id, model),
    })),
  ),
);
const poolOptions = computed(() => [
  { label: "Не использовать фейловер", value: "" },
  ...failoverPools.value.map((pool) => ({ label: pool.id, value: pool.id })),
]);
const enabledPublishedModels = computed(() =>
  publishedModels.value.filter((model) => model.enabled),
);
const hasEnabledPublishedModel = computed(() => enabledPublishedModels.value.length > 0);
const hasModelRoute = computed(() => targets.value.length > 0 && hasEnabledPublishedModel.value);
const routeSections = computed(() => [
  {
    id: "targets" as const,
    label: "Цели апстрима",
    count: targets.value.length,
    description: "Provider, Base URL, модель и API Key апстрима",
  },
  {
    id: "published" as const,
    label: "Публикуемые модели",
    count: publishedModels.value.length,
    description: "Имена, доступные даунстриму в /models и в поле model запроса",
  },
  {
    id: "failover" as const,
    label: "Пулы фейловера",
    count: failoverPools.value.length,
    description: "Резервные цели после охлаждения 429 и исчерпания сетевых повторов",
  },
]);
const routeWarnings = computed(() => {
  const messages: string[] = [];
  if (!targets.value.length) {
    messages.push("Нет целей");
  }
  if (!publishedModels.value.length) {
    messages.push("Нет публикуемых моделей");
  }
  if (publishedModels.value.length && !hasEnabledPublishedModel.value) {
    messages.push("Нет включённых публикуемых моделей");
  }
  return messages;
});

const getTargetLabel = (targetId: string) => {
  const target = targets.value.find((item) => item.id === targetId);
  return target ? target.display_name || target.id : targetId || "-";
};
const getTargetModelLabel = (targetId: string, upstreamModel: string) => {
  const targetLabel = getTargetLabel(targetId);
  return upstreamModel ? `${targetLabel} · ${upstreamModel}` : targetLabel;
};
const getPublishedPrimaryLabel = (model: PublishedModel) =>
  getTargetModelLabel(model.primary_target_id, model.primary_upstream_model);
const getPoolMemberLabel = (member: FailoverPool["members"][number]) =>
  getTargetModelLabel(member.target_id, member.upstream_model);
const isProviderId = (value: string | undefined): value is ProviderId =>
  value === "openai_chat_completion" ||
  value === "openai_response" ||
  value === "anthropic" ||
  value === "gemini";
const getProviderLabel = (provider?: string) =>
  isProviderId(provider) ? PROVIDER_LABELS[provider] : "OpenAI Chat Completion";
const activeSection = computed<RouteSectionId>({
  get: () => (activeView.value === "overview" ? "targets" : activeView.value),
  set: (value) => {
    activeView.value = value;
  },
});
const isOverview = computed(() => activeView.value === "overview");
const routePreviewTitle = computed(() => {
  if (enabledPublishedModels.value.length > 1) {
    return `Включено публикуемых моделей: ${enabledPublishedModels.value.length}`;
  }
  if (enabledPublishedModels.value.length === 1) {
    return enabledPublishedModels.value[0]?.name || "Публикуемая модель включена";
  }
  return publishedModels.value.length
    ? "Нет включённых публикуемых моделей"
    : "Модели не опубликованы";
});
const routePreviewSubtitle = computed(() => {
  if (!enabledPublishedModels.value.length) {
    return targets.value.length
      ? "После включения публикуемые модели станут доступны даунстриму"
      : "Пока нет доступных целей апстрима";
  }
  const names = enabledPublishedModels.value.map((model) => model.name);
  if (enabledPublishedModels.value.length === 1) {
    const model = enabledPublishedModels.value[0];
    const target = targets.value.find((item) => item.id === model?.primary_target_id);
    return target
      ? getTargetModelLabel(target.id, model?.primary_upstream_model || target.upstream_model)
      : "Основная цель не найдена";
  }
  const targetCount = new Set(
    enabledPublishedModels.value.map((model) => model.primary_target_id).filter(Boolean),
  ).size;
  const visibleNames = names.slice(0, 3).join(", ");
  const suffix = names.length > 3 ? ` +${names.length - 3}` : "";
  return `${visibleNames}${suffix} · основных целей: ${targetCount}`;
});
const routePreviewFailoverLabel = computed(() => {
  const poolIds = Array.from(
    new Set(
      enabledPublishedModels.value
        .map((model) => model.failover_pool_id)
        .filter((poolId): poolId is string => Boolean(poolId)),
    ),
  );
  if (!poolIds.length) {
    return "";
  }
  return poolIds.join(", ");
});
const currentSectionLabel = computed(
  () => routeSections.value.find((section) => section.id === activeSection.value)?.label || "",
);
const currentSectionDescription = computed(
  () =>
    routeSections.value.find((section) => section.id === activeSection.value)?.description || "",
);
const getDefaultMiddleRoute = (provider: ProviderId) =>
  provider === "gemini" ? GEMINI_DEFAULT_MIDDLE_ROUTE : DEFAULT_MIDDLE_ROUTE;
const normalizeApiBase = (value: string) => value.trim().replace(/\/+$/, "");
const normalizeMiddleRoute = (value: string, provider: ProviderId) => {
  let route = value.trim() || getDefaultMiddleRoute(provider);
  if (!route.startsWith("/")) {
    route = `/${route}`;
  }
  return route.length > 1 ? route.replace(/\/+$/, "") : route;
};
const formatJsonPatch = (patch: ModelRoutingTarget["request_body_patch"]) => {
  if (!patch?.length) {
    return "";
  }
  return JSON.stringify(patch, null, 2);
};
const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const normalizePatchPointer = (value: unknown) => (typeof value === "string" ? value.trim() : "");
const decodePatchPointer = (pointer: string, label: string, index: number) => {
  const tokens: string[] = [];
  for (const token of pointer.split("/").slice(1)) {
    let decoded = "";
    for (let position = 0; position < token.length; position += 1) {
      const char = token[position];
      if (char !== "~") {
        decoded += char;
        continue;
      }
      const escape = token[position + 1];
      if (escape === "0") {
        decoded += "~";
      } else if (escape === "1") {
        decoded += "/";
      } else {
        formError.value = `Редактор параметров: элемент ${index + 1}, ${label} содержит недопустимое экранирование`;
        return null;
      }
      position += 1;
    }
    tokens.push(decoded);
  }
  return tokens;
};
const validatePatchPointer = (value: unknown, label: string, index: number) => {
  const pointer = normalizePatchPointer(value);
  if (!pointer) {
    formError.value = `Редактор параметров: в элементе ${index + 1} отсутствует ${label}`;
    return null;
  }
  if (!pointer.startsWith("/")) {
    formError.value = `Редактор параметров: элемент ${index + 1}, ${label} должен начинаться с /`;
    return null;
  }
  if (pointer === "/stream" || pointer.startsWith("/stream/")) {
    formError.value = "Редактор параметров не позволяет изменять stream";
    return null;
  }
  const tokens = decodePatchPointer(pointer, label, index);
  if (tokens === null) {
    return null;
  }
  return { pointer, tokens };
};
const parseTargetRequestBodyPatch = () => {
  const source = targetForm.request_body_patch_text.trim();
  if (!source) {
    return [] as Record<string, unknown>[];
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(source);
  } catch {
    formError.value = "Редактор параметров: требуется корректный JSON";
    return null;
  }
  if (!Array.isArray(parsed)) {
    formError.value = "Редактор параметров: требуется массив JSON Patch";
    return null;
  }
  const operations: Record<string, unknown>[] = [];
  for (const [index, operation] of parsed.entries()) {
    if (!isPlainObject(operation)) {
      formError.value = `Редактор параметров: элемент ${index + 1} должен быть объектом`;
      return null;
    }
    const op = String(operation.op);
    if (!["add", "remove", "replace", "copy", "move", "test"].includes(op)) {
      formError.value = `Редактор параметров: элемент ${index + 1}, op не поддерживается`;
      return null;
    }
    const path = validatePatchPointer(operation.path, "path", index);
    if (path === null) {
      return null;
    }
    const normalizedOperation: Record<string, unknown> = {
      ...operation,
      op,
      path: path.pointer,
    };
    if (["add", "replace", "test"].includes(op) && !("value" in operation)) {
      formError.value = `Редактор параметров: в элементе ${index + 1} отсутствует value`;
      return null;
    }
    if (["copy", "move"].includes(op)) {
      const from = validatePatchPointer(operation.from, "from", index);
      if (from === null) {
        return null;
      }
      if (
        op === "move" &&
        path.tokens.length > from.tokens.length &&
        from.tokens.every((token, tokenIndex) => token === path.tokens[tokenIndex])
      ) {
        formError.value = `Редактор параметров: элемент ${index + 1} не может перемещать значение в собственный дочерний путь`;
        return null;
      }
      normalizedOperation.from = from.pointer;
    }
    operations.push(normalizedOperation);
  }
  return operations;
};
const makeIdentifier = (prefix: string, used: Set<string>) => {
  let index = used.size + 1;
  let candidate = `${prefix}-${index}`;
  while (used.has(candidate)) {
    index += 1;
    candidate = `${prefix}-${index}`;
  }
  return candidate;
};
const buildDiscoveryScope = () =>
  JSON.stringify([
    targetForm.provider,
    normalizeApiBase(targetForm.api_base),
    targetForm.api_key.trim(),
    normalizeMiddleRoute(targetForm.middle_route, targetForm.provider),
  ]);
const splitUpstreamModels = (value: string) =>
  Array.from(
    new Set(
      value
        .split(",")
        .map((model) => model.trim())
        .filter(Boolean),
    ),
  );
const getTargetFormUpstreamModels = () =>
  Array.from(new Set(selectedUpstreamModels.value.map((model) => model.trim()).filter(Boolean)));
const getTargetDiscoveryModelId = () =>
  selectedUpstreamModels.value[0] || targetForm.upstream_model.trim();
const canAddCustomUpstreamModels = computed(() =>
  splitUpstreamModels(targetForm.upstream_model).some(
    (model) => !selectedUpstreamModels.value.includes(model),
  ),
);
const availableModelSet = computed(() => new Set(availableModels.value));
const knownCustomUpstreamModels = computed(() =>
  Array.from(
    new Set([
      ...customUpstreamModelIds.value,
      ...(modelDiscoveryLoaded.value
        ? selectedUpstreamModels.value.filter((model) => !availableModelSet.value.has(model))
        : []),
    ]),
  ),
);
const customUpstreamModelSet = computed(() => new Set(knownCustomUpstreamModels.value));
const upstreamModelOptions = computed(() => {
  const customModels = knownCustomUpstreamModels.value.map((model) => ({
    value: model,
    tag: "Пользовательская",
  }));
  const selectedOnlyModels = selectedUpstreamModels.value
    .filter(
      (model) => !customUpstreamModelSet.value.has(model) && !availableModelSet.value.has(model),
    )
    .map((model) => ({
      value: model,
    }));
  const apiModels = availableModels.value.map((model) => ({
    value: model,
    disabled: customUpstreamModelSet.value.has(model),
    disabledReason: "Уже добавлена как пользовательский ID",
  }));
  return [...customModels, ...selectedOnlyModels, ...apiModels];
});
const getRememberedTargetCustomUpstreamModels = (targetId: string, upstreamModels: string[]) => {
  const upstreamModelSet = new Set(upstreamModels);
  return (targetCustomUpstreamModelIds.value[targetId] || []).filter((model) =>
    upstreamModelSet.has(model),
  );
};
const rememberTargetCustomUpstreamModels = (
  targetId: string,
  upstreamModels: string[],
  previousTargetId = targetId,
) => {
  const upstreamModelSet = new Set(upstreamModels);
  const customModels = knownCustomUpstreamModels.value.filter((model) =>
    upstreamModelSet.has(model),
  );
  const nextCustomModelsByTarget = Object.fromEntries(
    Object.entries(targetCustomUpstreamModelIds.value).filter(
      ([id]) => id !== previousTargetId && id !== targetId,
    ),
  );
  if (customModels.length) {
    nextCustomModelsByTarget[targetId] = customModels;
  }
  targetCustomUpstreamModelIds.value = nextCustomModelsByTarget;
};
const clearUpstreamModelDraft = () => {
  targetForm.upstream_model = "";
};
const addCustomUpstreamModels = (value = targetForm.upstream_model) => {
  const customModels = splitUpstreamModels(value);
  if (!customModels.length) {
    return;
  }
  selectedUpstreamModels.value = Array.from(
    new Set([...selectedUpstreamModels.value, ...customModels]),
  );
  customUpstreamModelIds.value = Array.from(
    new Set([...customModels, ...customUpstreamModelIds.value]),
  );
  clearUpstreamModelDraft();
};
const toggleUpstreamModelSelection = (model: string) => {
  const current = new Set(selectedUpstreamModels.value);
  if (current.has(model)) {
    current.delete(model);
  } else {
    current.add(model);
  }
  selectedUpstreamModels.value = Array.from(current);
  clearUpstreamModelDraft();
};
const removeSelectedUpstreamModel = (model: string) => {
  selectedUpstreamModels.value = selectedUpstreamModels.value.filter((item) => item !== model);
};
const resetTargetDiscovery = () => {
  availableModels.value = [];
  customUpstreamModelIds.value = [];
  modelDiscoveryLoaded.value = false;
  modelLoading.value = false;
  targetDiscoveryStrategy.value = "";
  targetDiscoveryScope.value = "";
};
const clearDeleteSelection = (kind: RouteSectionId) => {
  if (kind === "targets") {
    selectedTargetIds.value = [];
  } else if (kind === "published") {
    selectedPublishedNames.value = [];
  } else {
    selectedPoolIds.value = [];
  }
};
const setSectionDeleteMode = (kind: RouteSectionId, active: boolean) => {
  if (kind === "targets") {
    targetDeleteMode.value = active;
  } else if (kind === "published") {
    publishedDeleteMode.value = active;
  } else {
    poolDeleteMode.value = active;
  }
  clearDeleteSelection(kind);
};
const setItemSelected = (values: { value: string[] }, value: string, checked: boolean) => {
  const current = new Set(values.value);
  if (checked) {
    current.add(value);
  } else {
    current.delete(value);
  }
  values.value = Array.from(current);
};
const setTargetsSelected = (checked: boolean) => {
  selectedTargetIds.value = checked ? targets.value.map((target) => target.id) : [];
};
const setPublishedSelected = (checked: boolean) => {
  selectedPublishedNames.value = checked ? publishedModels.value.map((model) => model.name) : [];
};
const setPoolsSelected = (checked: boolean) => {
  selectedPoolIds.value = checked ? failoverPools.value.map((pool) => pool.id) : [];
};
const toggleTargetSelection = (targetId: string, checked: boolean) => {
  setItemSelected(selectedTargetIds, targetId, checked);
};
const togglePublishedSelection = (modelName: string, checked: boolean) => {
  setItemSelected(selectedPublishedNames, modelName, checked);
};
const togglePoolSelection = (poolId: string, checked: boolean) => {
  setItemSelected(selectedPoolIds, poolId, checked);
};
const hasTargetReference = (targetId: string) =>
  publishedModels.value.some((model) => model.primary_target_id === targetId);
const hasPoolReference = (poolId: string) =>
  publishedModels.value.some((model) => model.failover_pool_id === poolId);
const getRemovedTargetModelReferenceError = (oldId: string, nextTarget: ModelRoutingTarget) => {
  const validModels = new Set(nextTarget.upstream_models);
  const referencesByModel = new Map<string, Set<string>>();
  const addReference = (upstreamModel: string, source: string) => {
    if (!upstreamModel || validModels.has(upstreamModel)) {
      return;
    }
    const sources = referencesByModel.get(upstreamModel) || new Set<string>();
    sources.add(source);
    referencesByModel.set(upstreamModel, sources);
  };
  publishedModels.value.forEach((model) => {
    if (model.primary_target_id !== oldId && model.primary_target_id !== nextTarget.id) {
      return;
    }
    addReference(model.primary_upstream_model, `публикуемая модель ${model.name}`);
  });
  failoverPools.value.forEach((pool) => {
    pool.members.forEach((member) => {
      if (member.target_id !== oldId && member.target_id !== nextTarget.id) {
        return;
      }
      addReference(member.upstream_model, `пул фейловера ${pool.id}`);
    });
  });
  const references = Array.from(referencesByModel.entries());
  if (!references.length) {
    return "";
  }
  const details = references
    .slice(0, 3)
    .map(([upstreamModel, sources]) => {
      const visibleSources = Array.from(sources).slice(0, 3);
      const suffix = sources.size > 3 ? ` и ещё ${sources.size - 3}` : "";
      return `${upstreamModel} (${visibleSources.join(", ")}${suffix})`;
    })
    .join("; ");
  const suffix = references.length > 3 ? ` и ещё моделей: ${references.length - 3}` : "";
  return `Невозможно сохранить: модели апстрима ${details}${suffix} всё ещё используются. Сначала измените публикуемые модели или членов пула фейловера, затем удаляйте.`;
};
const isValidTargetModelKey = (key: string) => {
  const { targetId, upstreamModel } = parseTargetModelKey(key);
  const target = targets.value.find((item) => item.id === targetId);
  return Boolean(target && upstreamModel && getTargetModels(target).includes(upstreamModel));
};
const deleteConfirmOpen = ref(false);
const pendingDeleteKind = ref<"target" | "published" | "pool" | null>(null);
const pendingDeleteIds = ref<string[]>([]);
const pendingDeleteLabel = computed(() => {
  if (pendingDeleteIds.value.length > 1) {
    return `элементов: ${pendingDeleteIds.value.length}`;
  }
  if (pendingDeleteIds.value.length === 1) {
    const pendingId = pendingDeleteIds.value[0];
    if (pendingDeleteKind.value === "target") {
      const target = targets.value.find((item) => item.id === pendingId);
      return target?.display_name || pendingId;
    }
    return pendingId;
  }
  if (pendingDeleteKind.value === "target" && selectedTarget.value) {
    return selectedTarget.value.display_name || selectedTarget.value.id;
  }
  if (pendingDeleteKind.value === "published" && selectedPublishedModel.value) {
    return selectedPublishedModel.value.name;
  }
  if (pendingDeleteKind.value === "pool" && selectedPool.value) {
    return selectedPool.value.id;
  }
  return "";
});
const pendingDeleteTitle = computed(() => {
  if (pendingDeleteKind.value === "target") {
    return pendingDeleteIds.value.length > 1 ? "Массовое удаление целей" : "Удалить цель";
  }
  if (pendingDeleteKind.value === "published") {
    return pendingDeleteIds.value.length > 1
      ? "Массовое удаление публикуемых моделей"
      : "Удалить публикуемую модель";
  }
  return pendingDeleteIds.value.length > 1
    ? "Массовое удаление пулов фейловера"
    : "Удалить пул фейловера";
});
const pendingDeleteDescription = computed(() => {
  if (pendingDeleteKind.value === "target") {
    if (pendingDeleteIds.value.length > 1) {
      return "После удаления цели будут убраны из членов пулов фейловера. Цели, на которые ссылаются публикуемые модели, удалить нельзя.";
    }
    return "После удаления цель будет убрана из членов пулов фейловера. Цели, на которые ссылаются публикуемые модели, удалить нельзя.";
  }
  if (pendingDeleteKind.value === "published") {
    if (pendingDeleteIds.value.length > 1) {
      return "После удаления эти имена моделей больше не будут доступны даунстриму в /models.";
    }
    return "После удаления это имя модели больше не будет доступно даунстриму в /models.";
  }
  return "Пулы фейловера, на которые ссылаются публикуемые модели, удалить нельзя.";
});
const openDeleteConfirm = (kind: "target" | "published" | "pool", ids?: string[]) => {
  const pendingIds = Array.from(new Set((ids || []).map((id) => id.trim()).filter(Boolean)));
  if (kind === "target") {
    const targetIds = pendingIds.length
      ? pendingIds
      : selectedTarget.value
        ? [selectedTarget.value.id]
        : [];
    if (!targetIds.length) {
      return;
    }
    if (targetIds.some((targetId) => hasTargetReference(targetId))) {
      store.appendLog("Не удалось удалить цель: на неё всё ещё ссылаются публикуемые модели");
      return;
    }
    pendingDeleteIds.value = targetIds;
  }
  if (kind === "published") {
    const modelNames = pendingIds.length
      ? pendingIds
      : selectedPublishedModel.value
        ? [selectedPublishedModel.value.name]
        : [];
    if (!modelNames.length) {
      return;
    }
    pendingDeleteIds.value = modelNames;
  }
  if (kind === "pool") {
    const poolIds = pendingIds.length
      ? pendingIds
      : selectedPool.value
        ? [selectedPool.value.id]
        : [];
    if (!poolIds.length) {
      return;
    }
    if (poolIds.some((poolId) => hasPoolReference(poolId))) {
      store.appendLog(
        "Не удалось удалить пул фейловера: на него всё ещё ссылаются публикуемые модели",
      );
      return;
    }
    pendingDeleteIds.value = poolIds;
  }
  pendingDeleteKind.value = kind;
  deleteConfirmOpen.value = true;
};
const closeDeleteConfirm = () => {
  deleteConfirmOpen.value = false;
  pendingDeleteKind.value = null;
  pendingDeleteIds.value = [];
};
const openSettings = () => {
  settingsForm.mtga_auth_key = store.mtgaAuthKey.value;
  settingsForm.prompt_cache_bucket_id = store.promptCacheBucketId.value;
  settingsOpen.value = true;
};
const closeSettings = () => {
  settingsOpen.value = false;
};
const openOverview = () => {
  activeView.value = "overview";
};
const openSection = (section: RouteSectionId) => {
  activeView.value = section;
};

const openTargetEditor = (mode: "add" | "edit") => {
  editorKind.value = "target";
  editorMode.value = mode;
  formError.value = "";
  resetTargetDiscovery();
  if (mode === "edit" && selectedTarget.value) {
    const target = selectedTarget.value;
    targetForm.id = target.id;
    targetForm.display_name = target.display_name;
    targetForm.provider = target.provider;
    targetForm.api_base = target.api_base;
    selectedUpstreamModels.value = getTargetModels(target);
    customUpstreamModelIds.value = getRememberedTargetCustomUpstreamModels(
      target.id,
      selectedUpstreamModels.value,
    );
    targetForm.upstream_model = "";
    targetForm.api_key = target.api_key;
    targetForm.middle_route = target.middle_route || "";
    targetForm.prompt_cache_enabled = target.prompt_cache_enabled === true;
    targetForm.request_body_patch_text = formatJsonPatch(target.request_body_patch);
    requestBodyPatchOpen.value = Boolean(targetForm.request_body_patch_text.trim());
    targetDiscoveryStrategy.value = target.model_discovery_strategy || "";
    targetDiscoveryScope.value = buildDiscoveryScope();
  } else {
    targetForm.id = makeIdentifier("target", new Set(targets.value.map((target) => target.id)));
    targetForm.display_name = "";
    targetForm.provider = "openai_chat_completion";
    targetForm.api_base = "";
    targetForm.upstream_model = "";
    selectedUpstreamModels.value = [];
    targetForm.api_key = "";
    targetForm.middle_route = "";
    targetForm.prompt_cache_enabled = false;
    targetForm.request_body_patch_text = "";
    requestBodyPatchOpen.value = false;
  }
  editorOpen.value = true;
};

const openPublishedEditor = (mode: "add" | "edit") => {
  editorKind.value = "published";
  editorMode.value = mode;
  formError.value = "";
  if (mode === "edit" && selectedPublishedModel.value) {
    const model = selectedPublishedModel.value;
    publishedForm.name = model.name;
    publishedForm.enabled = model.enabled;
    publishedForm.primary_route_key = makeTargetModelKey(
      model.primary_target_id,
      model.primary_upstream_model,
    );
    publishedForm.failover_pool_id = model.failover_pool_id || "";
  } else {
    publishedForm.name = "";
    publishedForm.enabled = true;
    const defaultTarget =
      targets.value.find((target) => target.id === selectedTargetId.value) || targets.value[0];
    const defaultModel = defaultTarget ? getTargetModels(defaultTarget)[0] || "" : "";
    publishedForm.primary_route_key = defaultTarget
      ? makeTargetModelKey(defaultTarget.id, defaultModel)
      : "";
    publishedForm.failover_pool_id = "";
  }
  editorOpen.value = true;
};

const openPoolEditor = (mode: "add" | "edit") => {
  editorKind.value = "pool";
  editorMode.value = mode;
  formError.value = "";
  if (mode === "edit" && selectedPool.value) {
    const pool = selectedPool.value;
    poolForm.id = pool.id;
    poolForm.trigger_statuses = pool.trigger_statuses.join(", ");
    poolForm.cooldown_seconds = pool.cooldown_seconds;
    poolForm.member_keys = pool.members.map((member) =>
      makeTargetModelKey(member.target_id, member.upstream_model),
    );
  } else {
    poolForm.id = makeIdentifier(
      "failover-pool",
      new Set(failoverPools.value.map((pool) => pool.id)),
    );
    poolForm.trigger_statuses = "429";
    poolForm.cooldown_seconds = 10;
    const defaultTarget = targets.value.find((target) => target.id === selectedTargetId.value);
    const defaultModel = defaultTarget ? getTargetModels(defaultTarget)[0] || "" : "";
    poolForm.member_keys =
      defaultTarget && defaultModel ? [makeTargetModelKey(defaultTarget.id, defaultModel)] : [];
  }
  editorOpen.value = true;
};

const closeEditor = () => {
  editorOpen.value = false;
};

const persistConfig = async (successMessage: string) => {
  saving.value = true;
  try {
    const ok = await store.saveConfig();
    if (ok) {
      store.appendLog(successMessage);
      const applied = await store.runProxyApplyCurrentConfig();
      if (!applied) {
        store.appendLog(
          "Конфигурация сохранена, но работающий прокси может использовать старую маршрутизацию моделей",
        );
      }
      return true;
    }
    store.appendLog("Не удалось сохранить маршрутизацию моделей");
    return false;
  } finally {
    saving.value = false;
  }
};
const saveSettings = async () => {
  const previousAuthKey = store.mtgaAuthKey.value;
  const previousBucketId = store.promptCacheBucketId.value;
  store.mtgaAuthKey.value = settingsForm.mtga_auth_key;
  store.promptCacheBucketId.value = settingsForm.prompt_cache_bucket_id.trim();
  if (await persistConfig("Входящие настройки сохранены")) {
    closeSettings();
    return;
  }
  store.mtgaAuthKey.value = previousAuthKey;
  store.promptCacheBucketId.value = previousBucketId;
};

const saveTarget = async () => {
  const targetId = targetForm.id.trim();
  const apiBase = normalizeApiBase(targetForm.api_base);
  const upstreamModels = getTargetFormUpstreamModels();
  if (!targetId || !apiBase || !upstreamModels.length) {
    formError.value = "ID цели, API Base и модель апстрима обязательны";
    return;
  }
  if (
    targets.value.some(
      (target) =>
        target.id === targetId &&
        (editorMode.value === "add" || target.id !== selectedTargetId.value),
    )
  ) {
    formError.value = "ID цели уже существует";
    return;
  }
  const requestBodyPatch = parseTargetRequestBodyPatch();
  if (requestBodyPatch === null) {
    return;
  }
  const target: ModelRoutingTarget = {
    id: targetId,
    display_name: targetForm.display_name.trim(),
    provider: targetForm.provider,
    api_base: apiBase,
    upstream_models: upstreamModels,
    upstream_model: upstreamModels[0] || "",
    api_key: targetForm.api_key.trim(),
    middle_route: normalizeMiddleRoute(targetForm.middle_route, targetForm.provider),
    prompt_cache_enabled: targetForm.prompt_cache_enabled,
  };
  if (requestBodyPatch.length) {
    target.request_body_patch = requestBodyPatch;
  }
  if (targetDiscoveryStrategy.value && targetDiscoveryScope.value === buildDiscoveryScope()) {
    target.model_discovery_strategy = targetDiscoveryStrategy.value;
  }
  const renameTargetReferences = (oldId: string, nextId: string) => {
    if (oldId === nextId) {
      return;
    }
    publishedModels.value.forEach((model) => {
      if (model.primary_target_id === oldId) {
        model.primary_target_id = nextId;
      }
    });
    failoverPools.value.forEach((pool) => {
      pool.members.forEach((member) => {
        if (member.target_id === oldId) {
          member.target_id = nextId;
        }
      });
    });
  };
  const previousTargetId = editorMode.value === "edit" ? selectedTargetId.value : target.id;
  if (editorMode.value === "add") {
    targets.value.push(target);
  } else {
    const oldId = selectedTargetId.value;
    const referenceError = getRemovedTargetModelReferenceError(oldId, target);
    if (referenceError) {
      formError.value = referenceError;
      return;
    }
    const index = targets.value.findIndex((item) => item.id === oldId);
    if (index >= 0) {
      targets.value[index] = target;
      renameTargetReferences(oldId, target.id);
    }
  }
  selectedTargetId.value = target.id;
  if (await persistConfig(`Цель сохранена: ${target.display_name || target.id}`)) {
    rememberTargetCustomUpstreamModels(target.id, upstreamModels, previousTargetId);
    closeEditor();
  }
};

const savePublishedModel = async () => {
  const name = publishedForm.name.trim();
  const primaryRoute = parseTargetModelKey(publishedForm.primary_route_key);
  if (!name || !isValidTargetModelKey(publishedForm.primary_route_key)) {
    formError.value = "Имя публикуемой модели и основная цель обязательны";
    return;
  }
  if (
    publishedModels.value.some(
      (model) =>
        model.name === name &&
        (editorMode.value === "add" || model.name !== selectedPublishedName.value),
    )
  ) {
    formError.value = "Имя публикуемой модели уже существует";
    return;
  }
  const model: PublishedModel = {
    name,
    enabled: publishedForm.enabled,
    primary_target_id: primaryRoute.targetId,
    primary_upstream_model: primaryRoute.upstreamModel,
    failover_pool_id: publishedForm.failover_pool_id || null,
  };
  if (editorMode.value === "add") {
    publishedModels.value.push(model);
  } else {
    const index = publishedModels.value.findIndex(
      (item) => item.name === selectedPublishedName.value,
    );
    if (index >= 0) {
      publishedModels.value[index] = model;
    }
  }
  selectedPublishedName.value = model.name;
  if (await persistConfig(`Публикуемая модель сохранена: ${model.name}`)) {
    closeEditor();
  }
};

const parseStatuses = (value: string) =>
  Array.from(
    new Set(
      value
        .split(",")
        .map((item) => Number(item.trim()))
        .filter((status) => Number.isInteger(status) && status > 0),
    ),
  );

const savePool = async () => {
  const poolId = poolForm.id.trim();
  const statuses = parseStatuses(poolForm.trigger_statuses);
  if (!poolId || !statuses.length) {
    formError.value = "ID пула фейловера и коды статуса срабатывания обязательны";
    return;
  }
  if (
    failoverPools.value.some(
      (pool) =>
        pool.id === poolId && (editorMode.value === "add" || pool.id !== selectedPoolId.value),
    )
  ) {
    formError.value = "ID пула фейловера уже существует";
    return;
  }
  const pool: FailoverPool = {
    id: poolId,
    trigger_statuses: statuses,
    cooldown_seconds: Math.max(1, Number(poolForm.cooldown_seconds) || 10),
    members: poolForm.member_keys.filter(isValidTargetModelKey).map((key) => {
      const { targetId, upstreamModel } = parseTargetModelKey(key);
      return { target_id: targetId, upstream_model: upstreamModel };
    }),
  };
  if (editorMode.value === "add") {
    failoverPools.value.push(pool);
  } else {
    const oldId = selectedPoolId.value;
    const index = failoverPools.value.findIndex((item) => item.id === oldId);
    if (index >= 0) {
      failoverPools.value[index] = pool;
      if (oldId !== pool.id) {
        publishedModels.value.forEach((model) => {
          if (model.failover_pool_id === oldId) {
            model.failover_pool_id = pool.id;
          }
        });
      }
    }
  }
  selectedPoolId.value = pool.id;
  if (await persistConfig(`Пул фейловера сохранён: ${pool.id}`)) {
    closeEditor();
  }
};

const handleEditorSave = () => {
  if (saving.value) {
    return;
  }
  if (editorKind.value === "target") {
    void saveTarget();
  } else if (editorKind.value === "published") {
    void savePublishedModel();
  } else {
    void savePool();
  }
};

const deleteTargetsByIds = async (targetIds: string[]) => {
  const normalizedIds = Array.from(new Set(targetIds.filter(Boolean)));
  if (!normalizedIds.length || saving.value) {
    return false;
  }
  if (normalizedIds.some((targetId) => hasTargetReference(targetId))) {
    store.appendLog("Не удалось удалить цель: на неё всё ещё ссылаются публикуемые модели");
    return false;
  }
  const deletingSet = new Set(normalizedIds);
  const deletingTargets = targets.value.filter((target) => deletingSet.has(target.id));
  if (!deletingTargets.length) {
    return false;
  }
  const previousTargets = [...targets.value];
  const previousPools = failoverPools.value.map((pool) => ({
    ...pool,
    members: pool.members.map((member) => ({ ...member })),
  }));
  const previousSelectedTargetId = selectedTargetId.value;
  targets.value = targets.value.filter((item) => !deletingSet.has(item.id));
  failoverPools.value.forEach((pool) => {
    pool.members = pool.members.filter((member) => !deletingSet.has(member.target_id));
  });
  selectedTargetId.value = targets.value[0]?.id || "";
  const successMessage =
    deletingTargets.length === 1
      ? `Цель удалена: ${deletingTargets[0]?.display_name || deletingTargets[0]?.id || ""}`
      : `Удалено целей: ${deletingTargets.length}`;
  if (await persistConfig(successMessage)) {
    selectedTargetIds.value = selectedTargetIds.value.filter(
      (targetId) => !deletingSet.has(targetId),
    );
    if (!targets.value.length) {
      setSectionDeleteMode("targets", false);
    }
    return true;
  }
  targets.value = previousTargets;
  failoverPools.value = previousPools;
  selectedTargetId.value = previousSelectedTargetId;
  return false;
};

const deletePublishedByNames = async (modelNames: string[]) => {
  const normalizedNames = Array.from(new Set(modelNames.filter(Boolean)));
  if (!normalizedNames.length || saving.value) {
    return false;
  }
  const deletingSet = new Set(normalizedNames);
  const deletingModels = publishedModels.value.filter((model) => deletingSet.has(model.name));
  if (!deletingModels.length) {
    return false;
  }
  const previousPublishedModels = [...publishedModels.value];
  const previousSelectedPublishedName = selectedPublishedName.value;
  publishedModels.value = publishedModels.value.filter((item) => !deletingSet.has(item.name));
  selectedPublishedName.value = publishedModels.value[0]?.name || "";
  const successMessage =
    deletingModels.length === 1
      ? `Публикуемая модель удалена: ${deletingModels[0]?.name || ""}`
      : `Удалено публикуемых моделей: ${deletingModels.length}`;
  if (await persistConfig(successMessage)) {
    selectedPublishedNames.value = selectedPublishedNames.value.filter(
      (modelName) => !deletingSet.has(modelName),
    );
    if (!publishedModels.value.length) {
      setSectionDeleteMode("published", false);
    }
    return true;
  }
  publishedModels.value = previousPublishedModels;
  selectedPublishedName.value = previousSelectedPublishedName;
  return false;
};

const deletePoolsByIds = async (poolIds: string[]) => {
  const normalizedIds = Array.from(new Set(poolIds.filter(Boolean)));
  if (!normalizedIds.length || saving.value) {
    return false;
  }
  if (normalizedIds.some((poolId) => hasPoolReference(poolId))) {
    store.appendLog(
      "Не удалось удалить пул фейловера: на него всё ещё ссылаются публикуемые модели",
    );
    return false;
  }
  const deletingSet = new Set(normalizedIds);
  const deletingPools = failoverPools.value.filter((pool) => deletingSet.has(pool.id));
  if (!deletingPools.length) {
    return false;
  }
  const previousPools = [...failoverPools.value];
  const previousSelectedPoolId = selectedPoolId.value;
  failoverPools.value = failoverPools.value.filter((item) => !deletingSet.has(item.id));
  selectedPoolId.value = failoverPools.value[0]?.id || "";
  const successMessage =
    deletingPools.length === 1
      ? `Пул фейловера удалён: ${deletingPools[0]?.id || ""}`
      : `Удалено пулов фейловера: ${deletingPools.length}`;
  if (await persistConfig(successMessage)) {
    selectedPoolIds.value = selectedPoolIds.value.filter((poolId) => !deletingSet.has(poolId));
    if (!failoverPools.value.length) {
      setSectionDeleteMode("failover", false);
    }
    return true;
  }
  failoverPools.value = previousPools;
  selectedPoolId.value = previousSelectedPoolId;
  return false;
};

const confirmDelete = async () => {
  const kind = pendingDeleteKind.value;
  if (!kind || saving.value) {
    return;
  }
  const ids = pendingDeleteIds.value;
  const ok =
    kind === "target"
      ? await deleteTargetsByIds(ids)
      : kind === "published"
        ? await deletePublishedByNames(ids)
        : await deletePoolsByIds(ids);
  if (ok) {
    closeDeleteConfirm();
  }
};

const refreshConfig = async () => {
  if (refreshing.value) {
    return;
  }
  refreshing.value = true;
  try {
    if (await store.loadConfig()) {
      store.appendLog("Маршрутизация моделей обновлена");
    }
  } finally {
    refreshing.value = false;
  }
};

const testSelectedTarget = async () => {
  const target = selectedTarget.value;
  if (!target || targetTesting.value) {
    return;
  }
  targetTesting.value = true;
  try {
    await store.runTargetTest(target.id);
  } finally {
    targetTesting.value = false;
  }
};

const fetchTargetModels = async () => {
  if (modelLoading.value) {
    return;
  }
  const apiBase = normalizeApiBase(targetForm.api_base);
  if (!apiBase) {
    store.appendLog("Не удалось получить список моделей: API Base пуст");
    return;
  }
  modelLoading.value = true;
  const requestPayload = {
    provider: targetForm.provider,
    api_url: apiBase,
    api_key: targetForm.api_key.trim(),
    model_id: getTargetDiscoveryModelId(),
    middle_route: normalizeMiddleRoute(targetForm.middle_route, targetForm.provider),
  };
  const result = await store.fetchTargetModels(requestPayload);
  if (result) {
    availableModels.value = result.models;
    modelDiscoveryLoaded.value = true;
    targetDiscoveryStrategy.value = result.strategyId || "";
    targetDiscoveryScope.value = buildDiscoveryScope();
  }
  modelLoading.value = false;
};

const togglePoolMember = (targetModelKey: string, checked: boolean) => {
  const current = new Set(poolForm.member_keys);
  if (checked) {
    current.add(targetModelKey);
  } else {
    current.delete(targetModelKey);
  }
  poolForm.member_keys = Array.from(current);
};

watch(
  targets,
  (nextTargets) => {
    const validIds = new Set(nextTargets.map((target) => target.id));
    selectedTargetIds.value = selectedTargetIds.value.filter((targetId) => validIds.has(targetId));
    if (!nextTargets.length && targetDeleteMode.value) {
      setSectionDeleteMode("targets", false);
    }
    if (
      !selectedTargetId.value ||
      !nextTargets.some((target) => target.id === selectedTargetId.value)
    ) {
      selectedTargetId.value = nextTargets[0]?.id || "";
    }
  },
  { immediate: true, deep: true },
);

watch(
  publishedModels,
  (nextModels) => {
    const validNames = new Set(nextModels.map((model) => model.name));
    selectedPublishedNames.value = selectedPublishedNames.value.filter((modelName) =>
      validNames.has(modelName),
    );
    if (!nextModels.length && publishedDeleteMode.value) {
      setSectionDeleteMode("published", false);
    }
    if (
      !selectedPublishedName.value ||
      !nextModels.some((model) => model.name === selectedPublishedName.value)
    ) {
      selectedPublishedName.value = nextModels[0]?.name || "";
    }
  },
  { immediate: true, deep: true },
);

watch(
  failoverPools,
  (nextPools) => {
    const validIds = new Set(nextPools.map((pool) => pool.id));
    selectedPoolIds.value = selectedPoolIds.value.filter((poolId) => validIds.has(poolId));
    if (!nextPools.length && poolDeleteMode.value) {
      setSectionDeleteMode("failover", false);
    }
    if (!selectedPoolId.value || !nextPools.some((pool) => pool.id === selectedPoolId.value)) {
      selectedPoolId.value = nextPools[0]?.id || "";
    }
  },
  { immediate: true, deep: true },
);

watch(
  () => targetForm.provider,
  (provider, previous) => {
    if (!previous || targetForm.middle_route.trim() !== getDefaultMiddleRoute(previous)) {
      return;
    }
    targetForm.middle_route = getDefaultMiddleRoute(provider);
  },
);
</script>

<template>
  <div class="flex h-full min-h-0 flex-col gap-3">
    <div class="flex shrink-0 flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="mtga-card-title">Маршрутизация моделей</h2>
        <p class="mtga-card-subtitle">
          Управление входящими моделями MTGA, целями апстрима и фейловером
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-2">
        <span
          class="rounded-full border px-3 py-1 text-xs font-bold"
          :class="
            hasModelRoute
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
              : 'border-amber-200 bg-amber-50 text-amber-700'
          "
        >
          {{
            hasModelRoute ? "Готово к запуску" : routeWarnings.join(" / ") || "Требует настройки"
          }}
        </span>
      </div>
    </div>

    <section
      v-if="isOverview"
      class="flex min-h-0 flex-1 flex-col gap-3 overflow-auto pr-1 custom-scrollbar"
    >
      <div class="rounded-xl border border-slate-200/70 bg-white/60 p-4">
        <div>
          <div class="min-w-0">
            <div class="flex items-center gap-1.5 text-xs font-bold uppercase text-slate-400">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
              </svg>
              Обзор маршрутов
            </div>
            <div class="mt-1 truncate text-base font-semibold text-slate-900">
              {{ routePreviewTitle }}
            </div>
            <div class="mt-1 truncate text-sm text-slate-500">
              {{ routePreviewSubtitle }}
            </div>
          </div>
        </div>

        <div class="mt-4 grid grid-cols-3 gap-2">
          <div
            class="rounded-lg border border-slate-200/70 bg-slate-50/70 px-3 py-2 flex flex-col justify-between"
          >
            <div class="flex items-center gap-1.5 text-[11px] font-semibold text-slate-500">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <circle cx="12" cy="12" r="10"></circle>
                <circle cx="12" cy="12" r="6"></circle>
                <circle cx="12" cy="12" r="2"></circle>
              </svg>
              Цели апстрима
            </div>
            <div class="mt-1 font-mono text-lg font-bold text-slate-900">{{ targets.length }}</div>
          </div>
          <div
            class="rounded-lg border border-slate-200/70 bg-slate-50/70 px-3 py-2 flex flex-col justify-between"
          >
            <div class="flex items-center gap-1.5 text-[11px] font-semibold text-slate-500">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path
                  d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"
                ></path>
                <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                <line x1="12" y1="22.08" x2="12" y2="12"></line>
              </svg>
              Публикуемые модели
            </div>
            <div class="mt-1 font-mono text-lg font-bold text-slate-900">
              {{ publishedModels.length }}
            </div>
          </div>
          <div
            class="rounded-lg border border-slate-200/70 bg-slate-50/70 px-3 py-2 flex flex-col justify-between"
          >
            <div class="flex items-center gap-1.5 text-[11px] font-semibold text-slate-500">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M2 12h5"></path>
                <path d="M17 12h5"></path>
                <path d="M12 2v5"></path>
                <path d="M12 17v5"></path>
                <path d="m19 5-3.5 3.5"></path>
                <path d="m5 19 3.5-3.5"></path>
                <path d="m5 5 3.5 3.5"></path>
                <path d="m19 19-3.5-3.5"></path>
              </svg>
              Пулы фейловера
            </div>
            <div class="mt-1 font-mono text-lg font-bold text-slate-900">
              {{ failoverPools.length }}
            </div>
          </div>
        </div>

        <div v-if="routePreviewFailoverLabel || routeWarnings.length" class="mt-3 grid gap-2">
          <span
            v-if="routePreviewFailoverLabel"
            class="rounded-lg border border-slate-200/70 bg-slate-50/70 px-3 py-2 text-xs font-semibold text-slate-600"
          >
            Включённые пулы фейловера: {{ routePreviewFailoverLabel }}
          </span>
          <span
            v-for="warning in routeWarnings"
            :key="warning"
            class="rounded-lg border border-amber-200/70 bg-amber-50/70 px-3 py-2 text-xs font-semibold text-amber-700"
          >
            {{ warning }}
          </span>
        </div>
      </div>

      <div class="grid gap-2">
        <button
          v-for="section in routeSections"
          :key="section.id"
          class="group flex w-full cursor-pointer items-center justify-between gap-3 rounded-xl border border-slate-200/70 bg-white/55 px-4 py-3 text-left transition hover:border-amber-300 hover:bg-amber-50/70"
          @click="openSection(section.id)"
        >
          <span class="min-w-0">
            <span class="block text-sm font-bold text-slate-800">{{ section.label }}</span>
            <span class="block truncate text-xs text-slate-500">{{ section.description }}</span>
          </span>
          <span class="flex shrink-0 items-center gap-3">
            <span class="font-mono text-lg font-bold text-slate-900">{{ section.count }}</span>
            <span
              class="flex items-center text-xs font-bold text-amber-600 transition-transform group-hover:translate-x-0.5 group-hover:text-amber-700"
            >
              Управлять
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="ml-0.5"
              >
                <path d="m9 18 6-6-6-6" />
              </svg>
            </span>
          </span>
        </button>
      </div>

      <div class="grid grid-cols-2 gap-2">
        <button
          class="btn btn-sm rounded-xl border border-slate-200 bg-white/65 text-slate-700 hover:border-amber-300 hover:bg-amber-50"
          @click="openSettings"
        >
          Входящие настройки
        </button>
        <button
          class="btn btn-sm rounded-xl border border-slate-200 bg-white/65 text-slate-700 hover:border-amber-300 hover:bg-amber-50"
          :class="refreshing ? 'loading' : ''"
          :disabled="refreshing || saving"
          @click="refreshConfig"
        >
          Обновить конфигурацию
        </button>
      </div>
    </section>

    <section
      v-else
      class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200/70 bg-white/55"
    >
      <div class="shrink-0 border-b border-slate-200/70 bg-slate-50/70 px-4 py-3">
        <div class="flex items-start justify-between gap-3">
          <div class="flex min-w-0 items-start gap-3">
            <button
              class="btn btn-xs rounded-lg border border-slate-200 bg-white text-slate-600 hover:border-amber-300 hover:bg-amber-50"
              @click="openOverview"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="-ml-0.5"
              >
                <path d="m15 18-6-6 6-6" />
              </svg>
              Назад
            </button>
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <h3 class="truncate text-sm font-bold text-slate-900">{{ currentSectionLabel }}</h3>
                <span class="font-mono text-xs font-bold text-slate-500">
                  {{ routeSections.find((section) => section.id === activeSection)?.count || 0 }}
                </span>
              </div>
              <p class="mt-0.5 line-clamp-2 text-xs text-slate-500">
                {{ currentSectionDescription }}
              </p>
            </div>
          </div>
          <div class="flex shrink-0 flex-wrap justify-end gap-2">
            <template v-if="activeSection === 'targets'">
              <button
                class="btn btn-xs btn-primary min-w-12 rounded-lg"
                :disabled="targetDeleteMode"
                @click="openTargetEditor('add')"
              >
                Добавить
              </button>
              <button
                class="btn btn-xs min-w-12 rounded-lg border border-slate-200 bg-white text-slate-700 hover:border-amber-300 hover:bg-amber-50"
                :disabled="targetDeleteMode || !selectedTarget"
                @click="openTargetEditor('edit')"
              >
                Изменить
              </button>
              <button
                class="btn btn-xs min-w-12 rounded-lg border border-slate-200 bg-white text-slate-700 transition-[background-color,border-color,color,width] hover:border-amber-300 hover:bg-amber-50"
                :class="targetTesting ? 'w-19' : 'w-12'"
                :aria-busy="targetTesting"
                :disabled="targetDeleteMode || !selectedTarget || targetTesting"
                @click="testSelectedTarget"
              >
                <span
                  v-if="targetTesting"
                  class="h-3 w-3 animate-spin rounded-full border-2 border-amber-500/25 border-t-amber-600"
                  aria-hidden="true"
                ></span>
                <span>{{ targetTesting ? "Проверка..." : "Проверка" }}</span>
              </button>
              <MtgaBulkDeleteControls
                v-model:active="targetDeleteMode"
                :busy="saving"
                size="xs"
                :total-count="targets.length"
                button-width-class="min-w-12"
                @update:active="clearDeleteSelection('targets')"
              />
            </template>
            <template v-else-if="activeSection === 'published'">
              <button
                class="btn btn-xs btn-primary min-w-12 rounded-lg"
                :disabled="publishedDeleteMode || !targets.length"
                @click="openPublishedEditor('add')"
              >
                Добавить
              </button>
              <button
                class="btn btn-xs min-w-12 rounded-lg border border-slate-200 bg-white text-slate-700 hover:border-amber-300 hover:bg-amber-50"
                :disabled="publishedDeleteMode || !selectedPublishedModel"
                @click="openPublishedEditor('edit')"
              >
                Изменить
              </button>
              <MtgaBulkDeleteControls
                v-model:active="publishedDeleteMode"
                :busy="saving"
                size="xs"
                :total-count="publishedModels.length"
                button-width-class="min-w-12"
                @update:active="clearDeleteSelection('published')"
              />
            </template>
            <template v-else>
              <button
                class="btn btn-xs btn-primary min-w-12 rounded-lg"
                :disabled="poolDeleteMode || !targets.length"
                @click="openPoolEditor('add')"
              >
                Добавить
              </button>
              <button
                class="btn btn-xs min-w-12 rounded-lg border border-slate-200 bg-white text-slate-700 hover:border-amber-300 hover:bg-amber-50"
                :disabled="poolDeleteMode || !selectedPool"
                @click="openPoolEditor('edit')"
              >
                Изменить
              </button>
              <MtgaBulkDeleteControls
                v-model:active="poolDeleteMode"
                :busy="saving"
                size="xs"
                :total-count="failoverPools.length"
                button-width-class="min-w-12"
                @update:active="clearDeleteSelection('failover')"
              />
            </template>
          </div>
        </div>
      </div>

      <div class="min-h-0 flex-1 overflow-auto custom-scrollbar">
        <div v-if="activeSection === 'targets'" class="divide-y divide-slate-200/70">
          <MtgaBulkDeleteControls
            variant="selection"
            :active="targetDeleteMode"
            :all-selected="allTargetsSelected"
            :busy="saving"
            item-label="целей"
            :selected-count="selectedTargetIds.length"
            :total-count="targets.length"
            @delete-selected="openDeleteConfirm('target', selectedTargetIds)"
            @select-all-change="setTargetsSelected"
          />
          <template v-if="targetDeleteMode">
            <label
              v-for="target in targets"
              :key="target.id"
              class="flex cursor-pointer items-start gap-3 px-4 py-3 transition-colors hover:bg-amber-50/70"
            >
              <input
                type="checkbox"
                class="checkbox checkbox-xs mt-1 rounded border-slate-300 [--chkbg:var(--color-amber-500)] [--chkfg:white]"
                :checked="selectedTargetIdSet.has(target.id)"
                :disabled="saving"
                @change="
                  toggleTargetSelection(target.id, ($event.target as HTMLInputElement).checked)
                "
              />
              <div class="min-w-0 flex-1">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="truncate text-sm font-bold text-slate-900">
                      {{ target.display_name || target.id }}
                    </div>
                    <div class="mt-1 truncate font-mono text-xs text-slate-500">
                      {{ target.id }}
                    </div>
                  </div>
                  <span
                    class="shrink-0 rounded-full border border-slate-200 bg-white/80 px-2 py-0.5 text-[11px] font-semibold text-slate-600"
                  >
                    {{ getProviderLabel(target.provider) }}
                  </span>
                </div>
                <div class="mt-2 grid gap-1 text-xs text-slate-500">
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="model in getTargetModels(target)"
                      :key="model"
                      :class="MODEL_PREVIEW_CHIP_CLASS"
                    >
                      {{ model }}
                    </span>
                    <span v-if="!getTargetModels(target).length" :class="MODEL_PREVIEW_CHIP_CLASS">
                      -
                    </span>
                  </div>
                  <div class="truncate font-mono">{{ target.api_base }}</div>
                </div>
              </div>
              <button
                type="button"
                class="btn btn-ghost btn-xs btn-circle h-7 min-h-7 w-7 text-slate-300 transition-colors hover:bg-rose-50 hover:text-rose-600"
                :disabled="saving"
                @click.stop.prevent="openDeleteConfirm('target', [target.id])"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  class="h-3.5 w-3.5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </label>
          </template>
          <template v-else>
            <button
              v-for="target in targets"
              :key="target.id"
              class="w-full cursor-pointer px-4 py-3 text-left"
              :class="selectedTargetId === target.id ? 'bg-amber-100/70' : 'hover:bg-amber-50/70'"
              @click="selectedTargetId = target.id"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="truncate text-sm font-bold text-slate-900">
                    {{ target.display_name || target.id }}
                  </div>
                  <div class="mt-1 truncate font-mono text-xs text-slate-500">{{ target.id }}</div>
                </div>
                <span
                  class="shrink-0 rounded-full border border-slate-200 bg-white/80 px-2 py-0.5 text-[11px] font-semibold text-slate-600"
                >
                  {{ getProviderLabel(target.provider) }}
                </span>
              </div>
              <div class="mt-2 grid gap-1 text-xs text-slate-500">
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="model in getTargetModels(target)"
                    :key="model"
                    :class="MODEL_PREVIEW_CHIP_CLASS"
                  >
                    {{ model }}
                  </span>
                  <span v-if="!getTargetModels(target).length" :class="MODEL_PREVIEW_CHIP_CLASS">
                    -
                  </span>
                </div>
                <div class="truncate font-mono">{{ target.api_base }}</div>
              </div>
            </button>
          </template>
          <div
            v-if="!targets.length"
            class="flex flex-col items-center justify-center px-4 py-12 text-center"
          >
            <div class="rounded-full bg-slate-100/60 p-3 text-slate-400">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <circle cx="12" cy="12" r="10"></circle>
                <circle cx="12" cy="12" r="6"></circle>
                <circle cx="12" cy="12" r="2"></circle>
              </svg>
            </div>
            <div class="mt-3 text-sm font-medium text-slate-500">Нет целей</div>
            <div class="mt-1 text-xs text-slate-400">
              Настройте провайдера апстрима, API Key и модели
            </div>
            <button class="btn btn-sm btn-primary mt-4 rounded-xl" @click="openTargetEditor('add')">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M5 12h14" />
                <path d="M12 5v14" />
              </svg>
              Добавить Target
            </button>
          </div>
        </div>

        <div v-else-if="activeSection === 'published'" class="divide-y divide-slate-200/70">
          <MtgaBulkDeleteControls
            variant="selection"
            :active="publishedDeleteMode"
            :all-selected="allPublishedSelected"
            :busy="saving"
            item-label="моделей"
            :selected-count="selectedPublishedNames.length"
            :total-count="publishedModels.length"
            @delete-selected="openDeleteConfirm('published', selectedPublishedNames)"
            @select-all-change="setPublishedSelected"
          />
          <template v-if="publishedDeleteMode">
            <label
              v-for="model in publishedModels"
              :key="model.name"
              class="flex cursor-pointer items-start gap-3 px-4 py-3 transition-colors hover:bg-amber-50/70"
            >
              <input
                type="checkbox"
                class="checkbox checkbox-xs mt-1 rounded border-slate-300 [--chkbg:var(--color-amber-500)] [--chkfg:white]"
                :checked="selectedPublishedNameSet.has(model.name)"
                :disabled="saving"
                @change="
                  togglePublishedSelection(model.name, ($event.target as HTMLInputElement).checked)
                "
              />
              <div class="min-w-0 flex-1">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="truncate font-mono text-sm font-bold text-slate-900">
                      {{ model.name }}
                    </div>
                    <div class="mt-1 truncate text-xs text-slate-500">
                      Основная цель: {{ getPublishedPrimaryLabel(model) }}
                    </div>
                  </div>
                  <span
                    class="shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-bold"
                    :class="
                      model.enabled
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                        : 'border-slate-200 bg-slate-100 text-slate-500'
                    "
                  >
                    {{ model.enabled ? "Включена" : "Отключена" }}
                  </span>
                </div>
                <div class="mt-2 truncate font-mono text-xs text-slate-500">
                  Фейловер: {{ model.failover_pool_id || "-" }}
                </div>
              </div>
              <button
                type="button"
                class="btn btn-ghost btn-xs btn-circle h-7 min-h-7 w-7 text-slate-300 transition-colors hover:bg-rose-50 hover:text-rose-600"
                :disabled="saving"
                @click.stop.prevent="openDeleteConfirm('published', [model.name])"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  class="h-3.5 w-3.5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </label>
          </template>
          <template v-else>
            <button
              v-for="model in publishedModels"
              :key="model.name"
              class="w-full cursor-pointer px-4 py-3 text-left"
              :class="
                selectedPublishedName === model.name ? 'bg-amber-100/70' : 'hover:bg-amber-50/70'
              "
              @click="selectedPublishedName = model.name"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="truncate font-mono text-sm font-bold text-slate-900">
                    {{ model.name }}
                  </div>
                  <div class="mt-1 flex flex-wrap items-center gap-1 text-xs text-slate-500">
                    <span>Основная цель:</span>
                    <span :class="MODEL_PREVIEW_CHIP_CLASS">
                      {{ getPublishedPrimaryLabel(model) }}
                    </span>
                  </div>
                </div>
                <span
                  class="shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-bold"
                  :class="
                    model.enabled
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                      : 'border-slate-200 bg-slate-100 text-slate-500'
                  "
                >
                  {{ model.enabled ? "Включена" : "Отключена" }}
                </span>
              </div>
              <div class="mt-2 flex flex-wrap items-center gap-1 text-xs text-slate-500">
                <span>Фейловер:</span>
                <span :class="MODEL_PREVIEW_CHIP_CLASS">
                  {{ model.failover_pool_id || "-" }}
                </span>
              </div>
            </button>
          </template>
          <div
            v-if="!publishedModels.length"
            class="flex flex-col items-center justify-center px-4 py-12 text-center"
          >
            <div class="rounded-full bg-slate-100/60 p-3 text-slate-400">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path
                  d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"
                ></path>
                <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                <line x1="12" y1="22.08" x2="12" y2="12"></line>
              </svg>
            </div>
            <div class="mt-3 text-sm font-medium text-slate-500">
              Нет публикуемых моделей (Published)
            </div>
            <div class="mt-1 text-xs text-slate-400">
              Определите имена моделей для клиентов и основной маршрут
            </div>
            <button
              class="btn btn-sm btn-primary mt-4 rounded-xl"
              :disabled="!targets.length"
              @click="openPublishedEditor('add')"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M5 12h14" />
                <path d="M12 5v14" />
              </svg>
              Добавить Published
            </button>
          </div>
        </div>

        <div v-else class="divide-y divide-slate-200/70">
          <MtgaBulkDeleteControls
            variant="selection"
            :active="poolDeleteMode"
            :all-selected="allPoolsSelected"
            :busy="saving"
            item-label="пулов фейловера"
            :selected-count="selectedPoolIds.length"
            :total-count="failoverPools.length"
            @delete-selected="openDeleteConfirm('pool', selectedPoolIds)"
            @select-all-change="setPoolsSelected"
          />
          <template v-if="poolDeleteMode">
            <label
              v-for="pool in failoverPools"
              :key="pool.id"
              class="flex cursor-pointer items-start gap-3 px-4 py-3 transition-colors hover:bg-amber-50/70"
            >
              <input
                type="checkbox"
                class="checkbox checkbox-xs mt-1 rounded border-slate-300 [--chkbg:var(--color-amber-500)] [--chkfg:white]"
                :checked="selectedPoolIdSet.has(pool.id)"
                :disabled="saving"
                @change="togglePoolSelection(pool.id, ($event.target as HTMLInputElement).checked)"
              />
              <div class="min-w-0 flex-1">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="truncate font-mono text-sm font-bold text-slate-900">
                      {{ pool.id }}
                    </div>
                    <div class="mt-1 truncate text-xs text-slate-500">
                      Участников: {{ pool.members.length }}
                    </div>
                  </div>
                  <span
                    class="shrink-0 rounded-full border border-slate-200 bg-white/80 px-2 py-0.5 font-mono text-[11px] font-semibold text-slate-600"
                  >
                    {{ pool.cooldown_seconds }}s
                  </span>
                </div>
                <div class="mt-2 grid gap-1 text-xs text-slate-500">
                  <div>Коды статуса {{ pool.trigger_statuses.join(", ") }}</div>
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="member in pool.members"
                      :key="makeTargetModelKey(member.target_id, member.upstream_model)"
                      :class="MODEL_PREVIEW_CHIP_CLASS"
                    >
                      {{ getPoolMemberLabel(member) }}
                    </span>
                    <span v-if="!pool.members.length" :class="MODEL_PREVIEW_CHIP_CLASS"> - </span>
                  </div>
                </div>
              </div>
              <button
                type="button"
                class="btn btn-ghost btn-xs btn-circle h-7 min-h-7 w-7 text-slate-300 transition-colors hover:bg-rose-50 hover:text-rose-600"
                :disabled="saving"
                @click.stop.prevent="openDeleteConfirm('pool', [pool.id])"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  class="h-3.5 w-3.5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            </label>
          </template>
          <template v-else>
            <button
              v-for="pool in failoverPools"
              :key="pool.id"
              class="w-full cursor-pointer px-4 py-3 text-left"
              :class="selectedPoolId === pool.id ? 'bg-amber-100/70' : 'hover:bg-amber-50/70'"
              @click="selectedPoolId = pool.id"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <div class="truncate font-mono text-sm font-bold text-slate-900">
                    {{ pool.id }}
                  </div>
                  <div class="mt-1 truncate text-xs text-slate-500">
                    Участников: {{ pool.members.length }}
                  </div>
                </div>
                <span
                  class="shrink-0 rounded-full border border-slate-200 bg-white/80 px-2 py-0.5 font-mono text-[11px] font-semibold text-slate-600"
                >
                  {{ pool.cooldown_seconds }}s
                </span>
              </div>
              <div class="mt-2 grid gap-1 text-xs text-slate-500">
                <div>Коды статуса {{ pool.trigger_statuses.join(", ") }}</div>
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="member in pool.members"
                    :key="makeTargetModelKey(member.target_id, member.upstream_model)"
                    :class="MODEL_PREVIEW_CHIP_CLASS"
                  >
                    {{ getPoolMemberLabel(member) }}
                  </span>
                  <span v-if="!pool.members.length" :class="MODEL_PREVIEW_CHIP_CLASS"> - </span>
                </div>
              </div>
            </button>
          </template>
          <div
            v-if="!failoverPools.length"
            class="flex flex-col items-center justify-center px-4 py-12 text-center"
          >
            <div class="rounded-full bg-slate-100/60 p-3 text-slate-400">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M2 12h5"></path>
                <path d="M17 12h5"></path>
                <path d="M12 2v5"></path>
                <path d="M12 17v5"></path>
                <path d="m19 5-3.5 3.5"></path>
                <path d="m5 19 3.5-3.5"></path>
                <path d="m5 5 3.5 3.5"></path>
                <path d="m19 19-3.5-3.5"></path>
              </svg>
            </div>
            <div class="mt-3 text-sm font-medium text-slate-500">Нет пулов фейловера (Pools)</div>
            <div class="mt-1 text-xs text-slate-400">
              Настройте резервные цели для автоматического повтора при сбое апстрима
            </div>
            <button
              class="btn btn-sm btn-primary mt-4 rounded-xl"
              :disabled="!targets.length"
              @click="openPoolEditor('add')"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M5 12h14" />
                <path d="M12 5v14" />
              </svg>
              Добавить Pool
            </button>
          </div>
        </div>
      </div>
    </section>

    <MtgaDialog
      v-model:open="editorOpen"
      :max-width="editorKind === 'target' ? 'max-w-4xl' : 'max-w-2xl'"
      @close="closeEditor"
    >
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <div>
            <h3 class="text-lg font-semibold text-slate-900">
              {{
                editorKind === "target"
                  ? editorMode === "add"
                    ? "Новая цель"
                    : "Изменение цели"
                  : editorKind === "published"
                    ? editorMode === "add"
                      ? "Новая публикуемая модель"
                      : "Изменение публикуемой модели"
                    : editorMode === "add"
                      ? "Новый пул фейловера"
                      : "Изменение пула фейловера"
              }}
            </h3>
            <p class="text-xs text-slate-500">
              После сохранения записывается в конфигурацию маршрутизации моделей
            </p>
          </div>
        </div>
      </template>

      <div class="px-6 py-6">
        <div v-if="editorKind === 'target'" class="space-y-4">
          <div class="grid gap-4 md:grid-cols-2">
            <MtgaInput
              v-model="targetForm.id"
              label="Target ID"
              required
              readonly
              input-class="cursor-default text-slate-500"
              placeholder="target-1"
            />
            <MtgaInput
              v-model="targetForm.display_name"
              label="Отображаемое имя"
              placeholder="Claude основная линия"
            />
            <MtgaSelect
              v-model="targetForm.provider"
              label="Provider"
              required
              :options="PROVIDER_OPTIONS"
              class="w-full"
            />
            <MtgaInput
              v-model="targetForm.api_base"
              label="API Base"
              required
              placeholder="https://api.openai.com"
            />
            <div class="space-y-1">
              <MtgaInput
                v-model="targetForm.upstream_model"
                label="Модель апстрима"
                required
                show-dropdown
                multi-select
                show-add-option
                add-option-hint="Нажмите, чтобы добавить ID"
                :options="upstreamModelOptions"
                :selected-options="selectedUpstreamModels"
                :add-option-value="targetForm.upstream_model.trim()"
                :add-option-disabled="!canAddCustomUpstreamModels"
                :loading="modelLoading"
                placeholder="gpt-5"
                @add-option="addCustomUpstreamModels"
                @dropdown="fetchTargetModels"
                @select="toggleUpstreamModelSelection"
              />
              <div v-if="selectedUpstreamModels.length" class="flex flex-wrap gap-1">
                <button
                  v-for="model in selectedUpstreamModels"
                  :key="model"
                  type="button"
                  class="cursor-pointer rounded-md border border-slate-200 bg-white px-1.5 py-0.5 font-mono text-[10px] text-slate-500 hover:border-amber-300 hover:bg-amber-50 hover:text-amber-700"
                  @click="removeSelectedUpstreamModel(model)"
                >
                  {{ model }}
                </button>
              </div>
            </div>
            <MtgaInput
              v-model="targetForm.api_key"
              label="API Key"
              type="password"
              placeholder="sk-..."
            />
            <MtgaInput
              v-model="targetForm.middle_route"
              label="Middle Route"
              :placeholder="getDefaultMiddleRoute(targetForm.provider)"
            />
            <label
              class="mt-7 flex cursor-pointer items-center justify-between gap-2 rounded-lg border border-slate-200/60 bg-slate-50/50 px-4 py-3"
            >
              <span class="label-text text-sm font-medium text-slate-700"
                >Включить кэш промптов</span
              >
              <input
                v-model="targetForm.prompt_cache_enabled"
                type="checkbox"
                class="toggle toggle-primary toggle-sm"
              />
            </label>
          </div>

          <ModelRoutingRequestBodyPatchEditor
            v-model="targetForm.request_body_patch_text"
            v-model:open="requestBodyPatchOpen"
          />
        </div>

        <div v-else-if="editorKind === 'published'" class="grid gap-4 md:grid-cols-2">
          <MtgaInput
            v-model="publishedForm.name"
            label="Имя публикуемой модели"
            required
            placeholder="gpt-5"
          />
          <MtgaSelect
            v-model="publishedForm.primary_route_key"
            label="Основная цель"
            required
            :options="targetModelOptions"
            class="w-full"
          />
          <MtgaSelect
            v-model="publishedForm.failover_pool_id"
            label="Пул фейловера"
            :options="poolOptions"
            class="w-full"
          />
          <label
            class="mt-7 flex cursor-pointer items-center justify-between gap-2 rounded-lg border border-slate-200/60 bg-slate-50/50 px-4 py-3"
          >
            <span class="label-text text-sm font-medium text-slate-700"
              >Включить (доступна клиентам)</span
            >
            <input
              v-model="publishedForm.enabled"
              type="checkbox"
              class="toggle toggle-primary toggle-sm"
            />
          </label>
        </div>

        <div v-else class="space-y-4">
          <div class="grid gap-4 md:grid-cols-3">
            <MtgaInput
              v-model="poolForm.id"
              label="Pool ID"
              required
              placeholder="failover-pool-1"
            />
            <MtgaInput
              v-model="poolForm.trigger_statuses"
              label="Коды статуса срабатывания"
              required
              placeholder="429"
            />
            <MtgaInput
              v-model="poolForm.cooldown_seconds"
              label="Охлаждение (сек)"
              type="number"
              required
              placeholder="10"
            />
          </div>
          <div>
            <div class="mb-2 text-sm font-medium text-slate-600">Цели-участники</div>
            <div class="grid gap-2 sm:grid-cols-2">
              <label
                v-for="option in targetModelOptions"
                :key="option.value"
                class="flex cursor-pointer items-center gap-3 rounded-lg border border-slate-200 bg-white/50 px-3 py-2 text-sm transition-colors hover:border-amber-200 hover:bg-amber-50/50"
              >
                <input
                  type="checkbox"
                  class="checkbox checkbox-primary checkbox-sm rounded"
                  :checked="poolForm.member_keys.includes(String(option.value))"
                  @change="
                    togglePoolMember(
                      String(option.value),
                      ($event.target as HTMLInputElement).checked,
                    )
                  "
                />
                <span class="min-w-0 flex-1 truncate">{{ option.label }}</span>
              </label>
            </div>
          </div>
        </div>

        <div v-if="formError" class="alert alert-error mt-4 rounded-xl px-3 py-2 text-xs">
          {{ formError }}
        </div>
      </div>

      <template #footer>
        <button class="mtga-btn-dialog-ghost flex-1" @click="closeEditor">Отмена</button>
        <button
          class="mtga-btn-dialog-primary flex-1"
          :class="saving ? 'loading' : ''"
          :disabled="saving"
          @click="handleEditorSave"
        >
          Сохранить
        </button>
      </template>
    </MtgaDialog>

    <MtgaDialog v-model:open="deleteConfirmOpen" max-width="max-w-md" @close="closeDeleteConfirm">
      <template #header>
        <div>
          <h3 class="text-lg font-semibold text-slate-900">{{ pendingDeleteTitle }}</h3>
          <p class="text-xs text-slate-500">{{ pendingDeleteDescription }}</p>
        </div>
      </template>

      <div class="px-6 py-6">
        <div class="rounded-xl border border-rose-100 bg-rose-50/70 px-4 py-3">
          <div class="text-xs font-semibold text-rose-500">Будет удалено</div>
          <div class="mt-1 break-all font-mono text-sm font-bold text-rose-700">
            {{ pendingDeleteLabel || "-" }}
          </div>
        </div>
      </div>

      <template #footer>
        <button class="mtga-btn-dialog-ghost flex-1" @click="closeDeleteConfirm">Отмена</button>
        <button
          class="flex-1 rounded-xl bg-rose-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-rose-700"
          :class="saving ? 'loading' : ''"
          :disabled="saving"
          @click="confirmDelete"
        >
          Удалить
        </button>
      </template>
    </MtgaDialog>

    <MtgaDialog v-model:open="settingsOpen" max-width="max-w-xl" @close="closeSettings">
      <template #header>
        <div>
          <h3 class="text-lg font-semibold text-slate-900">Входящие настройки</h3>
          <p class="text-xs text-slate-500">
            Влияет только на входящую авторизацию MTGA и изоляцию prompt cache
          </p>
        </div>
      </template>

      <div class="grid gap-4 px-6 py-6">
        <MtgaInput
          v-model="settingsForm.mtga_auth_key"
          label="MTGA Auth Key"
          placeholder="Пусто — без авторизации"
          type="password"
          description="Если пусто, входящие запросы MTGA не авторизуются; API Key апстрима задаётся в Целях апстрима"
          :clearable="true"
        />
        <MtgaInput
          v-model="settingsForm.prompt_cache_bucket_id"
          label="Prompt Cache Bucket"
          placeholder="Автогенерация или оставьте пустым"
          description="Используется для изоляции prompt cache"
          :clearable="true"
        />
      </div>

      <template #footer>
        <button class="mtga-btn-dialog-ghost flex-1" @click="closeSettings">Отмена</button>
        <button
          class="mtga-btn-dialog-primary flex-1"
          :class="saving ? 'loading' : ''"
          :disabled="saving"
          @click="saveSettings"
        >
          Сохранить
        </button>
      </template>
    </MtgaDialog>
  </div>
</template>
