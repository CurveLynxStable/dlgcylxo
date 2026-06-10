# Автонастройка MTGA: прописывает FreeQwenApi (Qwen) как цель апстрима
# Запуск: E:\AI\mtga\scripts\windows\configure-mtga.ps1

$configDir  = Join-Path $env:APPDATA "MTGA"
$configFile = Join-Path $configDir "mtga_config.yaml"

# Закрываем MTGA, чтобы он не перезаписал конфиг
Get-Process | Where-Object { $_.ProcessName -match "^mtga" } | Stop-Process -Force -ErrorAction SilentlyContinue

New-Item -ItemType Directory -Force -Path $configDir | Out-Null
if (Test-Path $configFile) {
    Copy-Item $configFile "$configFile.bak" -Force
    Write-Host "Старый конфиг сохранён: $configFile.bak" -ForegroundColor Yellow
}

# Список публикуемых моделей Qwen (полный список: http://localhost:3264/api/models)
$qwenModels = @(
    "qwen3.7-max",
    "qwen3.7-plus",
    "qwen3.6-plus",
    "qwen3.5-plus",
    "qwen3.5-flash",
    "qwen3-max",
    "qwen3-coder-plus",
    "qwen3-vl-plus",
    "qwq-32b"
)

# Список публикуемых моделей DeepSeek (полный список: http://localhost:9655/v1/models)
$deepseekModels = @(
    "deepseek-chat",
    "deepseek-reasoner",
    "deepseek-r1",
    "deepseek-chat-search",
    "deepseek-reasoner-search",
    "deepseek-expert",
    "deepseek-v4-pro"
)

$qwenUpstream      = ($qwenModels | ForEach-Object { "  - $_" }) -join "`n"
$deepseekUpstream  = ($deepseekModels | ForEach-Object { "  - $_" }) -join "`n"
$publishedList = (
    ($qwenModels | ForEach-Object {
        "- name: $_`n  enabled: true`n  primary_target_id: freeqwenapi`n  primary_upstream_model: $_"
    }) +
    ($deepseekModels | ForEach-Object {
        "- name: $_`n  enabled: true`n  primary_target_id: freedeepseekapi`n  primary_upstream_model: $_"
    })
) -join "`n"

$yaml = @"
schema_version: 3
mtga_auth_key: ''
targets:
- id: freeqwenapi
  display_name: FreeQwenApi (Qwen)
  provider: openai_chat_completion
  api_base: http://127.0.0.1:3264/api
  upstream_models:
$qwenUpstream
  upstream_model: $($qwenModels[0])
  api_key: sk-local
  middle_route: /v1
- id: freedeepseekapi
  display_name: FreeDeepseekAPI (DeepSeek)
  provider: openai_chat_completion
  api_base: http://127.0.0.1:9655
  upstream_models:
$deepseekUpstream
  upstream_model: $($deepseekModels[0])
  api_key: sk-local
  middle_route: /v1
failover_pools: []
published_models:
$publishedList
"@

[System.IO.File]::WriteAllText($configFile, $yaml, (New-Object System.Text.UTF8Encoding $false))
Write-Host "Конфигурация MTGA записана: $configFile" -ForegroundColor Green

# Запускаем MTGA заново
$mtga = $null
foreach ($dir in @("E:\AI\MTGA", "$env:LOCALAPPDATA\Programs")) {
    if (Test-Path $dir) {
        $mtga = Get-ChildItem $dir -Recurse -Filter "*.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match "^(MTGA|mtga)" -and $_.Name -notmatch "setup|uninstall" } |
            Select-Object -First 1
        if ($mtga) { break }
    }
}
if ($mtga) {
    Start-Process $mtga.FullName
    Write-Host "MTGA запущен. Откройте вкладку «Прокси» и нажмите «Запустить прокси»." -ForegroundColor Green
} else {
    Write-Host "MTGA не найден — запустите его вручную." -ForegroundColor Yellow
}
