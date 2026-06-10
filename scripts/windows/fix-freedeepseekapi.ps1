# Патч FreeDeepseekAPI: разворачивает массивы content (Trae Agent) в текст,
# чтобы вместо "[object Object]" модель получала реальное сообщение.
$serverJs = "E:\AI\FreeDeepseekAPI\server.js"
if (-not (Test-Path $serverJs)) {
    Write-Host "Не найден $serverJs — проверьте путь установки FreeDeepseekAPI." -ForegroundColor Red
    exit 1
}
$src = [System.IO.File]::ReadAllText($serverJs)
$patchLine = "    messages = messages.map(m => (m && m.content !== null && m.content !== undefined && typeof m.content !== 'string') ? { ...m, content: normalizeMessageContent(m.content) } : m);"
if ($src.Contains($patchLine)) {
    Write-Host "Патч уже применён — ничего делать не нужно." -ForegroundColor Green
    exit 0
}
$anchor = "function formatMessages(messages, tools) {"
if (-not $src.Contains($anchor)) {
    Write-Host "Не найдена функция formatMessages — версия FreeDeepseekAPI отличается, патч не применён." -ForegroundColor Red
    exit 1
}
Copy-Item $serverJs "$serverJs.bak" -Force
$src = $src.Replace($anchor, $anchor + "`n" + $patchLine)
[System.IO.File]::WriteAllText($serverJs, $src, (New-Object System.Text.UTF8Encoding $false))
Write-Host "Патч применён (резервная копия: server.js.bak)." -ForegroundColor Green
Write-Host "Перезапустите FreeDeepseekAPI: закройте его окно и запустите start-deepseek.bat" -ForegroundColor Cyan
