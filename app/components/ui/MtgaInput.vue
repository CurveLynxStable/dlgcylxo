<script setup lang="ts">
/**
 * Стандартный компонент поля ввода MTGA
 * Реализован по спецификациям daisyUI 5 и Tailwind CSS 4
 * Поддерживает размеры, цветовые состояния, загрузку, иконки, очистку и выпадающий список
 */

interface MtgaInputOption {
  value: string;
  label?: string;
  tag?: string;
  disabled?: boolean;
  disabledReason?: string;
}

interface NormalizedMtgaInputOption {
  value: string;
  label: string;
  tag: string;
  disabled: boolean;
  disabledReason: string;
}

interface Props {
  modelValue: string | number;
  label?: string;
  description?: string;
  descriptionClass?: string;
  placeholder?: string;
  type?: string;
  required?: boolean;
  disabled?: boolean;
  loading?: boolean;
  readonly?: boolean;
  /** Размер: 'xs' | 'sm' | 'md' | 'lg' */
  size?: "xs" | "sm" | "md" | "lg";
  /** Цветовое состояние: 'primary' | 'success' | 'warning' | 'error' | 'neutral' */
  color?: "primary" | "success" | "warning" | "error" | "neutral";
  /** Путь левой иконки (SVG path d) */
  icon?: string;
  /** Путь правой иконки (SVG path d) */
  trailingIcon?: string;
  /** Показывать ли кнопку выпадающего списка (имитация Select) */
  showDropdown?: boolean;
  /** Пункты выпадающего списка */
  options?: Array<string | MtgaInputOption>;
  /** Содержимое закреплённой области добавления вверху списка */
  addOptionValue?: string;
  /** Подсказка справа в области добавления */
  addOptionHint?: string;
  /** Показывать ли область добавления вверху списка */
  showAddOption?: boolean;
  /** Отключена ли область добавления */
  addOptionDisabled?: boolean;
  /** Обрабатывать ли пункты в режиме множественного выбора */
  multiSelect?: boolean;
  /** Выбранные пункты в режиме множественного выбора */
  selectedOptions?: string[];
  /** Можно ли очистить */
  clearable?: boolean;
  /** Сообщение об ошибке; если задано, color принудительно error */
  error?: string;
  /** Классы, передаваемые элементу input */
  inputClass?: string;
}

const props = withDefaults(defineProps<Props>(), {
  type: "text",
  size: "md",
  clearable: true,
  label: "",
  description: "",
  descriptionClass: "",
  placeholder: "",
  color: "neutral",
  icon: "",
  trailingIcon: "",
  options: () => [],
  addOptionValue: "",
  addOptionHint: "",
  showAddOption: false,
  addOptionDisabled: false,
  multiSelect: false,
  selectedOptions: () => [],
  error: "",
  inputClass: "",
});

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
  (e: "dropdown"): void;
  (e: "select", value: string): void;
  (e: "add-option", value: string): void;
  (e: "focus"): void;
  (e: "blur"): void;
}>();

const dropdownOpen = ref(false);
const dropdownRef = ref<HTMLElement | null>(null);
const isPositioned = ref(false);
const isFiltering = ref(false); // Признак фильтрации (true только при вводе после открытия списка)
const slots = useSlots();

// Стили позиционирования выпадающего меню
const dropdownStyle = ref<Record<string, string | number>>({});

/**
 * Обновление позиции выпадающего меню
 * Позиция поля вычисляется через getBoundingClientRect
 */
const updateDropdownPosition = () => {
  if (!dropdownRef.value || !dropdownOpen.value) return;

  const rect = dropdownRef.value.getBoundingClientRect();
  // Если снизу недостаточно места — открываем вверх (простая реализация)
  const spaceBelow = window.innerHeight - rect.bottom;
  const hasSpaceBelow = spaceBelow > 250; // Максимальная высота списка ≈ 240px

  dropdownStyle.value = {
    position: "fixed",
    top: hasSpaceBelow ? `${rect.bottom + 6}px` : "auto",
    bottom: !hasSpaceBelow ? `${window.innerHeight - rect.top + 6}px` : "auto",
    left: `${rect.left}px`,
    width: `${rect.width}px`,
    zIndex: 9999,
  };

  // Откладываем на кадр, чтобы стили успели примениться к DOM
  requestAnimationFrame(() => {
    isPositioned.value = true;
  });
};

