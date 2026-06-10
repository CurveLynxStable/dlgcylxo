<script setup lang="ts">
const store = useMtgaStore();
const startAllPending = ref(false);

const handleStartAll = async () => {
  if (startAllPending.value) {
    return;
  }
  startAllPending.value = true;
  try {
    await store.runProxyStartAll();
  } finally {
    startAllPending.value = false;
  }
};
</script>

<template>
  <div class="flex flex-wrap items-center justify-between gap-4">
    <div>
      <div class="text-sm font-semibold text-slate-900">Быстрые действия</div>
      <div class="text-xs text-slate-500">
        Запуск одной кнопкой последовательно проверит сеть, сертификаты и hosts
      </div>
    </div>
    <MtgaLoadingButton
      class="btn btn-primary px-8 rounded-xl shadow-[0_12px_25px_-10px_rgba(240,187,50,0.6)]"
      :loading="startAllPending"
      @click="handleStartAll"
    >
      Запустить всё одной кнопкой
    </MtgaLoadingButton>
  </div>
</template>
