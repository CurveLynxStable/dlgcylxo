# MTGA

<picture>
    <img alt="MTGA" src="https://github.com/BiFangKNT/mtga/blob/gui/icons/hero-img_f0bb32.png?raw=true">
</picture>

[![English](https://img.shields.io/badge/docs-English-purple)](docs/README.en.md) [![Русский](https://img.shields.io/badge/доки-Русский-darkblue)](README.md) [![日本語](https://img.shields.io/badge/ドキュ-日本語-b7003a)](docs/README.ja.md) [![한국어 문서](https://img.shields.io/badge/docs-한국어-green)](docs/README.ko.md) [![Documentación en Español](https://img.shields.io/badge/docs-Español-orange)](docs/README.es.md) [![Documentation en Français](https://img.shields.io/badge/docs-Français-blue)](docs/README.fr.md) [![Documentação em Português (Brasil)](https://img.shields.io/badge/docs-Português-purple)](docs/README.pt.md) [![Dokumentation auf Deutsch](https://img.shields.io/badge/docs-Deutsch-darkgreen)](docs/README.de.md)

## Введение

MTGA — это решение для фиксации провайдера моделей в IDE на основе локального прокси, для Windows и macOS.

**Внимание: начиная с `v2.6.0` MTGA на нижестоящем уровне единообразно предоставляет OpenAI Chat Completions API; бэкенд через встроенный в проект слой исполнения MLiteLLM пересылает запросы в апстримы `openai_chat_completion`, `openai_response`, Anthropic, Gemini и т.д., без установки сторонних фреймворков пересылки. Тип апстрима явно задаётся полем «Провайдер» в группе конфигурации; для `openai_response` MTGA выполняет преобразование между chat-completions и responses на уровне прокси. Ограничения см. в [docs/provider-support.md](docs/provider-support.md).**

 <details>
  <summary>Ты ничего не видишь~~</summary>
  <br>
  <p>MTGA расшифровывается как Make Trae Great Again!</p>
 </details>

## Содержание

- [MTGA](#mtga)
  - [Введение](#введение)
  - [Содержание](#содержание)
  - [Журнал изменений](#журнал-изменений)
  - [Быстрый старт](#быстрый-старт)
    - [Установка](#установка)
      - [Windows](#windows)
      - [macOS](#macos)
    - [Использование](#использование)
  - [macOS: решение проблемы «пакет повреждён»](#macos-решение-проблемы-пакет-повреждён)
    - [Графическое решение](#графическое-решение)
    - [Решение через cli](#решение-через-cli)
  - [Диагностика ошибки «не удалось добавить модель» в Trae](#диагностика-ошибки-не-удалось-добавить-модель-в-trae)
  - [Настройка Trae IDE](#настройка-trae-ide)
  - [😎 Будьте в курсе обновлений](#-будьте-в-курсе-обновлений)
  - [Вклад](#вклад)
  - [Архитектура и ограничения зависимостей](#архитектура-и-ограничения-зависимостей)
  - [Дружественные ссылки](#дружественные-ссылки)
  - [Благодарности](#благодарности)
  - [Star History](#star-history)

---

## Журнал изменений

Свежий журнал см.: [последний релиз](https://github.com/BiFangKNT/mtga/releases/latest)

Архив истории: [CHANGELOG.md](CHANGELOG.md)

---

## Быстрый старт

### Установка

#### Windows

1. Скачайте последнюю версию `MTGA_v{version}_windows_x64-setup.exe` со страницы [GitHub Releases](https://github.com/BiFangKNT/mtga/releases)
2. Запустите установку двойным щелчком

#### macOS

1. Скачайте последнюю версию `MTGA_v{version}_apple_{arch}.dmg` со страницы [GitHub Releases](https://github.com/BiFangKNT/mtga/releases)
   - `{arch}` — архитектура процессора:
     - `x64`: процессоры Intel
     - `aarch64`: процессоры Apple Silicon (серия M)
2. Откройте DMG-файл двойным щелчком — система автоматически смонтирует установочный образ
3. Перетащите `MTGA_GUI.app` в папку `Applications`

### Использование

1. Запустите приложение MTGA
2. Добавьте группу конфигурации прокси
   - **В API URL указывайте только домен (порт опционален; если не уверены — не указывайте), без маршрута в конце, например: `https://your-api.example.com`**
   - Если ваш интерфейс использует нестандартный маршрут `/v1`, можно задать собственный промежуточный маршрут
     <img width="70%" alt="modify middle route" src="./images/modify-middle-route.png?raw=true" />
3. Заполните глобальную конфигурацию
   - **Чтобы включить мультимодальные возможности, можно сопоставить имя модели с одним из встроенных мультимодальных имён:**
     - <div style="display:flex;flex-direction:column;font-size:0">
        <img width="70%" alt="model mapping" src="./images/model-mapping-above.png?raw=true" />
        <img width="70%" alt="model mapping" src="./images/model-mapping-below.png?raw=true" />
       </div>
     - <img width="70%" alt="model mapping effects" src="./images/model-mapping-effects.png?raw=true" />
4. Нажмите кнопку «Запустить все сервисы одним щелчком» (на macOS нужны права администратора)
5. Дождитесь, пока программа автоматически выполнит следующие действия:
   - Создание и установка сертификата
   - Изменение файла hosts
   - Запуск прокси-сервера
6. После завершения настройте IDE согласно разделу [Настройка Trae IDE](#настройка-trae-ide)

> [!NOTE]
>
> - Конфигурация прокси и сгенерированные сертификаты сохраняются в каталоге пользовательских данных, см. `Настройки - Пользовательские данные`

> [!WARNING]
>
> - Требуются права администратора
> - Если на macOS появляется сообщение «пакет повреждён», см. [macOS: решение проблемы «пакет повреждён»](#macos-решение-проблемы-пакет-повреждён)
> - Если в Trae не удаётся добавить модель, см. [Диагностика ошибки «не удалось добавить модель» в Trae](#диагностика-ошибки-не-удалось-добавить-модель-в-trae)

## macOS: решение проблемы «пакет повреждён»

Если при запуске `MTGA_GUI.app` появляется такое сообщение:

<img width="244" height="223" alt="app corrupted" src="./images/app-corrupted.png?raw=true" />

**Нажмите «Отмена»**, затем выполните следующие шаги:

### Графическое решение

1. Скачайте `Sentinel.dmg` со страницы [Sentinel Releases](https://github.com/alienator88/Sentinel/releases/latest)
2. Откройте `Sentinel.dmg` двойным щелчком и перетащите `Sentinel.app` в папку `Applications`
3. Запустите `Sentinel.app` из Launchpad или папки Applications
4. Перетащите `MTGA_GUI.app` этого проекта в левое окно `Sentinel.app`
   - <img width="355.33" height="373.33" alt="sentinel add app" src="./images/sentinel-add-app.png?raw=true" />

`MTGA_GUI.app` будет автоматически обработан и запущен

### Решение через cli

1. Найдите полный путь к `MTGA_GUI.app`, например `/Applications/MTGA_GUI.app`.
2. Откройте приложение «Терминал» (Terminal).
3. Выполните следующую команду для подписи `MTGA_GUI.app`:
   ```zsh
   xattr -d com.apple.quarantine <полный путь к приложению>
   ```
   Это удалит расширенный атрибут `com.apple.quarantine` у `MTGA_GUI.app`.
4. Запустите `MTGA_GUI.app`.

## Диагностика ошибки «не удалось добавить модель» в Trae

Если всё в порядке, в области логов вы увидите записи о получении запроса:

<img width="40%" alt="received list request" src="./images/received-list-request.png?raw=true" />

Если логов нет, проверьте:

- **hosts**: убедитесь, что присутствует строка `127.0.0.1 api.openai.com` и она не закомментирована (не начинается с #).
- **Прослушивание порта**: убедитесь, что порт 443 не занят другой программой (браузер, VPN и т.д.).
  - Проверить можно следующими командами:

    ```
    # windows
    netstat -ano | find ":443" | find "LISTENING"

    # macos
    netstat -lnp tcp | grep :443
    ```

  - Если какой-то процесс слушает порт 443, рекомендуется завершить его.

- **Сетевой прокси**: убедитесь, что не запущено другое прокси-ПО — оно может мешать работе прокси MTGA.
  - Если вам нужен обход блокировок, используйте режим TUN вместо системного прокси. По возможности разверните прокси-сервис **вне локальной машины**.
  - Неправильная конфигурация DNS также может приводить к сбоям разрешения имён.
  - Если не уверены — держите сетевое окружение «чистым».
- **Проблемы с сертификатом**: если Trae сообщает об ошибках SSL/TLS, проверьте, что CA-сертификат корректно установлен в «Доверенные корневые центры сертификации».
- **Брандмауэр**: убедитесь, что брандмауэр разрешает входящие соединения на порт 443 (хотя это локальное соединение `127.0.0.1` и обычно особая настройка не нужна, проверить стоит).
- **Продвинутая диагностика**:
  - Настройте MTGA: `Основной поток - Операции прокси-сервера - отметьте «Отключить строгий режим SSL»` и запустите все сервисы.
  - Установите и откройте инструмент [Reqable](https://reqable.com/), установите его сертификат по подсказкам.
  - При запуске по умолчанию включается отладка — отключите её в правом верхнем углу:
    <img width="40%" alt="reqable debug mode off" src="./images/reqable-debug-mode-off.png?raw=true" />
  - Откройте тестовую страницу http:
    <img width="55%" alt="reqable http create" src="./images/reqable-http-create.png?raw=true" />
  - Укажите url list api, в авторизации выберите «Bearer Token» и введите Key из глобальной конфигурации MTGA:
    <img width="70%" alt="reqable fill in config" src="./images/reqable-fill-in-config.png?raw=true" />
  - Нажмите «Отправить» и изучите тело ответа.

---

## Настройка Trae IDE

1.  Откройте Trae IDE и войдите в учётную запись.
2.  В окне AI-диалога нажмите значок модели в правом нижнем углу и выберите в конце списка «Добавить модель».
3.  **Провайдер**: выберите `OpenAI`.
4.  **Модель**: согласно ID модели из глобальной конфигурации; если это `gpt-5`, выберите `GPT-5`.
5.  **API-ключ**: Key из глобальной конфигурации.
6.  Нажмите «Добавить модель».
7.  Вернитесь в окно AI-чата и в правом нижнем углу выберите только что добавленную пользовательскую модель.

Теперь при взаимодействии с этой пользовательской моделью через Trae запросы будут проходить через ваш локальный прокси MTGA и пересылаться на настроенный `API URL`.

---

## 😎 Будьте в курсе обновлений

Нажмите кнопки Star и Watch в правом верхнем углу репозитория, чтобы получать новости.

![star to keep latest](https://github.com/BiFangKNT/mtga/blob/gui/images/star-to-keep-latest.gif?raw=true)

---

## Вклад

См. [руководство для контрибьюторов](CONTRIBUTING.md)

## Архитектура и ограничения зависимостей

Чтобы избежать неконтролируемой связанности модулей, проект следует следующим правилам слоёв и зависимостей:

- UI -> actions -> services -> доменные модули (cert/hosts/network/proxy/update) -> runtime/platform
- UI не должен напрямую зависеть от доменных модулей; все операции оркестрируются через actions/services.
- Платформенно-зависимая логика размещается в `modules/platform`.
- Вызовы мульти-провайдерных апстримов обеспечивает `python-src/modules/mlitellm` — встроенный в проект облегчённый слой исполнения, не устанавливаемый как отдельная сторонняя зависимость.

## Дружественные ссылки

[![linux.do](https://img.shields.io/badge/LINUX--DO-Community-blue.svg?logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTIwIiBoZWlnaHQ9IjEyMCIgdmlld0JveD0iMCAwIDEyMCAxMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI%2BPGNsaXBQYXRoIGlkPSJhIj48Y2lyY2xlIGN4PSI2MCIgY3k9IjYwIiByPSI0NyIvPjwvY2xpcFBhdGg%2BPGNpcmNsZSBmaWxsPSIjZjBmMGYwIiBjeD0iNjAiIGN5PSI2MCIgcj0iNTAiLz48cmVjdCBmaWxsPSIjMWMxYzFlIiBjbGlwLXBhdGg9InVybCgjYSkiIHg9IjEwIiB5PSIxMCIgd2lkdGg9IjEwMCIgaGVpZ2h0PSIzMCIvPjxyZWN0IGZpbGw9IiNmMGYwZjAiIGNsaXAtcGF0aD0idXJsKCNhKSIgeD0iMTAiIHk9IjQwIiB3aWR0aD0iMTAwIiBoZWlnaHQ9IjQwIi8%2BPHJlY3QgZmlsbD0iI2ZmYjAwMyIgY2xpcC1wYXRoPSJ1cmwoI2EpIiB4PSIxMCIgeT0iODAiIHdpZHRoPSIxMDAiIGhlaWdodD0iMzAiLz48L3N2Zz4%3D&style=flat)](https://linux.do/)

## Благодарности

Каталог `ca` заимствован из репозитория `wkgcass/vproxy` — спасибо автору!

## Star History

<a href="https://www.star-history.com/#BiFangKNT/mtga&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=BiFangKNT/mtga&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=BiFangKNT/mtga&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=BiFangKNT/mtga&type=date&legend=top-left" />
 </picture>
</a>