// Слушаем события окна для синхронизации позиции
watch(dropdownOpen, async (val) => {
  if (val) {
    isPositioned.value = false;
    isFiltering.value = false; // При открытии сбрасываем фильтр и показываем полный список
    dropdownStyle.value = {}; // Сброс стилей
    await nextTick();
    updateDropdownPosition();
    window.addEventListener("scroll", updateDropdownPosition, true);
    window.addEventListener("resize", updateDropdownPosition);
  } else {
    window.removeEventListener("scroll", updateDropdownPosition, true);
    window.removeEventListener("resize", updateDropdownPosition);
    isPositioned.value = false;
    isFiltering.value = false;
  }
});

// Соответствие стилей
const inputSizeClass = computed(() => {
  const sizes = {
    xs: "px-2 py-1",
    sm: "px-3 py-1.5",
    md: "px-3.5 py-2",
    lg: "px-4 py-2.5",
  };
  return sizes[props.size];
});

const hasActionArea = computed(() => {
  return props.loading || props.showDropdown || slots.trailing || props.trailingIcon;
});

const normalizedOptions = computed<NormalizedMtgaInputOption[]>(() =>
  props.options.map((option) => {
    if (typeof option === "string") {
      return {
        value: option,
        label: option,
        tag: "",
        disabled: false,
        disabledReason: "",
      };
    }
    return {
      value: option.value,
      label: option.label || option.value,
      tag: option.tag || "",
      disabled: option.disabled === true,
      disabledReason: option.disabledReason || "",
    };
  }),
);
const selectedOptionSet = computed(() => new Set(props.selectedOptions));
const isOptionSelected = (option: string) => {
  if (props.multiSelect) {
    return selectedOptionSet.value.has(option);
  }
  return props.modelValue === option;
};

// Расчёт ширины суффиксной зоны для динамических отступов поля
const suffixPaddingClass = computed(() => {
  let actionCount = 0;
  if (props.loading) actionCount++;
  if (props.showDropdown) actionCount++;
  if (props.trailingIcon || slots.trailing) actionCount++;

  const hasClear = props.clearable && props.modelValue && !props.disabled && !props.readonly;

  // Разделитель и суффиксные кнопки есть только при actionCount > 0
  if (actionCount > 0) {
    if (hasClear) return "pr-24"; // Кнопка очистки + разделитель + суффиксные кнопки
    return "pr-16"; // Разделитель + суффиксные кнопки
  }

  if (hasClear) return "pr-10"; // Только кнопка очистки
  return "pr-3.5"; // По умолчанию
});

// Закрытие списка по клику снаружи
const handleClickOutside = (event: MouseEvent) => {
  const target = event.target;
  if (dropdownRef.value && target instanceof Node && !dropdownRef.value.contains(target)) {
    dropdownOpen.value = false;
  }
};

