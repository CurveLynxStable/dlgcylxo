<script setup lang="ts">
/**
 * Панель настроек
 * Управление пользовательскими данными: резервное копирование, восстановление и очистка
 */
import type { ProxyMode } from "~/composables/mtgaTypes";
import {
  type ThemeConfig,
  DEFAULT_THEME_CONFIG,
  applyThemeConfig,
  copyThemeConfig,
  loadThemeFromStorage,
  sanitizeThemeConfig,
  saveThemeToStorage,
} from "~/composables/themeConfig";

const store = useMtgaStore();
const appInfo = store.appInfo;

const clearConfirmOpen = ref(false);
const clearConfirmTitle = "Подтвердите очистку данных";
const clearConfirmMessage =
  "Очистить пользовательские данные? Будут удалены конфигурация, SSL-сертификаты и резервная копия hosts (папка backups сохраняется).";
const proxyModeSwitchConfirmOpen = ref(false);
const currentProxyModeForConfirm = ref<ProxyMode | null>(null);
const themeDialogOpen = ref(false);
const proxySettingsSaving = ref(false);
const appSettingsSaving = ref(false);
const traePathBrowsing = ref(false);

const themeConfig = reactive<ThemeConfig>({ ...DEFAULT_THEME_CONFIG });
if (import.meta.client) {
  const savedTheme = loadThemeFromStorage();
  if (savedTheme) {
    copyThemeConfig(themeConfig, savedTheme);
  }
}

const proxyMode = computed({
  get: () => store.proxyMode.value,
  set: (value: ProxyMode) => {
    store.proxyMode.value = value;
  },
});

const traePath = computed({
  get: () => store.traePath.value,
  set: (value: string) => {
    store.traePath.value = value;
  },
});

const traeNativeEnabled = computed(() => proxyMode.value === "trae_native");
const traeOfficialBaseUrlEnabled = computed(() => proxyMode.value === "trae_official_base_url");
const savedProxyMode = computed(() => store.savedProxyMode.value);
const proxyModeDirty = computed(() => proxyMode.value !== savedProxyMode.value);
const proxyRuntimeKnown = computed(() => store.proxyRuntimeKnown.value);
const proxyRuntimeRunning = computed(() => store.proxyRuntimeRunning.value);
const proxyRuntimeActiveMode = computed(() => store.proxyRuntimeActiveMode.value);
const proxyRuntimeLoopbackPort = computed(() => store.proxyRuntimeLoopbackPort.value);
const minimizeToTrayOnClose = computed({
  get: () => store.minimizeToTrayOnClose.value,
  set: (value: boolean) => {
    store.minimizeToTrayOnClose.value = value;
  },
});

const traePathMissing = computed(() => traeNativeEnabled.value && !traePath.value.trim());
const PREFERRED_TRAE_OFFICIAL_BASE_URL = "http://127.0.0.1:18083/v1";

const buildTraeOfficialBaseUrl = (port: number) => `http://127.0.0.1:${port}/v1`;

const formatProxyModeLabel = (value: ProxyMode | null | undefined) => {
  if (value === "trae_native") {
    return "Trae native";
  }
  if (value === "trae_official_base_url") {
    return "Официальный Base URL";
  }
  if (value === "reverse_hosts") {
    return "Обратный прокси";
  }
  return "Не запущен";
};

const runtimeStatusBadgeClass = computed(() => {
  if (!proxyRuntimeKnown.value) {
    return "border-slate-200 bg-white/60 text-slate-500";
  }
  if (proxyRuntimeRunning.value) {
    return "border-emerald-500/40 bg-emerald-50 text-emerald-700";
  }
  return "border-slate-200 bg-white/60 text-slate-500";
});

const runtimeStatusDotClass = computed(() => {
  if (!proxyRuntimeKnown.value) {
    return "bg-slate-300";
  }
  return proxyRuntimeRunning.value ? "bg-emerald-500" : "bg-slate-300";
});

const runtimeStatusLabel = computed(() => {
  if (!proxyRuntimeKnown.value) {
    return "Синхронизация состояния...";
  }
  if (proxyRuntimeRunning.value) {
    return formatProxyModeLabel(proxyRuntimeActiveMode.value);
  }
  return "Не запущен";
});

