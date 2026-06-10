@echo off
rem Zapusk FreeQwenApi - Qwen dlya Trae cherez MTGA
cd /d E:\AI\FreeQwenApi
if not exist session\accounts echo Net akkaunta Qwen - sejchas otkroetsya avtorizaciya, vojdite v chat.qwen.ai
if not exist session\accounts call npm run auth
set SKIP_ACCOUNT_MENU=1
call npm start
pause
