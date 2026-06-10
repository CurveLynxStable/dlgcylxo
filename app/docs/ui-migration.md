# Обзор миграции UI (Nuxt + Tailwind + daisyUI)

Этот файл объединяет прежний анализ/план/описание конфигурации и служит руководством по миграции с Tkinter UI на `mtga-tauri/app/`.

## Цели миграции и разбиение на компоненты

- Макет уровня страницы: `AppShell` (заголовок + колонки)
- Основные компоненты:
  - `ConfigGroupPanel`, `GlobalConfigPanel`, `RuntimeOptionsPanel`
  - `MainTabs` + компоненты вкладок
  - `LogPanel`, `FooterActions`
  - `UpdateDialog`, `ConfirmDialog`

## Рекомендуемый каркас страницы (структура каталогов)

```
app/
  app.vue
  components/
    AppShell.vue
    LogPanel.vue
    FooterActions.vue
    panels/
      ConfigGroupPanel.vue
      GlobalConfigPanel.vue
      RuntimeOptionsPanel.vue
    tabs/
      MainTabs.vue
      CertTab.vue
      HostsTab.vue
      ProxyTab.vue
      DataManagementTab.vue
      AboutTab.vue
    dialogs/
      UpdateDialog.vue
      ConfirmDialog.vue
```

## Рекомендуемый порядок миграции

1. Макет + панель логов
2. Группы конфигурации / глобальная конфигурация / параметры рантайма
3. Функциональные вкладки (Tabs)
4. Диалог обновления и диалог подтверждения

## Сводка текущего прогресса (для восстановления контекста)

- Выбран технологический стек UI: Tailwind + daisyUI (CSS-first конфигурация на базе daisyUI 5 / Tailwind v4).
- Создан каркас компонентов: `AppShell`, `LogPanel`, `FooterActions`, `panels/*`, `tabs/*`, `dialogs/*`.
- Каркасный макет подключён в `mtga-tauri/app/app.vue`: панель + вкладки слева, панель логов справа, кнопки внизу.
- Подтверждён способ взаимодействия: фронтенд вызывает команды Python-бэкенда через `pyInvoke` (pytauri-wheel).

## TODO (чек-лист следующих шагов)

- [x] Установить и включить Tailwind + daisyUI (создать `mtga-tauri/app/assets/css/tailwind.css`, подключить в `mtga-tauri/nuxt.config.ts`).
- [x] `MainTabs` поддерживает переключение и монтирует содержимое вкладок (сертификаты/hosts/прокси/данные/о программе).
- [x] `ConfigGroupPanel` сделан интерактивным: данные списка, состояние выбора, диалоги добавления/изменения/удаления.
- [x] `GlobalConfigPanel` и `RuntimeOptionsPanel` подключены к реальным данным и логике сохранения.
- [x] `LogPanel` поддерживает поток добавляемых логов (события бэкенда или фронтенда).
- [x] `UpdateDialog` и диалог подтверждения: доработано взаимодействие и рендер HTML-контента.
- [x] Минимальная функциональная цепочка через `pyInvoke` (например, `greet` -> вывод в лог).

## Обзор функциональности существующего UI

- **Общий макет**: заголовок + две колонки, слева зона действий, справа прокручиваемая панель логов.
- **Зона конфигурации**: список групп конфигурации (добавление/изменение/удаление/вверх/вниз/проверка/обновление), глобальная конфигурация (маппинг ID модели / ключ авторизации MTGA).
- **Параметры рантайма**: режим отладки, отключение строгого режима SSL, принудительный потоковый режим.
- **Функциональные вкладки**:
  - Управление сертификатами: генерация / установка / очистка (с диалогом подтверждения)
  - Файл hosts: изменение / резервная копия / восстановление / открытие
  - Операции прокси: запуск / остановка / проверка сетевого окружения
  - Управление пользовательскими данными (только в собранном виде): открыть каталог / резервная копия / восстановление / очистка
  - О программе: информация о версии + проверка обновлений
- **Диалог обновления**: показ HTML release notes + переход на страницу релиза

## Способ взаимодействия (pytauri-wheel)

