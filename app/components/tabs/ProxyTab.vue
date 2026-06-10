<script setup lang="ts">
type ProxyAction = "start" | "stop" | "check";

const store = useMtgaStore();
const options = store.runtimeOptions;
const { runningAction, runAction } = usePendingAction<ProxyAction>();

const debugModeTooltip = [
  "После включения:",
  "1) прокси-сервер выводит более подробные отладочные логи для диагностики;",
  "2) перед запуском прокси дополнительно проверяется явная настройка прокси в системе/переменных окружения",
  "с предупреждением, что она может обходить перенаправление через hosts.",
  "(По умолчанию проверка 2 не выполняется — только в режиме отладки)",
].join("\n");

const handleStart = async () => {
  await runAction("start", () => store.runProxyStart());
};

const handleStop = async () => {
  await runAction("stop", () => store.runProxyStop());
};

const handleCheck = async () => {
  await runAction("check", () => store.runProxyCheckNetwork());
};
</script>

<template>
  <div class="mtga-soft-panel space-y-3 mb-4">
    <div>
      <div class="text-sm font-semibold text-slate-900">Параметры рантайма</div>
      <div class="text-xs text-slate-500">Управление поведением прокси и отладкой</div>
    </div>
    <div class="space-y-3">
      <label
        class="flex items-center gap-3 text-sm text-slate-700 tooltip mtga-tooltip cursor-pointer hover:bg-slate-100/50 rounded px-3 py-2 -my-1 transition-colors"
        :data-tip="debugModeTooltip"
        style="--mtga-tooltip-max: 500px"
      >
        <input v-model="options.debugMode" type="checkbox" class="checkbox checkbox-sm" />
        <span>Режим отладки</span>
      </label>
      <label
        class="flex items-center gap-3 text-sm text-slate-700 cursor-pointer hover:bg-slate-100/50 rounded px-3 py-2 -my-1 transition-colors"
      >
        <input v-model="options.disableSslStrict" type="checkbox" class="checkbox checkbox-sm" />
        <span>Отключить строгий режим SSL</span>
      </label>
      <div class="flex flex-wrap items-center gap-1 text-sm text-slate-700">
        <label
          class="flex items-center gap-3 cursor-pointer hover:bg-slate-100/50 rounded px-3 py-2 -my-1 transition-colors"
        >
          <input v-model="options.forceStream" type="checkbox" class="checkbox checkbox-sm" />
          <span>Принудительный потоковый режим</span>
        </label>
        <MtgaSelect
          v-model="options.streamMode"
          :options="['true', 'false']"
          size="xs"
          class="w-20"
          :disabled="!options.forceStream"
        />
      </div>
    </div>
  </div>

  <div class="mtga-soft-panel space-y-3">
    <div>
      <div class="text-sm font-semibold text-slate-900">Прокси-сервис</div>
      <div class="text-xs text-slate-500">Запуск / остановка / проверка сети</div>
    </div>
    <div class="space-y-2">
      <MtgaLoadingButton
        class="mtga-btn-primary"
        :loading="runningAction === 'start'"
        :disabled="Boolean(runningAction)"
        @click="handleStart"
      >
        Запустить прокси-сервер
      </MtgaLoadingButton>
      <MtgaLoadingButton
        class="mtga-btn-error"
        :loading="runningAction === 'stop'"
        :disabled="Boolean(runningAction)"
        @click="handleStop"
      >
        Остановить прокси-сервер
      </MtgaLoadingButton>
      <MtgaLoadingButton
        class="mtga-btn-outline"
        :loading="runningAction === 'check'"
        :disabled="Boolean(runningAction)"
        @click="handleCheck"
      >
        Проверить сетевое окружение
      </MtgaLoadingButton>
    </div>
  </div>
</template>
