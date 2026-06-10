# Быстрый запуск: FreeQwenApi + FreeDeepseekAPI + MTGA + Trae
# Запуск: E:\AI\mtga\scripts\windows\start-qwen-trae.ps1

$FqaDir  = "E:\AI\FreeQwenApi"
$FdsDir  = "E:\AI\FreeDeepseekAPI"
$TraeExe = "$env:LOCALAPPDATA\Programs\Trae\Trae.exe"

# 1. FreeQwenApi в отдельном окне (если ещё не запущен)
$fqaRunning = $false
try {
    Invoke-RestMethod "http://localhost:3264/api/health" -TimeoutSec 2 | Out-Null
    $fqaRunning = $true
    Write-Host "FreeQwenApi уже запущен." -ForegroundColor Green
} catch {}
if (-not $fqaRunning) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command",
        "cd '$FqaDir'; `$env:SKIP_ACCOUNT_MENU='1'; npm start"
}

# 2. Ждём готовности API
Write-Host "Ожидание FreeQwenApi (http://localhost:3264/api/health)..." -ForegroundColor Cyan
for ($i = 0; $i -lt 60; $i++) {
    try {
        $r = Invoke-RestMethod "http://localhost:3264/api/health" -TimeoutSec 2
        Write-Host "FreeQwenApi запущен." -ForegroundColor Green
        break
    } catch { Start-Sleep -Seconds 2 }
}

# 3. FreeDeepseekAPI в отдельном окне (если установлен и ещё не запущен)
if (Test-Path $FdsDir) {
    $fdsRunning = $false
    try {
        Invoke-RestMethod "http://localhost:9655/health" -TimeoutSec 2 | Out-Null
        $fdsRunning = $true
        Write-Host "FreeDeepseekAPI уже запущен." -ForegroundColor Green
    } catch {}
    if (-not $fdsRunning) {
        if (Test-Path (Join-Path $FdsDir "deepseek-auth.json")) {
            Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FdsDir'; npm start"
            Write-Host "FreeDeepseekAPI запускается (http://localhost:9655)..." -ForegroundColor Cyan
        } else {
            Write-Host "FreeDeepseekAPI: нет deepseek-auth.json — выполните в $FdsDir команду: npm run auth" -ForegroundColor Yellow
        }
    }
}

# 4. MTGA (если установлен)
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
    Write-Host "MTGA запущен. Включите прокси на вкладке «Прокси»." -ForegroundColor Green
} else {
    Write-Host "MTGA не найден — установите его из E:\AI\mtga\src-tauri\target\bundle-release\bundle\ и запустите вручную." -ForegroundColor Yellow
}

# 5. Trae
if (Test-Path $TraeExe) {
    Write-Host "После запуска прокси в MTGA запустите/перезапустите Trae." -ForegroundColor Cyan
    Read-Host "Нажмите Enter, чтобы запустить Trae"
    Start-Process $TraeExe
} else {
    Write-Host "Trae не найден по пути $TraeExe — запустите его вручную." -ForegroundColor Yellow
}
