/**
 * Общее управление pending-состоянием асинхронных действий.
 * Одновременно выполняется только одно действие — для состояний loading / disabled кнопок.
 */
export const usePendingAction = <T extends string>() => {
  const runningAction = ref<T | null>(null);

  const runAction = async (action: T, runner: () => Promise<boolean>) => {
    if (runningAction.value) {
      return false;
    }

    runningAction.value = action;
    try {
      return await runner();
    } finally {
      runningAction.value = null;
    }
  };

  return {
    runningAction,
    runAction,
  };
};
