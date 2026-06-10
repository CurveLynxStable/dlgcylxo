# Описание каталога scripts

Каталог скриптов сопровождения репозитория; не предназначен для обычных конечных пользователей.

## Предварительные требования

- Версия Node.js должна удовлетворять требованиям репозитория (см. `engines.node` в корневом `package.json`).
- Установлен `pnpm`.
- Для `gitflow.mjs` нужен установленный [git-flow-next](https://github.com/gittower/git-flow-next), а `git-flow` должен быть доступен в `PATH`.
- Для цели `py` в `ci-gate.mjs` нужен `uv`.
- Для `rs-check.mjs` нужен тулчейн Rust (`cargo`).

## Текущий список скриптов

- `ci-gate.mjs`
  - Единая точка входа проверок качества, цели: `app`, `py`, `rs`, `all`.
  - `app`: выполняет `postinstall`, `prettier --check`, `eslint`, `vue-tsc`.
  - `py`: в `python-src` выполняет `uv run pyright` и `uv run ruff check .`.
  - `rs`: вызывает `node ./scripts/rs-check.mjs gate`.
- `gitflow.mjs`
  - `setup`: очищает локальную конфигурацию `gitflow.*`, заново выполняет `git-flow init` и настраивает создание tag для release по умолчанию.
  - `finish`: завершает релиз на ветке `release/<version>`: проверяет рабочую копию, версию и конфликты tag, после завершения пушит ветки и tag и возвращается на ветку разработки.
  - Параметры `finish`:
    - `-v, --version` (совместимо с `--Version`)
    - `-r, --remote` (совместимо с `--Remote`)
    - `-m, --main-branch` (совместимо с `--MainBranch`)
    - `-d, --dev-branch` (совместимо с `--DevBranch`)
- `prettier-check-locations.mjs`
  - Находит места несоответствий Prettier и выводит их в формате `file:line:column: message` для перехода через problem matcher редактора.
- `prune-pyembed.mjs`
  - Удаляет из `src-tauri/pyembed/python` содержимое, заведомо не нужное во время выполнения.
  - Сейчас удаляются: `pip`, CLI-обёртки, `ensurepip`, `idlelib`, `tkinter/tcl`, `turtledemo`, `__pycache__`, `.pyc/.pyo`, а также `modules/resources/openssl`.
  - Поддерживает `--dry-run` — только предпросмотр удаляемого без записи в файлы.
- `rs-check.mjs`
  - Точка входа проверок Rust, режимы: `dev` (по умолчанию) и `gate`.
  - `dev`: требует наличия локального pyembed Python, устанавливает `PYO3_PYTHON` и выполняет `cargo fmt` + `cargo check -p mtga-tauri`.
  - `gate`: выполняет `cargo fmt --check` + `cargo check -p mtga-tauri` и подготавливает каталог `src-tauri/pyembed/python`.

## Соответствующие входные точки package.json

- `pnpm gate -- <app|py|rs|all>`
- `pnpm app:gate`
- `pnpm py:gate`
- `pnpm rs:gate`
- `pnpm rs:check`
- `pnpm pyembed:prune`
- `pnpm pyembed:prune:dry-run`
- `pnpm gitflow:setup`
- `pnpm release:push`
- `pnpm release:push -- -v 2.0.0-beta.10 -r origin -m tauri -d dev`

## Локальная сборка Tauri

- `pnpm tauri:bundle:win`
- `pnpm tauri:bundle:mac`

Перечисленные локальные bundle-скрипты сначала выполняют `pnpm pyembed:prune`, затем переходят к сборке Tauri; используемые в CI скрипты `*:ci` это не затрагивает.
