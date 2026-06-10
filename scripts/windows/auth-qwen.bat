@echo off
rem Obnovlenie sessii Qwen - pri oshibke "anti-bot challenge" ili sletevshej avtorizacii
cd /d E:\AI\FreeQwenApi
echo Sejchas otkroetsya brauzer - vojdite v chat.qwen.ai i reshite kapchu esli pokazhut.
echo Posle uspeshnogo vhoda okno zakroetsya samo. Zatem zapustite start-qwen.bat
call npm run auth
echo Gotovo. Teper zapustite start-qwen.bat
pause
