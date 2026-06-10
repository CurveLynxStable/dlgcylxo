@echo off
rem Zapusk FreeDeepseekAPI (DeepSeek dlya Trae cherez MTGA)
cd /d E:\AI\FreeDeepseekAPI
if not exist deepseek-auth.json (
    echo deepseek-auth.json ne najden - zapusk avtorizacii (vojdite v chat.deepseek.com)...
    call npm run auth -- --login
)
call npm start
pause