Фронтенд вызывает Python-бэкенд через `tauri-plugin-pytauri-api`:

```ts
import { pyInvoke } from "tauri-plugin-pytauri-api";
const msg = await pyInvoke("greet", { name: "bifang" });
```

Необходимые возможности: чтение/запись конфигурации, операции с сертификатами/hosts/прокси, управление пользовательскими данными, проверка обновлений, флаги среды выполнения.

## Контракт фронтенд–бэкенд (команды pyInvoke)

### Реализовано

```
greet({ name: string }) -> string

load_config() -> {
  config_groups: ConfigGroup[]
  current_config_index: number
  mapped_model_id: string
  mtga_auth_key: string
}

save_config({
  config_groups: ConfigGroup[]
  current_config_index: number
  mapped_model_id?: string
  mtga_auth_key?: string
}) -> boolean

get_app_info() -> {
  display_name: string
  version: string
  github_repo: string
  ca_common_name: string
  api_key_visible_chars: number
}

is_packaged() -> boolean
```

### Предстоит реализовать (в порядке подключения кнопок UI)

```
generate_certificates()
install_ca_cert()
clear_ca_cert({ ca_common_name?: string })

hosts_modify({ mode: "add" | "backup" | "restore" | "remove" })
hosts_open()

proxy_start()
proxy_stop()
proxy_check_network()
proxy_start_all()

user_data_open_dir()
user_data_backup()
user_data_restore_latest()
user_data_clear()

check_updates()
```

## Определение полей состояния (фронтенд store)

```
config_groups: ConfigGroup[]
current_config_index: number
mapped_model_id: string
mtga_auth_key: string
runtime_options: {
  debugMode: boolean
  disableSslStrict: boolean
  forceStream: boolean
  streamMode: "true" | "false"
}
logs: string[]
app_info: {
  display_name: string
  version: string
  github_repo: string
  ca_common_name: string
  api_key_visible_chars: number
}
show_data_tab: boolean
```

## Структура ConfigGroup

```
type ConfigGroup = {
  name?: string
  api_url: string
  model_id: string
  api_key: string
  middle_route?: string
  target_model_id?: string
  mapped_model_id?: string
}
```

## Соответствие функций старого Tkinter → кнопок нового UI

```
ConfigGroupPanel:
  Проверка -> test_chat_completion
  Обновить -> load_config
  Добавить/Изменить/Удалить/Вверх/Вниз -> save_config

GlobalConfigPanel:
  Сохранить глобальную конфигурацию -> save_config

RuntimeOptionsPanel:
  Отладка/SSL/потоковый режим -> только состояние фронтенда, передаётся бэкенду при запуске прокси

CertTab:
  Сгенерировать CA и серверный сертификат -> generate_certificates
  Установить CA-сертификат -> install_ca_cert
  Удалить системный CA-сертификат -> clear_ca_cert

HostsTab:
  Изменить файл hosts -> hosts_modify(add)
  Резервная копия hosts -> hosts_modify(backup)
  Восстановить hosts -> hosts_modify(restore)
  Открыть файл hosts -> hosts_open

ProxyTab:
  Запустить прокси-сервер -> proxy_start
  Остановить прокси-сервер -> proxy_stop
  Проверить сетевое окружение -> proxy_check_network

FooterActions:
  Запустить всё одной кнопкой -> proxy_start_all

DataManagementTab (только в собранном виде):
  Открыть каталог -> user_data_open_dir
  Резервная копия -> user_data_backup
  Восстановить данные -> user_data_restore_latest
  Очистить данные -> user_data_clear

AboutTab:
  Проверить обновления -> check_updates
```

## Минимальная интеграция Tailwind + daisyUI (по daisyUI 5 / Tailwind v4)

Зависимости (пример для pnpm):

```bash
pnpm add -D tailwindcss daisyui
```

`mtga-tauri/app/assets/css/tailwind.css`:

```css
@import "tailwindcss";
@plugin "daisyui";

/* Тема (опционально): сначала используем light как тему по умолчанию */
@plugin "daisyui" {
  themes: light --default;
}
```

