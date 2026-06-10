# Установка связки MTGA + FreeQwenApi для Trae (Windows)
# Запуск: PowerShell от имени администратора:
#   Set-ExecutionPolicy -Scope Process Bypass -Force
#   E:\AI\mtga\scripts\windows\setup-e-ai.ps1

$ErrorActionPreference = "Stop"
$AiRoot = "E:\AI"
$MtgaDir = Join-Path $AiRoot "mtga"
$FqaDir  = Join-Path $AiRoot "FreeQwenApi"

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User") + ";" +
                "$env:APPDATA\npm" + ";" +
                "$env:USERPROFILE\.cargo\bin"
}

Write-Host "=== 1/5: Установка инструментов (winget) ===" -ForegroundColor Cyan
$nodeOk = $false
if (Get-Command node -ErrorAction SilentlyContinue) {
    $nodeOk = (node -v) -match '^v24\.'
}
if (-not $nodeOk) {
    winget install --id OpenJS.NodeJS.LTS -e --accept-package-agreements --accept-source-agreements
}
winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements
winget install --id Rustlang.Rustup -e --accept-package-agreements --accept-source-agreements
winget install --id astral-sh.uv -e --accept-package-agreements --accept-source-agreements
winget install --id Microsoft.VisualStudio.2022.BuildTools -e --accept-package-agreements --accept-source-agreements --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"

Refresh-Path
node -v
if (-not ((node -v) -match '^v24\.')) {
    Write-Host "ВНИМАНИЕ: требуется Node 24.x, у вас $(node -v). Удалите старый Node и запустите скрипт снова." -ForegroundColor Yellow
}
$cargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
if (Test-Path $cargoBin) { $env:Path += ";$cargoBin" }
if (-not (Get-Command rustup -ErrorAction SilentlyContinue)) {
    Write-Host "Скачивание rustup-init..." -ForegroundColor Cyan
    $rustupInit = Join-Path $env:TEMP "rustup-init.exe"
    Invoke-WebRequest -Uri "https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe" -OutFile $rustupInit
    & $rustupInit -y --default-toolchain stable
    $env:Path += ";$cargoBin"
}
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    rustup toolchain install stable
    rustup default stable
}
cargo --version

Write-Host "=== 2/5: pnpm 10.32.1 ===" -ForegroundColor Cyan
npm install -g pnpm@10.32.1
Refresh-Path
pnpm --version

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

# Скачиваем встраиваемый Python (pyembed), как в CI
$pyembedExe = Join-Path $MtgaDir "src-tauri\pyembed\python\python.exe"
if (-not (Test-Path $pyembedExe)) {
    Write-Host "Скачивание встраиваемого Python 3.13 (python-build-standalone)..." -ForegroundColor Cyan
    $pyembedDir = Join-Path $MtgaDir "src-tauri\pyembed"
    New-Item -ItemType Directory -Path $pyembedDir -Force | Out-Null
    $release = Invoke-RestMethod "https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"
    $asset = $release.assets | Where-Object { $_.name -match 'cpython-3\.13\..*\+.*-x86_64-pc-windows-msvc-install_only_stripped\.tar\.gz$' } | Select-Object -First 1
    if (-not $asset) { throw "Не найден подходящий архив Python 3.13 для Windows" }
    $archivePath = Join-Path $pyembedDir "python-standalone.tar.gz"
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $archivePath
    tar -xzf $archivePath -C $pyembedDir
    Remove-Item $archivePath
}

pnpm pytauri:install:win
pnpm pyembed:prune
pnpm tauri:bundle:win:ci
Write-Host "Установщик MTGA: $MtgaDir\src-tauri\target\bundle-release\bundle\" -ForegroundColor Green
$bundleDir = Join-Path $MtgaDir "src-tauri\target\bundle-release\bundle"
$installer = Get-ChildItem $bundleDir -Recurse -Filter "*.exe" -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "setup" } | Select-Object -First 1
if ($installer) {
    Write-Host "Тихая установка MTGA: $($installer.FullName)" -ForegroundColor Cyan
    Start-Process $installer.FullName -ArgumentList "/S" -Wait
    Write-Host "MTGA установлен." -ForegroundColor Green
} else {
    Write-Host "Установщик MTGA не найден в $bundleDir" -ForegroundColor Yellow
}

Write-Host "=== 5/5: FreeQwenApi ===" -ForegroundColor Cyan
Set-Location $FqaDir
npm install
if (-not (Test-Path (Join-Path $FqaDir "session\accounts"))) {
    Write-Host "Сейчас откроется Chromium — войдите в свой аккаунт Qwen Chat (chat.qwen.ai)" -ForegroundColor Yellow
    npm run auth
    npm run models:sync
} else {
    Write-Host "Аккаунт Qwen уже авторизован — пропускаем." -ForegroundColor Green
}

Write-Host ""
Write-Host "Готово! Установите MTGA из папки bundle и запускайте: E:\AI\mtga\scripts\windows\start-qwen-trae.ps1" -ForegroundColor Green