const traePathPlaceholder = computed(() => {
  if (import.meta.client && /Mac/i.test(navigator.platform)) {
    return "/Applications/Trae.app";
  }
  return "%LOCALAPPDATA%\\Programs\\Trae\\Trae.exe";
});

/**
 * Текст подсказки для открытия каталога
 */
const openDirTooltip = computed(() => {
  const current = appInfo.value.user_data_dir?.trim();
  const fallback = appInfo.value.default_user_data_dir?.trim();
  if (current && fallback && current !== fallback) {
    return `Открыть каталог пользовательских данных в файловом менеджере\nТекущий: ${current}\nПо умолчанию: ${fallback}`;
  }
  if (current) {
    return `Открыть каталог пользовательских данных в файловом менеджере\nКаталог: ${current}`;
  }
  if (fallback) {
    return `Открыть каталог пользовательских данных в файловом менеджере\nКаталог по умолчанию: ${fallback}`;
  }
  return "Открыть каталог пользовательских данных в файловом менеджере";
});

/**
 * Текст подсказки для резервного копирования
 */
const backupTooltip = [
  "Создать полную резервную копию с отметкой времени",
  "Содержимое: конфигурация, SSL-сертификаты, резервная копия hosts",
  "Расположение: каталог данных/backups/backup_время/",
].join("\n");

/**
 * Текст подсказки для восстановления данных
 */
const restoreTooltip = [
  "Восстановить данные из последней резервной копии (перезаписывает текущие)",
  "Автоматически выбирается самая свежая копия",
  "Внимание: операция перезапишет текущую конфигурацию и сертификаты",
].join("\n");

/**
 * Текст подсказки для очистки данных
 */
const clearTooltip = [
  "Удалить все пользовательские данные (исторические копии сохраняются)",
  "Удаляется: конфигурация, SSL-сертификаты, резервная копия hosts",
  "Сохраняется: папка backups и её содержимое",
].join("\n");

const proxyModeTooltip = [
  "Официальный Base URL: официальный интерфейс, запускается только локальный loopback",
  "Обратный прокси: классическая схема hosts + HTTPS",
  "Trae native: MTGA запускает Trae и подключает native rewriter",
  "Кнопка «Запустить всё» работает согласно выбранному режиму",
].join("\n");

const traePathTooltip = [
  "Выбор пути к исполняемому файлу Trae",
  "Рекомендуется использовать кнопку «Обзор», чтобы не ошибиться в пути",
  "При этом режиме «Запустить всё» автоматически запустит Trae с native SSE URL rewriter",
].join("\n");

const officialBaseUrlTooltip = [
  "Этот режим запускает только локальный loopback, не меняет hosts и не устанавливает сертификаты",
  `Предпочтительный адрес: ${PREFERRED_TRAE_OFFICIAL_BASE_URL}`,
  "Если порт 18083 занят, будет выбран следующий свободный порт",
  "После запуска здесь автоматически отобразится фактический адрес",
].join("\n");

const officialRuntimeLoopbackPort = computed(() => {
  if (!proxyRuntimeRunning.value || proxyRuntimeActiveMode.value !== "trae_official_base_url") {
    return null;
  }
  return proxyRuntimeLoopbackPort.value;
});

const officialBaseUrlDisplay = computed(() => {
  const runtimePort = officialRuntimeLoopbackPort.value;
  if (typeof runtimePort === "number") {
    return buildTraeOfficialBaseUrl(runtimePort);
  }
  return PREFERRED_TRAE_OFFICIAL_BASE_URL;
});

const officialBaseUrlStatusText = computed(() => {
  const runtimePort = officialRuntimeLoopbackPort.value;
  if (runtimePort === null) {
    return "Пока не запущено — показан предпочтительный адрес; после запуска обновится на фактический порт";
  }
  if (runtimePort === 18083) {
    return "Фактический адрес работающего сервиса";
  }
  return `Фактический адрес работающего сервиса, порт изменён на ${runtimePort}`;
});

onMounted(() => {
  void store.startProxyStatusListener().finally(() => {
    void store.fetchProxyRuntimeStatus();
  });
});

/**
 * Открытие каталога данных
 */
const handleOpen = () => {
  store.runUserDataOpenDir();
};

/**
 * Резервное копирование данных
 */
const handleBackup = () => {
  store.runUserDataBackup();
};

/**
 * Восстановление данных
 */
const handleRestore = () => {
  store.runUserDataRestoreLatest();
};

/**
 * Очистка данных
 */
