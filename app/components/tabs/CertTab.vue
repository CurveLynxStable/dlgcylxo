<script setup lang="ts">
type CertAction = "generate" | "install" | "clear";

const store = useMtgaStore();
const appInfo = store.appInfo;
const { runningAction, runAction } = usePendingAction<CertAction>();

const isConfirmOpen = ref(false);
const inputCommonName = ref("");
const showInputError = ref(false);

const clearCaTooltip = computed(() => {
  const commonName = appInfo.value.ca_common_name || "MTGA_CA";
  return [
    "macOS: удаляет подходящий CA-сертификат из системной связки ключей;",
    "Windows: удаляет подходящий CA-сертификат из хранилища Локальный компьютер/Root",
    `Common Name: ${commonName}`,
    "Требуются права администратора; используйте только при сбросе сертификатов",
  ].join("\n");
});

const handleGenerate = async () => {
  await runAction("generate", () => store.runGenerateCertificates());
};

const handleInstall = async () => {
  await runAction("install", () => store.runInstallCaCert());
};

/**
 * Запуск очистки системного CA-сертификата — сначала открываем диалог подтверждения
 */
const handleClear = () => {
  inputCommonName.value = appInfo.value.ca_common_name || "MTGA_CA";
  showInputError.value = false;
  isConfirmOpen.value = true;
};

/**
 * Фактическая очистка после подтверждения пользователем
 */
const confirmClear = async () => {
  if (!inputCommonName.value.trim()) {
    showInputError.value = true;
    return;
  }
  isConfirmOpen.value = false;
  await runAction("clear", () => store.runClearCaCert(inputCommonName.value));
};

watch(inputCommonName, (val) => {
  if (val.trim()) {
    showInputError.value = false;
  }
});
</script>

<template>
  <div class="mtga-soft-panel space-y-3">
    <div>
      <div class="text-sm font-semibold text-slate-900">Сертификаты</div>
      <div class="text-xs text-slate-500">
        Генерация, установка и очистка локальных сертификатов
      </div>
    </div>
    <div class="space-y-2">
      <MtgaLoadingButton
        class="mtga-btn-primary"
        :loading="runningAction === 'generate'"
        :disabled="Boolean(runningAction)"
        @click="handleGenerate"
      >
        Сгенерировать CA и серверный сертификат
      </MtgaLoadingButton>
      <div class="grid grid-cols-2 gap-2">
        <MtgaLoadingButton
          class="mtga-btn-primary"
          :loading="runningAction === 'install'"
          :disabled="Boolean(runningAction)"
          @click="handleInstall"
        >
          Установить CA-сертификат
        </MtgaLoadingButton>
        <MtgaLoadingButton
          class="mtga-btn-error tooltip mtga-tooltip"
          :data-tip="clearCaTooltip"
          :loading="runningAction === 'clear'"
          :disabled="Boolean(runningAction)"
          style="--mtga-tooltip-max: 280px"
          @click="handleClear"
        >
          Удалить системный CA-сертификат
        </MtgaLoadingButton>
      </div>
    </div>
  </div>

  <!-- Диалог подтверждения -->
  <ConfirmDialog
    v-model:open="isConfirmOpen"
    v-model="inputCommonName"
    title="Подтвердите удаление CA-сертификата"
    message="Подходящий CA-сертификат будет удалён из системного хранилища доверия. Продолжить?"
    show-input
    label="Common Name:"
    placeholder="Введите Common Name сертификата"
    :error="showInputError ? 'Введите корректный Common Name' : ''"
    input-class="font-mono"
    confirm-text="Удалить"
    type="error"
    @confirm="confirmClear"
  />
</template>
