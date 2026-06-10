# Быстрый запуск: FreeQwenApi + MTGA + Trae
# Запуск: E:\AI\mtga\scripts\windows\start-qwen-trae.ps1

$FqaDir  = "E:\AI\FreeQwenApi"
$TraeExe = "$env:LOCALAPPDATA\Programs\Trae\Trae.exe"

# 1. FreeQwenApi в отдельном окне
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$FqaDir'; `$env:SKIP_ACCOUNT_MENU='1'; npm start"

# 2. Ждём готовности API
Write-Host "Ожидание FreeQwenApi (http://localhost:3264/api/health)..." -ForegroundColor Cyan
for ($i = 0; $i -lt 60; $i++) {
    try {
        $r = Invoke-RestMethod "http://localhost:3264/api/health" -TimeoutSec 2
        Write-Host "FreeQwenApi запущен." -ForegroundColor Green
        break
    } catch { Start-Sleep -Seconds 2 }
}

# 3. MTGA (если установлен)
$mtga = Get-ChildItem "$env:LOCALAPPDATA\Programs" -Recurse -Filter "MTGA*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($mtga) {
    Start-Process $mtga.FullName
    Write-Host "MTGA запущен. Включите прокси на вкладке «Прокси»." -ForegroundColor Green
} else {
    Write-Host "MTGA не найден — установите его из E:\AI\mtga\src-tauri\target\bundle-release\bundle\ и запустите вручную." -ForegroundColor Yellow
}

# 4. Trae
if (Test-Path $TraeExe) {
    Write-Host "После запуска прокси в MTGA запустите/перезапустите Trae." -ForegroundColor Cyan
    Read-Host "Нажмите Enter, чтобы запустить Trae"
    Start-Process $TraeExe
} else {
    Write-Host "Trae не найден по пути $TraeExe — запустите его вручную." -ForegroundColor Yellow
}
