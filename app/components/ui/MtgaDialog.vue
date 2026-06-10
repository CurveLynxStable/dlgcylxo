<script setup lang="ts">
/**
 * Базовый компонент диалога MTGA
 * Отвечает только за поведение контейнера: показ, закрытие и структурные слоты
 */
const props = withDefaults(
  defineProps<{
    /** Показывать ли диалог */
    open?: boolean;
    /** Максимальная ширина диалога, по умолчанию max-w-sm */
    maxWidth?: string;
    /** Закрывать по клику на фон, по умолчанию true */
    closeOnBackdrop?: boolean;
    /** Закрывать по ESC, по умолчанию true */
    closeOnEsc?: boolean;
  }>(),
  {
    open: false,
    maxWidth: "max-w-sm",
    closeOnBackdrop: true,
    closeOnEsc: true,
  },
);

const emit = defineEmits<{
  (event: "update:open", value: boolean): void;
  (event: "close"): void;
}>();

/**
 * Единая точка закрытия: синхронизирует open и эмитирует событие close
 */
const requestClose = () => {
  if (!props.open) {
    return;
  }
  emit("update:open", false);
  emit("close");
};

const handleBackdropClick = () => {
  if (!props.closeOnBackdrop) {
    return;
  }
  requestClose();
};

const handleEscape = () => {
  if (!props.closeOnEsc) {
    return;
  }
  requestClose();
};
</script>

<template>
  <dialog class="modal" :class="{ 'modal-open': props.open }" @keydown.esc.prevent="handleEscape">
    <div
      class="modal-box mtga-card max-h-[calc(100dvh-2rem)] overflow-hidden border-slate-200/60 p-0 shadow-2xl transition-all duration-200"
      :class="[props.maxWidth, props.open ? 'scale-100 opacity-100' : 'scale-95 opacity-0']"
    >
      <div class="mtga-card-body flex max-h-[calc(100dvh-2rem)] flex-col p-0">
        <!-- Слот заголовка: разделитель снизу добавляет базовый компонент -->
        <div v-if="$slots.header" class="px-6 py-5 border-b border-slate-100/50">
          <slot name="header"></slot>
        </div>

        <!-- Слот по умолчанию: основное содержимое -->
        <div class="flex-1 min-h-0 overflow-y-auto">
          <slot></slot>
        </div>

        <!-- Нижний слот: область кнопок действий -->
        <div
          v-if="$slots.footer"
          class="px-6 py-3 bg-slate-50/50 border-t border-slate-100 flex items-center gap-3"
        >
          <slot name="footer"></slot>
        </div>
      </div>
    </div>

    <!-- Фоновое затемнение -->
    <form
      v-if="props.closeOnBackdrop"
      method="dialog"
      class="modal-backdrop bg-slate-900/20 backdrop-blur-[2px] transition-opacity duration-200"
      :class="props.open ? 'opacity-100' : 'opacity-0'"
      @click.prevent="handleBackdropClick"
    >
      <button type="button" aria-label="Закрыть диалог">close</button>
    </form>
    <div
      v-else
      class="modal-backdrop bg-slate-900/20 backdrop-blur-[2px] transition-opacity duration-200"
      :class="props.open ? 'opacity-100' : 'opacity-0'"
    ></div>
  </dialog>
</template>

<style scoped>
.modal-open {
  pointer-events: auto;
  visibility: visible;
  opacity: 1;
}
</style>
