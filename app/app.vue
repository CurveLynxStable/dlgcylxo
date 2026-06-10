<script setup lang="ts">
import { ICONS } from "./composables/icons";
import { applyThemeConfig, loadThemeFromStorage } from "./composables/themeConfig";

const {
  logs,
  init,
  appInfo,
  hasNewVersion,
  updateDialogOpen,
  updateVersionLabel,
  updateNotesHtml,
  updateReleaseUrl,
  runCheckUpdates,
  runCheckUpdatesOnce,
  closeUpdateDialog,
  openUpdateRelease,
  stopLogStream,
  stopProxyStepListener,
  panelNavTarget,
  panelNavSignal,
} = useMtgaStore();

if (import.meta.client) {
  const savedTheme = loadThemeFromStorage();
  if (savedTheme) {
    applyThemeConfig(savedTheme);
  }
}

/**
 * ID текущей выбранной левой панели
 */
const activeTab = ref("model-routing");
const direction = ref<"down" | "up">("down");

/**
 * Переключение навигации
 * @param id ID целевой панели
 */
const selectTab = (id: string) => {
  const oldIndex = navigation.findIndex((item) => item.id === activeTab.value);
  const newIndex = navigation.findIndex((item) => item.id === id);

  if (newIndex !== oldIndex) {
    direction.value = newIndex > oldIndex ? "down" : "up";
    activeTab.value = id;
  }
};

const clearLogs = () => {
  logs.value = [];
};

/**
 * Состояние глобального прокси Tooltip
 */
const tooltipProxy = reactive({
  show: false,
  content: "",
  maxWidth: "280px",
  style: {} as Record<string, string>,
});

// Проверка поддержки CSS Anchor Positioning API (macOS WebKit пока не поддерживает)
const supportsAnchor =
  typeof CSS !== "undefined" && CSS.supports && CSS.supports("anchor-name", "--test");

// Текущий элемент с активным якорем — для своевременной очистки
let lastAnchorTarget: HTMLElement | null = null;

const emitFrontendReady = async () => {
  if (typeof window === "undefined") {
    return;
  }
  const tauriWindow = window as Window & {
    __TAURI__?: {
      event?: {
        emit?: (event: string, payload?: unknown) => Promise<unknown> | unknown;
      };
    };
  };
  const emit = tauriWindow.__TAURI__?.event?.emit;
  if (typeof emit !== "function") {
    return;
  }
  try {
    await emit("mtga:frontend-ready", {
      ts_ms: Date.now(),
    });
  } catch {
    // ignore
  }
};

/**
 * Глобальный обработчик наведения мыши — ловит элементы mtga-tooltip
 */
const handleGlobalMouseOver = (e: MouseEvent) => {
  const eventTarget = e.target;
  const target = eventTarget instanceof HTMLElement ? eventTarget.closest(".mtga-tooltip") : null;

  if (target instanceof HTMLElement) {
    // Если цель сменилась — сначала очистить якорь старой цели
    if (lastAnchorTarget && lastAnchorTarget !== target) {
      lastAnchorTarget.style.removeProperty("anchor-name");
    }

    tooltipProxy.content = target.getAttribute("data-tip") || "";
    tooltipProxy.maxWidth = target.style.getPropertyValue("--mtga-tooltip-max") || "280px";
    tooltipProxy.show = true;

    if (supportsAnchor) {
      // Якорное позиционирование поддерживается: задаём имя якоря новой цели
      target.style.setProperty("anchor-name", "--mtga-tooltip-anchor");
      tooltipProxy.style = {};
    } else {
      // Якорное позиционирование не поддерживается (например, macOS): считаем позицию вручную
      const rect = target.getBoundingClientRect();
      tooltipProxy.style = {
        left: `${rect.left + rect.width / 2}px`,
        bottom: `${window.innerHeight - rect.top + 10}px`,
        top: "auto",
      };
    }

    lastAnchorTarget = target;
  } else {
    tooltipProxy.show = false;
    // При выходе из зоны tooltip очищаем якорь
    if (lastAnchorTarget) {
      lastAnchorTarget.style.removeProperty("anchor-name");
      lastAnchorTarget = null;
    }
  }
};

/**
 * Конфигурация меню навигации
 */
const navigation = [
  { id: "model-routing", name: "Маршрутизация", icon: ICONS.MODEL_ROUTING },
  { id: "main-tabs", name: "Основное", icon: ICONS.MAIN_TABS },
  { id: "proxy-logs", name: "Логи прокси", icon: ICONS.PROXY_LOGS },
  { id: "system-prompts", name: "Промпты", icon: ICONS.SYSTEM_PROMPTS },
  { id: "settings", name: "Настройки", icon: ICONS.SETTINGS },
];

