# Установка связки MTGA + FreeQwenApi для Trae (Windows)
# Запуск: PowerShell от имени администратора:
#   Set-ExecutionPolicy -Scope Process Bypass -Force
#   E:\AI\mtga\scripts\windows\setup-e-ai.ps1

$ErrorActionPreference = "Stop"
$AiRoot = "E:\AI"
$MtgaDir = Join-Path $AiRoot "mtga"
$FqaDir  = Join-Path $AiRoot "FreeQwenApi"

Write-Host "=== 1/5: Установка инструментов (winget) ===" -ForegroundColor Cyan
winget install --id OpenJS.NodeJS --version 24.16.0 -e --accept-package-agreements --accept-source-agreements
winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements
winget install --id Rustlang.Rustup -e --accept-package-agreements --accept-source-agreements
winget install --id astral-sh.uv -e --accept-package-agreements --accept-source-agreements
winget install --id Microsoft.VisualStudio.2022.BuildTools -e --accept-package-agreements --accept-source-agreements --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"

# Обновляем PATH в текущей сессии
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")

Write-Host "=== 2/5: pnpm 10.32.1 ===" -ForegroundColor Cyan
npm install -g pnpm@10.32.1

Write-Host "=== 3/5: Клонирование MTGA (русская версия) ===" -ForegroundColor Cyan
if (-not (Test-Path $MtgaDir)) {
    git clone --branch mtga-ru https://github.com/CurveLynxStable/dlgcylxo.git $MtgaDir
}

Write-Host "=== 4/5: Сборка MTGA ===" -ForegroundColor Cyan
Set-Location $MtgaDir
pnpm i
Set-Location (Join-Path $MtgaDir "python-src")
uv sync --project .
Set-Location $MtgaDir
pnpm pytauri:install:win
pnpm tauri:bundle:win -- --profile bundle-release
Write-Host "Установщик MTGA: $MtgaDir\src-tauri\target\bundle-release\bundle\" -ForegroundColor Green

Write-Host "=== 5/5: FreeQwenApi ===" -ForegroundColor Cyan
Set-Location $FqaDir
npm install
Write-Host "Сейчас откроется Chromium — войдите в свой аккаунт Qwen Chat (chat.qwen.ai)" -ForegroundColor Yellow
npm run auth
npm run models:sync

Write-Host ""
Write-Host "Готово! Установите MTGA из папки bundle и запускайте: E:\AI\mtga\scripts\windows\start-qwen-trae.ps1" -ForegroundColor Green
