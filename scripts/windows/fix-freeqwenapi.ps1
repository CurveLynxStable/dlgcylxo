# Патч FreeQwenApi v2 для Trae Agent:
# 1) запрещает модели вызывать несуществующие инструменты (LS, Glob, Read и т.п.);
# 2) автоматически заменяет выдуманные имена на ближайшие реальные инструменты Trae.
# Скачивает пропатченные файлы из репозитория и подменяет их (с резервными копиями .bak).
$apiDir = "E:\AI\FreeQwenApi\src\api"
if (-not (Test-Path "$apiDir\routes.js")) {
    Write-Host "Не найден $apiDir\routes.js — проверьте путь установки FreeQwenApi." -ForegroundColor Red
    exit 1
}
$base = "https://raw.githubusercontent.com/CurveLynxStable/dlgcylxo/mtga-ru/scripts/windows/patches/freeqwenapi"
foreach ($name in @("routes.js", "toolParser.js")) {
    $dest = Join-Path $apiDir $name
    Copy-Item $dest "$dest.bak" -Force
    Invoke-WebRequest "$base/$name" -OutFile $dest
    Write-Host "Обновлён $name (резервная копия: $name.bak)" -ForegroundColor Green
}
$check = [System.IO.File]::ReadAllText("$apiDir\toolParser.js")
if ($check.Contains("remapToolCallNames")) {
    Write-Host "Патч применён успешно." -ForegroundColor Green
    Write-Host "Перезапустите FreeQwenApi: закройте его окно и запустите start-qwen.bat" -ForegroundColor Cyan
} else {
    Write-Host "Похоже, скачалась старая версия (кеш GitHub). Подождите 2-3 минуты и запустите скрипт снова." -ForegroundColor Yellow
}
