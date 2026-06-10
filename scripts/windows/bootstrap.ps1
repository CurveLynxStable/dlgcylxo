# Полностью автоматическая установка MTGA + FreeQwenApi для Trae.
# Запуск одной командой в PowerShell от имени администратора:
#   irm https://raw.githubusercontent.com/CurveLynxStable/dlgcylxo/mtga-ru/scripts/windows/bootstrap.ps1 | iex

$ErrorActionPreference = "Stop"
$MtgaDir = "E:\AI\mtga"

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

Write-Host "=== Установка Git ===" -ForegroundColor Cyan
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements
    Refresh-Path
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    $gitCmd = Get-ChildItem "$env:ProgramFiles\Git\cmd\git.exe" -ErrorAction SilentlyContinue
    if ($gitCmd) { $env:Path += ";$env:ProgramFiles\Git\cmd" }
}

Write-Host "=== Клонирование репозитория (ветка mtga-ru) ===" -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $MtgaDir ".git"))) {
    git clone --branch mtga-ru https://github.com/CurveLynxStable/dlgcylxo.git $MtgaDir
} else {
    Set-Location $MtgaDir
    git fetch origin mtga-ru
    git checkout mtga-ru
    git pull origin mtga-ru
}

Write-Host "=== Запуск основного скрипта установки ===" -ForegroundColor Cyan
& (Join-Path $MtgaDir "scripts\windows\setup-e-ai.ps1")
