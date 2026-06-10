# Патч FreeQwenApi: запрещает модели вызывать несуществующие инструменты
# (LS, Glob, Read и т.п. из Claude Code) в режиме Agent Trae.
$routesJs = "E:\AI\FreeQwenApi\src\api\routes.js"
if (-not (Test-Path $routesJs)) {
    Write-Host "Не найден $routesJs — проверьте путь установки FreeQwenApi." -ForegroundColor Red
    exit 1
}
$src = [System.IO.File]::ReadAllText($routesJs)
$patchLine = "- CRITICAL: ONLY the tool names listed above exist. Tools from other agents (LS, Glob, Grep, Read, Write, Edit, Bash, RunCommand, TodoWrite, Task, Skill, WebFetch) do NOT exist here unless they appear in the list above. Calling an unlisted tool name ALWAYS fails with `"Tool does not exists`". Before every tool call, verify the name is in the list above; if you need a capability, pick the closest tool FROM THE LIST."
if ($src.Contains("CRITICAL: ONLY the tool names listed above exist")) {
    Write-Host "Патч уже применён — ничего делать не нужно." -ForegroundColor Green
    exit 0
}
$anchor = "- Use exact tool names from the list above. Do not prefix names with namespaces."
if (-not $src.Contains($anchor)) {
    Write-Host "Не найдена строка-якорь — версия FreeQwenApi отличается, патч не применён." -ForegroundColor Red
    exit 1
}
Copy-Item $routesJs "$routesJs.bak" -Force
$src = $src.Replace($anchor, $anchor + "`n" + $patchLine)
[System.IO.File]::WriteAllText($routesJs, $src, (New-Object System.Text.UTF8Encoding $false))
Write-Host "Патч применён (резервная копия: routes.js.bak)." -ForegroundColor Green
Write-Host "Перезапустите FreeQwenApi: закройте его окно и запустите start-qwen.bat" -ForegroundColor Cyan