Подключение стилей в `mtga-tauri/nuxt.config.ts`:

```ts
export default defineNuxtConfig({
  css: ["./app/assets/css/tailwind.css"],
});
```

Часто используемые классы компонентов:

- Tabs: `tabs` / `tab`
- Dialog: `modal` / `modal-box`
- Tooltip: `tooltip`
- Таблицы: `table`
- Формы: `input` / `select` / `checkbox`
- Кнопки: `btn` + `btn-primary/secondary`

## Методика разработки в период миграции

### Инженерия бэкенда

В `mtga-tauri/python-src`:

```bash
uv venv
uv pip install -e .
```

### Запуск фронтенда

В `mtga-tauri/app`:

```bash
pnpm dev
```

### Запуск бэкенда

В `mtga-tauri/python-src`:

```pwsh
$env:DEV_SERVER="http://localhost:3000"; $env:MTGA_SRC_TAURI_DIR="..\\src-tauri"; uv run python -m mtga_app
```

## Сборка: встраивание Python (Tauri bundle)

### 1) Подготовка встроенного интерпретатора

- Сначала нужно подготовить каталог `mtga-tauri/src-tauri/pyembed/...`.
- Распакуйте `python-build-standalone` в `mtga-tauri/src-tauri/pyembed/`:
  - Windows: `mtga-tauri/src-tauri/pyembed/python/python.exe`
  - macOS: `mtga-tauri/src-tauri/pyembed/python/bin/python3`

### 2) Установка бэкенда во встроенный интерпретатор

В `mtga-tauri/src-tauri`:

Windows:

```pwsh
$env:PYTAURI_STANDALONE="1"
uv pip install --exact --python ".\pyembed\python\python.exe" --reinstall-package mtga-app "..\python-src"
```

macOS:

```zsh
export PYTAURI_STANDALONE="1"
uv pip install --exact --python "./pyembed/python/bin/python3" --reinstall-package mtga-app "../python-src"
```

### 3) Размещение .env (опционально)

По умолчанию обязательные переменные окружения не требуются; чтобы переопределить автоматически определяемый каталог ресурсов, можно разместить `.env` так, чтобы встроенный интерпретатор мог его прочитать:

- Windows: `mtga-tauri/src-tauri/pyembed/python/Lib/.env`
- macOS: `mtga-tauri/src-tauri/pyembed/python/lib/python3.13/.env` (скорректируйте по фактической версии)

Сейчас поддерживается только опциональная переменная:

- `MTGA_RESOURCE_DIR`: переопределяет автоматическое определение каталога ресурсов

Также можно задать в лаунчере `MTGA_ENV_FILE` с абсолютным путём к `.env`.

### 4) Настройка tauri-cli (только для сборки)

Создайте `mtga-tauri/src-tauri/tauri.bundle.json`:

```json
{
  "bundle": {
    "active": true,
    "targets": "all",
    "resources": {
      "pyembed/python": "./"
    }
  }
}
```

> Не вписывайте `bundle.resources` в `tauri.conf.json` — передавайте через `--config`.

Также рекомендуется добавить в `mtga-tauri/src-tauri/.taurignore`:

```
/pyembed/
```

чтобы `tauri dev` не копировал каждый раз огромный каталог интерпретатора.

Добавьте в `mtga-tauri/src-tauri/Cargo.toml`:

```toml
[profile.bundle-dev]
inherits = "dev"

[profile.bundle-release]
inherits = "release"
```

### 5) Build & Bundle (переменные окружения + финальная команда сборки)

**Вернитесь в корневой каталог `mtga-tauri`.**
Задайте Python для этапа компиляции:

```pwsh
$env:PYO3_PYTHON = (Resolve-Path -LiteralPath ".\src-tauri\pyembed\python\python.exe").Path
```

Для macOS дополнительно:

```zsh
export PYO3_PYTHON=$(realpath ./src-tauri/pyembed/python/bin/python3)
export RUSTFLAGS=" \
  -C link-arg=-Wl,-rpath,@executable_path/../Resources/lib \
  -L $(realpath ./src-tauri/pyembed/python/lib)"
install_name_tool -id '@rpath/libpython3.13.dylib' \
  ./src-tauri/pyembed/python/lib/libpython3.13.dylib
```

