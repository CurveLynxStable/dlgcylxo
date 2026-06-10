@echo off
rem Zapusk FreeDeepseekAPI - DeepSeek dlya Trae cherez MTGA
cd /d E:\AI\FreeDeepseekAPI
if not exist deepseek-auth.json echo Net deepseek-auth.json - sejchas otkroetsya avtorizaciya, vojdite v chat.deepseek.com
if not exist deepseek-auth.json call npm run auth -- --login
call npm start
pause
