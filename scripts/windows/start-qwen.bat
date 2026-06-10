@echo off
rem Zapusk FreeQwenApi (Qwen dlya Trae cherez MTGA)
cd /d E:\AI\FreeQwenApi
if not exist session\accounts (
    echo Akkaunt Qwen ne najden - zapusk avtorizacii: vojdite v chat.qwen.ai
    call npm run auth
)
set SKIP_ACCOUNT_MENU=1
call npm start
pause