const resolvePanelTarget = (value: string | null) => {
  if (!value) {
    return null;
  }
  return navigation.some((item) => item.id === value) ? value : null;
};

watch(
  panelNavSignal,
  () => {
    const resolved = resolvePanelTarget(panelNavTarget.value);
    if (!resolved) {
      return;
    }
    selectTab(resolved);
  },
  { immediate: true },
);

onMounted(async () => {
  try {
    await init();
    await nextTick();
  } finally {
    await emitFrontendReady();
  }
  void runCheckUpdatesOnce();
});

onBeforeUnmount(() => {
  stopLogStream();
  stopProxyStepListener();
});
</script>

<template>
  <div @mouseover="handleGlobalMouseOver">
    <AppShell>
      <template #left>
        <div class="flex items-stretch h-full min-h-0">
          <!-- Вертикальное меню -->
          <div class="w-38 border-r border-slate-200/50 flex flex-col p-3 shrink-0">
            <ul class="menu p-0 gap-1">
              <li v-for="item in navigation" :key="item.id">
                <a
                  :class="[
                    'flex flex-row items-center justify-start gap-2.5 px-3 py-2.5 rounded-xl transition-all duration-200 group border',
                    activeTab === item.id
                      ? 'bg-amber-500/15 text-amber-600 border-amber-500/40 shadow-sm shadow-amber-500/10'
                      : 'text-slate-500 border-transparent hover:bg-slate-200/40',
                  ]"
                  @click="selectTab(item.id)"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    class="h-5 w-5 opacity-80 shrink-0"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      :d="item.icon"
                    />
                  </svg>
                  <span class="text-sm font-bold tracking-wide truncate">{{ item.name }}</span>
                </a>
              </li>
            </ul>

            <!-- О программе и обновления -->
            <div class="mt-auto pt-4 border-t border-slate-200/50 flex flex-col gap-2 px-1">
              <div class="flex flex-col gap-0.5">
                <div class="relative w-fit">
                  <div class="text-[11px] font-medium text-slate-400">
                    {{ appInfo.version }}
                  </div>
                  <span v-if="hasNewVersion" class="mtga-badge-new -top-1.5! -right-9!"> NEW </span>
                </div>
              </div>

              <button
                class="btn btn-xs btn-outline rounded-lg border-slate-200 hover:border-amber-500 hover:bg-amber-50 hover:text-amber-600 font-bold w-full"
                @click="runCheckUpdates"
              >
                Проверить обновления
              </button>

              <div class="text-[10px] text-slate-400/80 text-center mt-1">powered by BiFangKNT</div>
            </div>
          </div>

          <!-- Область содержимого панелей -->
          <div class="flex-1 min-w-0 p-6 overflow-hidden flex flex-col">
            <Transition
              enter-active-class="transition duration-200 ease-out"
              :enter-from-class="
                direction === 'down' ? 'translate-y-4 opacity-0' : '-translate-y-4 opacity-0'
              "
              enter-to-class="translate-y-0 opacity-100"
              leave-active-class="transition duration-150 ease-in"
              leave-from-class="translate-y-0 opacity-100"
              :leave-to-class="
                direction === 'down' ? '-translate-y-4 opacity-0' : 'translate-y-4 opacity-0'
              "
              mode="out-in"
            >
              <div
                :key="activeTab"
                class="flex-1 overflow-y-auto overflow-x-hidden custom-scrollbar"
              >
                <ModelRoutingPanel v-if="activeTab === 'model-routing'" />
                <MainTabs v-if="activeTab === 'main-tabs'" />
                <ProxyLogPanel v-if="activeTab === 'proxy-logs'" />
                <SystemPromptPanel v-if="activeTab === 'system-prompts'" />
                <SettingsPanel v-if="activeTab === 'settings'" />
              </div>
            </Transition>
          </div>
        </div>
      </template>

      <template #right>
        <div class="h-full flex flex-col p-6">
          <LogPanel :logs="logs" class="flex-1" @clear="clearLogs" />
        </div>
      </template>

      <template #footer>
        <FooterActions />
      </template>
    </AppShell>

    <UpdateDialog
      :open="updateDialogOpen"
      :version-label="updateVersionLabel"
      :notes-html="updateNotesHtml"
      :release-url="updateReleaseUrl"
      @close="closeUpdateDialog"
      @open-release="openUpdateRelease"
    />

    <!-- Глобальный прокси Tooltip для выхода за пределы обрезки контейнера -->
    <div
      v-show="tooltipProxy.show"
      class="mtga-tooltip-proxy"
      :style="{
        '--mtga-tooltip-max': tooltipProxy.maxWidth,
        ...tooltipProxy.style,
      }"
    >
      {{ tooltipProxy.content }}
    </div>
  </div>
</template>