const handleClear = () => {
  clearConfirmOpen.value = true;
};

const cancelClear = () => {
  clearConfirmOpen.value = false;
};

const confirmClear = () => {
  clearConfirmOpen.value = false;
  store.runUserDataClear();
};

const handleBrowseTraePath = async () => {
  if (traePathBrowsing.value) {
    return;
  }
  traePathBrowsing.value = true;
  try {
    await store.runBrowseTraePath();
  } finally {
    traePathBrowsing.value = false;
  }
};

const setProxyMode = (value: ProxyMode) => {
  proxyMode.value = value;
};

const saveProxySettings = async (options?: { stopRunningProxy?: boolean }) => {
  const stopRunningProxy = options?.stopRunningProxy === true;
  if (proxySettingsSaving.value) {
    return;
  }

  proxySettingsSaving.value = true;
  proxyModeSwitchConfirmOpen.value = false;
  currentProxyModeForConfirm.value = null;
  try {
    const ok = await store.saveConfig();
    if (!ok) {
      store.appendLog("Не удалось сохранить настройки режима прокси");
      return;
    }

    if (!stopRunningProxy) {
      store.appendLog("Настройки режима прокси сохранены");
      return;
    }

    store.appendLog("Настройки режима прокси сохранены, остановка текущего прокси...");
    const stopped = await store.runProxyStop();
    if (stopped) {
      store.appendLog("Текущий прокси остановлен; запустите заново с новым режимом");
      return;
    }
    store.appendLog("Настройки режима прокси сохранены, но остановить текущий прокси не удалось");
  } finally {
    proxySettingsSaving.value = false;
  }
};

const handleProxySettingsSave = async () => {
  if (proxyMode.value === "trae_native" && !traePath.value.trim()) {
    store.appendLog(
      "Ошибка: Путь к Trae не выбран — укажите его перед включением режима Trae native",
    );
    return;
  }

  if (proxyModeDirty.value) {
    const runtimeStatus = await store.fetchProxyRuntimeStatus();
    if (runtimeStatus?.running) {
      currentProxyModeForConfirm.value = runtimeStatus.active_mode;
      proxyModeSwitchConfirmOpen.value = true;
      return;
    }
  }

  await saveProxySettings();
};

const cancelProxyModeSwitch = () => {
  proxyModeSwitchConfirmOpen.value = false;
  currentProxyModeForConfirm.value = null;
};

const confirmProxyModeSwitch = async () => {
  await saveProxySettings({ stopRunningProxy: true });
};

const openThemeDialog = () => {
  themeDialogOpen.value = true;
};

const handleThemeSave = (value: ThemeConfig) => {
  const normalized = sanitizeThemeConfig(value);
  copyThemeConfig(themeConfig, normalized);
  applyThemeConfig(themeConfig);
  const saveResult = saveThemeToStorage(themeConfig);
  if (saveResult.ok) {
    store.appendLog("Конфигурация темы сохранена");
    return;
  }
  store.appendLog(
    `Конфигурация темы применена, но локальное сохранение не удалось: ${saveResult.error}`,
  );
};

const handleMinimizeToTrayOnCloseChange = async () => {
  if (appSettingsSaving.value) {
    return;
  }
  const previousValue = store.savedMinimizeToTrayOnClose.value;
  appSettingsSaving.value = true;
  try {
    const ok = await store.saveAppSettings();
    if (!ok) {
      minimizeToTrayOnClose.value = previousValue;
      store.appendLog("Не удалось сохранить настройку поведения при закрытии");
      return;
    }
    store.appendLog("Настройка поведения при закрытии сохранена");
  } finally {
    appSettingsSaving.value = false;
  }
};
</script>

