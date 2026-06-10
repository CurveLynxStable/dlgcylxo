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

$yaml = @"
schema_version: 3
mtga_auth_key: ''
targets:
- id: freeqwenapi
  display_name: FreeQwenApi (Qwen)
  provider: openai_chat_completion
  api_base: http://127.0.0.1:3264/api
  upstream_models:
  - qwen3.7-max
  upstream_model: qwen3.7-max
  api_key: sk-local
  middle_route: /v1
failover_pools: []
published_models:
- name: qwen3.7-max
  enabled: true
  primary_target_id: freeqwenapi
  primary_upstream_model: qwen3.7-max
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
