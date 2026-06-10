# Repository Guidelines

## Структура проекта и организация модулей

- `app/`: входная точка фронтенда Nuxt; страница сейчас рендерится из `app/app.vue`.
- `public/`: каталог статических ресурсов (иконки, изображения и т.д.).
- `src-tauri/`: бэкенд Tauri и конфигурация десктопной сборки; ключевые файлы — `src-tauri/src/main.rs`, `src-tauri/src/lib.rs`, `src-tauri/Cargo.toml` и `src-tauri/tauri.conf.json`.
- `python-src/mtga_app/`: исходники Python-бэкенда (`__init__.py`, `__main__.py`), привязка к Tauri через `pytauri-wheel` — рукописный Rust glue-код не нужен.
- `python-src/pyproject.toml`, `python-src/uv.lock`, `python-src/.venv/`: зависимости Python и конфигурация виртуального окружения.
- `src-tauri/icons/` и `src-tauri/capabilities/`: иконки приложения и определения разрешений (capabilities).
- `nuxt.config.ts`, `tsconfig.json`: конфигурация сборки фронтенда и типов.

## Команды сборки, тестирования и разработки

- `pnpm i`: установка зависимостей с запуском `nuxt prepare`.
- `uv sync --project .`: установка runtime-зависимостей Python в `python-src/` (зависимости управляются uv).
- Когда нужно запустить Python, всегда используйте `uv run ...`, не `python ...` напрямую.
- `pnpm dev:all`: запуск dev-серверов фронтенда и бэкенда (по умолчанию `http://localhost:3000`).
- `pnpm pytauri:install:{платформа: win/mac}`: установка бэкенда в tauri.
- `pnpm tauri:dev`: запуск нативного dev-окружения Tauri.
- `pnpm tauri:bundle:{платформа: win/mac} -- --profile bundle-release`: сборка десктопного приложения (зависит от конфигурации в `src-tauri/`).

## Стиль кода и соглашения об именовании

- Однофайловые компоненты Vue используют отступ в 2 пробела и стандартную структуру Nuxt/Vue.
- `package.json` объявлен как ESM (`"type": "module"`), используйте синтаксис `import`.
- Целевая версия Python — 3.13 (см. `python-src/pyproject.toml`), отступ 4 пробела и именование по PEP 8.
- Rust-код находится в `src-tauri/src/`; стиль по умолчанию `rustfmt`, именование `snake_case`.
- Оптимизированный для LLM prompt daisyUI: https://daisyui.com/llms.txt

## Рекомендации по тестированию

- В `package.json` нет скрипта `test`; фиксированный фронтенд-тестовый фреймворк сейчас отсутствует.
- Если добавляете Rust-тесты, запускайте `cargo test` в `src-tauri/` и опишите покрытие в PR.

## Проверки качества

Перед передачей изменений пользователю LLM обязан выполнить проверки качества:

- Любые изменения Python: обязательно `pnpm py:check`.
- Любые изменения YAML: обязательно `pnpm eslint . --fix`.
- Любые изменения Rust: обязательно `pnpm rs:check`.
- Любые изменения JS/TS/Vue: обязательно `pnpm app:check`.

## Коммиты и PR

- Сообщения коммитов — Conventional Commits: `feat: ...`, `feat(tauri): ...`, `chore: ...`.
- В PR указывайте цель изменений, область влияния и способ проверки; для UI или конфигурации Tauri прикладывайте скриншоты и пояснения.

## Безопасность и конфигурация

- При изменении `src-tauri/tauri.conf.json` или `src-tauri/capabilities/` явно описывайте влияние на разрешения.
- Не коммитьте артефакты сборки: `node_modules/`, `src-tauri/target/`, `dist/`, локальный `.venv/`.