<template>
  <div class="flex items-center justify-between gap-3">
    <div>
      <h2 class="mtga-card-title">Настройки приложения</h2>
      <p class="mtga-card-subtitle">Управление данными и системной конфигурацией</p>
    </div>
    <span class="mtga-chip">Система</span>
  </div>

  <div class="mt-4 space-y-4">
    <div class="mtga-soft-panel space-y-3">
      <div>
        <div class="text-sm font-semibold text-slate-900">Пользовательские данные</div>
        <div class="text-xs text-slate-500">Резервное копирование и восстановление данных</div>
      </div>
      <div class="space-y-2">
        <button
          class="mtga-btn-outline tooltip mtga-tooltip"
          :data-tip="openDirTooltip"
          @click="handleOpen"
        >
          Открыть каталог
        </button>
        <button
          class="mtga-btn-primary tooltip mtga-tooltip"
          :data-tip="backupTooltip"
          style="--mtga-tooltip-max: 360px"
          @click="handleBackup"
        >
          Резервная копия
        </button>
        <button
          class="mtga-btn-outline tooltip mtga-tooltip"
          :data-tip="restoreTooltip"
          style="--mtga-tooltip-max: 360px"
          @click="handleRestore"
        >
          Восстановить данные
        </button>
        <button
          class="mtga-btn-error tooltip mtga-tooltip"
          :data-tip="clearTooltip"
          style="--mtga-tooltip-max: 360px"
          @click="handleClear"
        >
          Очистить данные
        </button>
      </div>
    </div>

    <div class="mtga-soft-panel space-y-3">
      <div class="flex items-start justify-between gap-3">
        <div>
          <div class="text-sm font-semibold text-slate-900">Режим запуска</div>
          <div class="text-xs text-slate-500">Определяет способ подключения</div>
        </div>
        <span
          class="inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold"
          :class="runtimeStatusBadgeClass"
        >
          <span class="h-1.5 w-1.5 rounded-full" :class="runtimeStatusDotClass" />
          Состояние: {{ runtimeStatusLabel }}
        </span>
      </div>

      <div
        class="tooltip mtga-tooltip grid grid-cols-1 gap-2 md:grid-cols-3"
        :data-tip="proxyModeTooltip"
        style="--mtga-tooltip-max: 360px"
      >
        <button
          type="button"
          class="cursor-pointer rounded-xl border px-3 py-2 text-left transition-all active:scale-[0.99]"
          :class="
            traeOfficialBaseUrlEnabled
              ? 'border-emerald-500/50 bg-emerald-50/80 shadow-sm shadow-emerald-500/10'
              : 'border-slate-200/80 bg-white/40 hover:border-slate-300 hover:bg-white/70'
          "
          @click="setProxyMode('trae_official_base_url')"
        >
          <span class="block text-sm font-semibold text-slate-800">Официальный Base URL</span>
          <span class="mt-0.5 block text-[11px] leading-4 text-slate-500"
            >только loopback, без patch</span
          >
        </button>
        <button
          type="button"
          class="cursor-pointer rounded-xl border px-3 py-2 text-left transition-all active:scale-[0.99]"
          :class="
            proxyMode === 'reverse_hosts'
              ? 'border-amber-500/50 bg-amber-50/80 shadow-sm shadow-amber-500/10'
              : 'border-slate-200/80 bg-white/40 hover:border-slate-300 hover:bg-white/70'
          "
          @click="setProxyMode('reverse_hosts')"
        >
          <span class="block text-sm font-semibold text-slate-800">Обратный прокси</span>
          <span class="mt-0.5 block text-[11px] leading-4 text-slate-500"
            >hosts + HTTPS-прокси</span
          >
        </button>
        <button
          type="button"
          class="cursor-pointer rounded-xl border px-3 py-2 text-left transition-all active:scale-[0.99]"
          :class="
            traeNativeEnabled
              ? 'border-amber-500/50 bg-amber-50/80 shadow-sm shadow-amber-500/10'
              : 'border-slate-200/80 bg-white/40 hover:border-slate-300 hover:bg-white/70'
          "
          @click="setProxyMode('trae_native')"
        >
          <span class="block text-sm font-semibold text-slate-800">Trae native</span>
          <span class="mt-0.5 block text-[11px] leading-4 text-slate-500"
            >patch исходников Trae</span
          >
        </button>
      </div>

      <div
        v-if="traeNativeEnabled"
        class="mtga-tooltip w-full rounded-xl border border-slate-200/80 bg-white/35 p-3"
        :data-tip="traePathTooltip"
        style="--mtga-tooltip-max: 360px"
      >
        <div class="mb-2 flex items-center justify-between gap-3">
          <div>
            <div class="text-xs font-semibold text-slate-700">Исполняемый файл Trae</div>
            <div class="text-[11px] text-slate-400">
              Используется для запуска чистого экземпляра Trae из MTGA
            </div>
          </div>
        </div>
        <div class="flex items-start gap-2">
          <MtgaInput
            v-model="traePath"
            class="min-w-0 flex-1"
            :placeholder="traePathPlaceholder"
            :error="
              traePathMissing ? 'Перед включением режима Trae native выберите путь к Trae.' : ''
            "
          />
          <button
            type="button"
            class="btn btn-outline btn-sm h-10 min-w-[76px] shrink-0 cursor-pointer gap-2 rounded-xl border-slate-200 px-3 hover:border-amber-500 hover:bg-amber-50/50 hover:text-amber-600"
            :disabled="traePathBrowsing"
            :aria-busy="traePathBrowsing"
            @click="handleBrowseTraePath"
          >
            <span
              v-if="traePathBrowsing"
              class="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-amber-500"
            />
            <span>{{ traePathBrowsing ? "Выбор..." : "Обзор" }}</span>
          </button>
        </div>
      </div>

      <div
        v-if="traeOfficialBaseUrlEnabled"
        class="mtga-tooltip w-full rounded-xl border border-emerald-200/70 bg-emerald-50/50 p-3"
        :data-tip="officialBaseUrlTooltip"
        style="--mtga-tooltip-max: 360px"
      >
        <div class="mb-2 flex items-center justify-between gap-3">
          <div>
            <div class="text-xs font-semibold text-emerald-800">
              Base URL пользовательской модели Trae
            </div>
            <div class="text-[11px] text-emerald-700/80">
              Этот режим запускает только локальный loopback; base_url в Trae нужно указать вручную
            </div>
          </div>
        </div>
        <div
          class="rounded-lg border border-emerald-200/70 bg-white/80 px-3 py-2 font-mono text-sm text-emerald-900"
        >
          {{ officialBaseUrlDisplay }}
        </div>
        <div class="mt-2 text-[11px] text-emerald-700/80">
          {{ officialBaseUrlStatusText }}
        </div>
      </div>

      <div class="flex items-center justify-end">
        <button
          class="btn btn-primary btn-sm rounded-xl px-4"
          :class="proxySettingsSaving ? 'loading' : ''"
          :disabled="proxySettingsSaving"
          @click="handleProxySettingsSave"
        >
          Сохранить режим запуска
        </button>
      </div>
    </div>

    <button class="mtga-clickable-row" @click="openThemeDialog">
      <span class="flex flex-col items-start gap-0.5 text-left">
        <span class="font-semibold text-slate-800">Настройка темы</span>
        <span class="text-xs font-normal text-slate-500">Настройка цветов, шрифтов и фона</span>
      </span>
    </button>

    <label
      class="mtga-btn-outline flex h-auto cursor-pointer items-center justify-between gap-3 px-4 py-2 text-sm transition-all active:scale-[0.98]"
    >
      <span class="flex min-w-0 flex-col gap-0.5 text-left">
        <span class="font-semibold text-slate-800">Сворачивать в трей при закрытии</span>
        <span class="text-xs font-normal text-slate-500"
          >После закрытия главного окна продолжать работу в фоне</span
        >
      </span>
      <input
        v-model="minimizeToTrayOnClose"
        type="checkbox"
        class="toggle toggle-primary toggle-sm shrink-0"
        :disabled="appSettingsSaving"
        @change="handleMinimizeToTrayOnCloseChange"
      />
    </label>
  </div>

  <ConfirmDialog
    :open="clearConfirmOpen"
    :title="clearConfirmTitle"
    :message="clearConfirmMessage"
    confirm-text="Очистить"
    type="error"
    @cancel="cancelClear"
    @confirm="confirmClear"
  />

  <ConfirmDialog
    :open="proxyModeSwitchConfirmOpen"
    title="Подтвердите смену режима"
    message="Прокси сейчас работает. После сохранения нового режима MTGA немедленно остановит текущий прокси; следующий запуск будет в новом режиме."
    confirm-text="Сохранить и остановить прокси"
    @cancel="cancelProxyModeSwitch"
    @confirm="confirmProxyModeSwitch"
  >
    <div class="space-y-2 text-sm text-slate-600">
      <p>Сейчас работает: {{ formatProxyModeLabel(currentProxyModeForConfirm) }}</p>
      <p>Будет переключено на: {{ formatProxyModeLabel(proxyMode) }}</p>
    </div>
  </ConfirmDialog>

  <ThemeSettingsDialog
    v-model:open="themeDialogOpen"
    :config="themeConfig"
    @save="handleThemeSave"
  />
</template>
