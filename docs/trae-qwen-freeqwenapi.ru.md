# Trae + Qwen через MTGA и FreeQwenApi (инструкция на русском)

Эта инструкция описывает, как использовать **бесплатные модели Qwen** в **Trae IDE**
с помощью связки:

- **FreeQwenApi** — локальный OpenAI-совместимый прокси к Qwen Chat
  (`http://localhost:3264/api`);
- **MTGA** — перенаправляет запросы моделей Trae на ваш собственный
  OpenAI-совместимый endpoint (этот репозиторий).

Схема:

```text
Trae IDE  →  MTGA (127.0.0.1:18083)  →  FreeQwenApi (127.0.0.1:3264)  →  Qwen Chat
```

## 1. Требования (Windows)

- Windows 10/11;
- установленный Trae (например, `C:\Users\<вы>\AppData\Local\Programs\Trae`);
- [Node.js LTS](https://nodejs.org/) (для FreeQwenApi);
- папка для проектов, например `E:\AI` (FreeQwenApi уже в `E:\AI\FreeQwenApi`);
- аккаунт Qwen Chat (бесплатная регистрация на <https://chat.qwen.ai>).

## 2. Установка и запуск FreeQwenApi

```bat
cd /d E:\AI\FreeQwenApi
npm install
npm run auth        :: откроется Chromium — войдите в Qwen Chat
npm run models:sync
```

Запуск сервера:

```bat
set SKIP_ACCOUNT_MENU=1
npm start
```

Проверка: откройте <http://localhost:3264/api/health> — должен вернуться JSON со
статусом. Список моделей: <http://localhost:3264/api/models>.

## 3. Установка MTGA

Вариант А — готовая сборка: скачайте установщик из раздела Releases вашего
репозитория (или соберите через GitHub Actions, workflow
`build-prerelease-tauri.yml`).

Вариант Б — локальная сборка (требуются Node 24, pnpm 10.32.1, Rust, uv):

```bat
cd /d E:\AI\mtga
pnpm i
cd python-src && uv sync --project . && cd ..
pnpm pytauri:install:win
pnpm tauri:bundle:win -- --profile bundle-release
```

## 4. Настройка MTGA

1. Запустите MTGA.
2. На вкладке **Прокси** добавьте группу конфигурации (Цели апстрима → Добавить):
   - **API URL**: `http://127.0.0.1:3264/api`
   - **API key**: любое значение (например, `sk-local`) — FreeQwenApi его не проверяет;
   - **Провайдер**: OpenAI-совместимый (Chat Completions);
   - **ID модели**: `qwen3.7-max` (или другая модель из
     `http://localhost:3264/api/models`).
3. В разделе **Публикуемые модели** опубликуйте нужные модели.
4. Нажмите «Проверить модель» — должно появиться `✅ Проверка модели успешна`.
5. Запустите прокси (кнопка запуска на вкладке Прокси).

## 5. Настройка Trae

Используйте режим «официальный Base URL» (по умолчанию):

1. В MTGA включите перенаправление — Trae будет ходить на
   `http://127.0.0.1:18083/v1`.
2. Перезапустите Trae.
3. В Trae выберите модель, опубликованную в MTGA (например, `qwen3.7-max`).

Если используется режим Trae native — укажите в настройках MTGA путь к Trae:
`C:\Users\<вы>\AppData\Local\Programs\Trae`.

## 6. Автозапуск (опционально)

Создайте `E:\AI\start-qwen.bat`:

```bat
@echo off
cd /d E:\AI\FreeQwenApi
set SKIP_ACCOUNT_MENU=1
start "FreeQwenApi" cmd /k npm start
```

и добавьте ярлык в автозагрузку (`shell:startup`), затем запускайте MTGA.

## 7. Типичные проблемы

| Симптом                                                | Решение                                                                      |
| ------------------------------------------------------ | ---------------------------------------------------------------------------- |
| `Не найдено ни одного аккаунта` при старте FreeQwenApi | выполните `npm run auth` и войдите в Qwen Chat                               |
| `❌ Тайм-аут получения списка моделей` в MTGA          | проверьте, запущен ли FreeQwenApi (`http://localhost:3264/api/health`)       |
| Trae не видит модели                                   | убедитесь, что прокси MTGA запущен и модели опубликованы; перезапустите Trae |
| Лимиты Qwen                                            | добавьте второй аккаунт: `npm run auth -- --add` (ротация автоматическая)    |