onMounted(() => {
  document.addEventListener("click", handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener("click", handleClickOutside);
});

const toggleDropdown = (e: Event) => {
  e.stopPropagation();
  if (props.disabled || props.loading) return;
  if (!dropdownOpen.value) {
    emit("dropdown");
  }
  dropdownOpen.value = !dropdownOpen.value;
};

const handleSelect = (option: NormalizedMtgaInputOption) => {
  if (option.disabled) {
    return;
  }
  if (props.multiSelect) {
    emit("select", option.value);
    isFiltering.value = false;
    dropdownOpen.value = true;
    return;
  }
  emit("update:modelValue", option.value);
  emit("select", option.value);
  dropdownOpen.value = false;
};

const handleAddOption = () => {
  if (props.addOptionDisabled) {
    return;
  }
  emit("add-option", props.addOptionValue);
  isFiltering.value = false;
  dropdownOpen.value = true;
};

const handleAddOptionEnter = (e: KeyboardEvent) => {
  if (e.isComposing || !props.showAddOption) {
    return;
  }
  e.preventDefault();
  handleAddOption();
};

const handleInput = (e: Event) => {
  if (e.target instanceof HTMLInputElement) {
    const val = e.target.value;
    emit("update:modelValue", val);

    // Если Popover открыт и есть пункты — при вводе держим его открытым и фильтруем
    if (props.showDropdown && (normalizedOptions.value.length > 0 || props.showAddOption)) {
      dropdownOpen.value = true;
      isFiltering.value = true; // Началась фильтрация
    }
  }
};

// Отфильтрованные пункты
const filteredOptions = computed(() => {
  if (!normalizedOptions.value.length) return [];
  // Если фильтрация не активна (список только открыт) — показываем всё
  if (!isFiltering.value) return normalizedOptions.value;

  const search = String(props.modelValue).toLowerCase().trim();
  if (!search) return normalizedOptions.value;
  return normalizedOptions.value.filter((opt) =>
    opt.tag || isOptionSelected(opt.value)
      ? true
      : `${opt.label} ${opt.value}`.toLowerCase().includes(search),
  );
});

const handleClear = (e: MouseEvent) => {
  e.stopPropagation(); // Останавливаем всплытие, чтобы клик не закрыл список
  emit("update:modelValue", "");
  isFiltering.value = true; // Очистка считается фильтрацией — показываем все пункты
  // При очистке список не закрывается
};
</script>

<template>
  <div class="form-control w-full">
    <!-- Область верхней метки -->
    <div v-if="label" class="label py-1">
      <span
        class="label-text font-medium flex items-center gap-0.5"
        :class="[size === 'xs' ? 'text-xs' : 'text-sm', error ? 'text-error' : 'text-slate-600']"
      >
        {{ label }}
        <span v-if="required" class="text-error ml-0.5">*</span>
      </span>
    </div>

    <!-- Обёртка поля ввода -->
    <div
      ref="dropdownRef"
      class="relative flex items-center group transition-all duration-150 ease-out border rounded-xl shadow-sm"
      :class="[
        error
          ? 'border-error/50 bg-error/5'
          : 'border-slate-200 bg-slate-100/70 focus-within:bg-white focus-within:border-primary focus-within:ring-4 focus-within:ring-primary/20',
        disabled || loading
          ? 'opacity-60 cursor-not-allowed'
          : 'hover:border-primary/40 hover:bg-white',
      ]"
    >
      <!-- Префиксный слот / иконка -->
      <div
        v-if="$slots.leading || icon"
        class="absolute left-3 flex items-center justify-center pointer-events-none transition-colors duration-150"
        :class="[
          size === 'xs' ? 'w-4' : 'w-5',
          error
            ? 'text-error/70'
            : 'text-slate-400 group-hover:text-primary/60 group-focus-within:text-primary',
        ]"
      >
        <slot name="leading">
          <svg
            v-if="icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="w-full h-full"
          >
            <path :d="icon" />
          </svg>
        </slot>
      </div>

      <!-- Основное поле ввода -->
      <input
        :value="modelValue"
        :type="type"
        :placeholder="placeholder"
        :disabled="disabled || loading"
        :readonly="readonly"
        class="w-full bg-transparent outline-none transition-all duration-150 border-none focus:ring-0"
        :class="[
          inputSizeClass,
          suffixPaddingClass,
          $slots.leading || icon ? 'pl-10' : 'pl-3.5',
          size === 'xs' ? 'h-7 text-xs' : size === 'sm' ? 'h-8 text-sm' : 'h-10 text-sm',
          inputClass,
        ]"
        @input="handleInput"
        @keydown.enter="handleAddOptionEnter"
        @focus="emit('focus')"
        @blur="emit('blur')"
      />

      <!-- Кнопка очистки (отдельно от зоны действий, слева от разделителя) -->
      <button
        v-if="clearable && modelValue && !disabled && !readonly"
        type="button"
        class="absolute btn btn-ghost btn-circle btn-xs text-slate-400 hover:text-error hover:bg-error/10 transition-all duration-200 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
        :class="[hasActionArea ? 'right-11' : 'right-2.5']"
        title="Очистить"
        @click="handleClear"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          class="h-3.5 w-3.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>

      <!-- Суффиксная зона действий (с разделителем) -->
      <div v-if="hasActionArea" class="absolute right-0 top-0 bottom-0 flex items-center pr-2">
        <!-- Разделитель -->
        <div
          class="h-1/2 w-px bg-slate-200 mx-1 group-hover:bg-primary/20 group-focus-within:bg-primary/30 transition-colors"
        ></div>

        <div class="flex items-center gap-1">
          <!-- Кнопка выпадающего списка (имитация Select) -->
          <button
            v-if="showDropdown"
            type="button"
            class="btn btn-ghost btn-circle btn-xs text-slate-400 hover:text-primary transition-all duration-200"
            :class="{ 'rotate-180 text-primary bg-primary/10': dropdownOpen }"
            @click="toggleDropdown"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </button>

          <!-- Пользовательский суффиксный слот / иконка -->
          <div
            v-if="$slots.trailing || trailingIcon"
            class="flex items-center justify-center transition-colors px-1"
            :class="[
              size === 'xs' ? 'w-4' : 'w-5',
              error ? 'text-error/70' : 'text-slate-400 group-focus-within:text-primary/70',
            ]"
          >
            <slot name="trailing">
              <svg
                v-if="trailingIcon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                class="w-full h-full"
              >
                <path :d="trailingIcon" />
              </svg>
            </slot>
          </div>
        </div>
      </div>

      <!-- Панель списка (Teleport как Portal — решает проблему overflow родителя) -->
      <Teleport to="body">
        <div
          v-if="showDropdown && dropdownOpen && isPositioned"
          :style="dropdownStyle"
          class="bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden animate-in fade-in zoom-in duration-300 origin-top"
          @click.stop
        >
          <!-- Оверлей загрузки (центрированная анимация + размытие) -->
          <div
            v-if="loading"
            class="absolute inset-0 z-10 flex items-center justify-center bg-white/40 backdrop-blur-[2px] transition-all duration-300"
          >
            <div class="flex flex-col items-center gap-2">
              <span class="loading loading-spinner loading-md text-primary"></span>
              <span class="text-[10px] text-slate-500 font-medium">Загрузка...</span>
            </div>
          </div>

          <div
            v-if="!showAddOption && (!filteredOptions || filteredOptions.length === 0)"
            class="px-4 py-6 text-center"
          >
            <p class="text-slate-400 text-xs">Нет совпадений</p>
          </div>

          <ul
            v-else
            class="menu flex-col flex-nowrap p-1 max-h-[240px] overflow-auto custom-scrollbar w-full"
          >
            <li v-if="showAddOption" class="sticky top-0 z-1 bg-white pb-1">
              <button
                type="button"
                class="grid w-full cursor-pointer grid-cols-[minmax(0,1fr)_6rem] items-center gap-2 rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-sm transition-colors duration-200 hover:border-primary/40 hover:bg-primary/5 disabled:cursor-not-allowed disabled:hover:border-slate-200 disabled:hover:bg-slate-50"
                :disabled="addOptionDisabled"
                @click="handleAddOption"
              >
                <span class="truncate text-left font-mono text-slate-700">
                  {{ addOptionValue }}
                </span>
                <span class="w-24 shrink-0 text-right text-xs text-slate-400">
                  {{ addOptionHint || "Нажмите, чтобы добавить ID" }}
                </span>
              </button>
            </li>

            <li v-if="filteredOptions.length === 0 && !showAddOption" class="px-4 py-6 text-center">
              <p class="text-slate-400 text-xs">Нет совпадений</p>
            </li>

            <li v-for="opt in filteredOptions" :key="`${opt.value}:${opt.tag || 'api'}`">
              <button
                type="button"
                class="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-all duration-200"
                :class="[
                  opt.disabled
                    ? 'cursor-not-allowed text-slate-300'
                    : 'cursor-pointer hover:bg-primary/5 hover:text-primary',
                  !opt.disabled && isOptionSelected(opt.value)
                    ? 'bg-primary/10 text-primary font-medium'
                    : '',
                ]"
                :disabled="opt.disabled"
                :title="opt.disabledReason || undefined"
                @click="handleSelect(opt)"
              >
                <span class="truncate flex-1 text-left">{{ opt.label }}</span>
                <span
                  v-if="opt.tag"
                  class="shrink-0 rounded-full border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700"
                >
                  {{ opt.tag }}
                </span>
                <svg
                  v-if="!opt.disabled && isOptionSelected(opt.value)"
                  xmlns="http://www.w3.org/2000/svg"
                  class="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </button>
            </li>
          </ul>
        </div>
      </Teleport>
    </div>

    <!-- Описание / сообщение об ошибке -->
    <div v-if="description || error" class="label py-1 min-h-[24px]">
      <span
        class="label-text-alt transition-all duration-300 ease-out flex items-center gap-1"
        :class="[
          error ? 'text-error font-medium text-[11px]' : ['text-slate-400', descriptionClass],
        ]"
      >
        <template v-if="error">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="w-3.5 h-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          {{ error }}
        </template>
        <template v-else>
          {{ description }}
        </template>
      </span>
    </div>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 10px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: var(--color-primary, #f0bb32);
}
</style>