Финальная сборка:

```bash
pnpm -- tauri build --config="src-tauri/tauri.bundle.json" -- --profile bundle-release
```

### Настройка иконок инсталлятора/приложения для Windows

1. **Иконка NSIS-инсталлятора (setup.exe)**
   В `mtga-tauri/src-tauri/tauri.conf.json`:

```json
"bundle": {
  "windows": {
    "nsis": {
      "installerIcon": "icons/icon.ico"
    }
  }
}
```

2. **Иконка приложения (окно программы/панель задач/ярлык)**
   В том же файле в `bundle.icon` укажите `.ico` (Windows):

```json
"bundle": {
  "icon": [
    "icons/icon.ico"
  ]
}
```

3. **Картинки интерфейса MSI-инсталлятора (WiX banner/dialog BMP)**
   В `mtga-tauri/src-tauri/tauri.conf.json`:

```json
"bundle": {
  "windows": {
    "wix": {
      "bannerPath": "icons/wix-banner.bmp",
      "dialogImagePath": "icons/wix-dialog.bmp"
    }
  }
}
```

### Генерация картинок MSI (быстрая генерация в PowerShell)

Сгенерируйте из существующего логотипа две BMP-картинки, необходимые WiX:

```pwsh
Add-Type -AssemblyName System.Drawing
$logoPath = (Resolve-Path -LiteralPath ".\src-tauri\icons\128x128@2x.png").Path
$logo = [System.Drawing.Image]::FromFile($logoPath)

$iconsDir = (Resolve-Path -LiteralPath ".\src-tauri\icons").Path

# banner 493x58
$banner = New-Object System.Drawing.Bitmap 493,58
$g1 = [System.Drawing.Graphics]::FromImage($banner)
$g1.Clear([System.Drawing.Color]::White)
$g1.DrawImage($logo, 10, 4, 50, 50)
$banner.Save((Join-Path $iconsDir "wix-banner.bmp"), [System.Drawing.Imaging.ImageFormat]::Bmp)

# dialog 493x312
$dialog = New-Object System.Drawing.Bitmap 493,312
$g2 = [System.Drawing.Graphics]::FromImage($dialog)
$g2.Clear([System.Drawing.Color]::White)
$g2.DrawImage($logo, 20, 20, 80, 80)
$dialog.Save((Join-Path $iconsDir "wix-dialog.bmp"), [System.Drawing.Imaging.ImageFormat]::Bmp)
```

## Согласование модулей/ресурсов бэкенда Tauri (ключевые договорённости)

- Используется «схема копирования»: `mtga-tauri/python-src/modules` — источник основной логики на стороне Tauri, корневой `modules` репозитория используется только старым GUI.
- `mtga-tauri/.env` — опциональная точка конфигурации (поддерживается переопределение пути через `MTGA_ENV_FILE`); по умолчанию настройка не нужна, сейчас остаётся только `MTGA_RESOURCE_DIR` для переопределения каталога ресурсов.
- `mtga-tauri/python-src/mtga_app/__init__.py` загружает `mtga-tauri/.env` максимально рано; пакет `modules` сейчас жёстко импортируется из `python-src/modules`.
- При запуске из `python-src` в период разработки нужно задать `MTGA_SRC_TAURI_DIR`, указывающий на `src-tauri` (для поиска `tauri.conf.json`).
- Договорённость о каталоге ресурсов: `mtga-tauri/python-src/modules/resources/{ca,openssl}`; `ResourceManager` сначала использует ресурсы пакета,
  затем локальные `mtga-tauri/python-src/modules/resources`, при необходимости можно переопределить через `MTGA_RESOURCE_DIR`.
- Иконка приложения обрабатывается Tauri (`mtga-tauri/src-tauri/icons` + `mtga-tauri/tauri.conf.json`) и не входит в ресурсы Python.
- В `mtga-tauri/python-src/pyproject.toml` уже объявлены ресурсы пакета `modules` (`resources/ca`, `resources/openssl`).
