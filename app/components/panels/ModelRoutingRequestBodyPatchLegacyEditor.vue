<script setup lang="ts">
const REQUEST_BODY_PATCH_TOOLTIP = [
  "Формат: массив JSON Patch, правила применяются сверху вниз.",
  "path использует JSON Pointer: /thinking — поле корневого объекта, /tools/0 — первый элемент массива;",
  "value может быть строкой, числом, булевым, объектом или массивом.",
  "add: добавить поле или элемент массива.",
  "remove: удалить существующее поле или элемент массива.",
  "replace: заменить значение существующего поля.",
  "copy: скопировать значение из from в path.",
  "move: переместить значение из from в path, исходное место очищается.",
  "test: проверить, что текущее значение path равно value; при ошибке правка параметров отклоняется.",
  "Ограничение: изменение stream не допускается.",
].join("\n");

const props = withDefaults(
  defineProps<{
    modelValue: string;
    open?: boolean;
  }>(),
  {
    open: false,
  },
);

const emit = defineEmits<{
  (event: "update:modelValue", value: string): void;
  (event: "update:open", value: boolean): void;
}>();

const isOpen = computed({
  get: () => props.open,
  set: (value) => {
    emit("update:open", value);
  },
});

const updateModelValue = (event: Event) => {
  if (event.target instanceof HTMLTextAreaElement) {
    emit("update:modelValue", event.target.value);
  }
};
</script>

<template>
  <details
    class="tooltip mtga-tooltip block w-full rounded-xl border border-slate-200/70 bg-slate-50/60 px-4 py-3"
    :data-tip="REQUEST_BODY_PATCH_TOOLTIP"
    style="--mtga-tooltip-max: 520px"
    :open="isOpen"
    @toggle="isOpen = ($event.target as HTMLDetailsElement).open"
  >
    <summary
      class="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-semibold text-slate-700"
    >
      <span class="flex min-w-0 items-center gap-2">
        <span>Правка параметров</span>
      </span>
      <span
        class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-500"
      >
        JSON Patch
      </span>
    </summary>
    <div class="mt-3">
      <textarea
        :value="modelValue"
        class="min-h-36 w-full resize-y rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-xs leading-5 text-slate-800 outline-none transition focus:border-amber-300 focus:ring-4 focus:ring-amber-100"
        spellcheck="false"
        placeholder='[
  {"op":"add","path":"/thinking","value":{"type":"enabled","budget_tokens":1024}},
  {"op":"replace","path":"/temperature","value":0.2},
  {"op":"add","path":"/tools/0","value":{"type":"web_search"}},
  {"op":"copy","from":"/metadata/user_id","path":"/user"},
  {"op":"test","path":"/model","value":"Qwen/Qwen3.5-27B"}
]'
        @input="updateModelValue"
      ></textarea>
      <div class="mt-2 text-xs leading-5 text-slate-500">
        Эти правила имеют приоритет над адаптером провайдера — используйте осторожно,
        ответственность на вас.
      </div>
    </div>
  </details>
</template>
