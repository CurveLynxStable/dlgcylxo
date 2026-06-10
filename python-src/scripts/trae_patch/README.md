# Trae Native Route Scripts

Здесь сохранены только инструменты повторной проверки пути, отработанного до интеграции маршрута Trae native custom model в основной поток, а также несколько ценных вспомогательных утилит.

## Проверка и сопровождение

- `trae_native_custom_model_session.py`: скрипт реальной сессии с апстримом, окончательно отработанный перед интеграцией в основной поток.
- `trae_macos_offline_patch_session.py`: исследовательский скрипт macOS: офлайн patch/clone/codesign/launch/CDP smoke.
  - Рекомендуется указывать фиксированный путь копии в `--clone-app` и при повторных проверках переиспользовать её через `--reuse-clone`, чтобы не копировать/пересоздавать временную идентичность app каждый раз.
- `trae_macos_native_symbol_report.py`: экспортирует ключевые native-символы macOS `libai_agent.dylib`, дизассемблирование, гипотезы смещений структур, кандидатные точки patch, доступные пустоты `__TEXT,__text` и рекомендованную стратегию офлайн patch первой версии — для проектирования recipe.
- `trae_macos_url_patch_recipe.py`: на основе рекомендованных primary site/cave из `trae_macos_native_symbol_report.py` генерирует офлайн patch recipe, который напрямую потребляется `trae_macos_offline_patch_session.py`.
  - Если `modules/trae_patch/macos/url_patch_manifest.json` совпадает по sha256 с текущим `libai_agent.dylib`, приоритетно переиспользуются уже проверенные site/cave без повторного вывода через symbol report.
  - Текущий primary site по умолчанию — `default_handler_final_request_url_load @ 0x1204b3c`; он находится перед `DefaultSseProxyHandler -> reqwest::Client::request` и напрямую переписывает пару URL `x3/x4`.
  - `http_request_url_to_builder @ 0x5dbd48` сохранён как вспомогательный сайт пути NetBridge adapter, но больше не считается единственным входом, покрывающим все custom-model запросы апстрима.
- `trae_local_model_loopback.py`: локальный loopback, переиспользуемый автономными сессионными скриптами.
- `trae_native_byte_pattern.py`: проверяет локализацию байтового шаблона URL copy call — удобно для перепроверки после обновления версии Trae.
- `trae_ai_agent_latest_verdict.py`: определяет результат последнего chat по логам Trae.

## Вспомогательные утилиты

- `trae_cdp_targets.py`: перечисляет CDP targets Trae, подтверждая возможность присоединения к странице.
- `trae_cdp_send_chat.py`: отправляет тестовое сообщение в chat UI Trae через CDP. Сохранён только как триггер-инструмент, не участвует в основном потоке native rewriter.
- `trae_cdp_dom_probe.py`: экспортирует видимые кнопки, textbox и DOM, связанный с `icube/chat/agent/panel`, текущего workbench — удобно для калибровки CDP selector.

`python-src/artifacts/` и корневой `artifacts/` — временные диагностические выгрузки; их не нужно коммитить и можно удалять в любой момент.
