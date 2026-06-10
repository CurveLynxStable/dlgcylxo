@echo off
rem Obnovlenie sessii DeepSeek - pri sletevshej avtorizacii ili oshibkah dostupa
cd /d E:\AI\FreeDeepseekAPI
echo Sejchas otkroetsya brauzer - vojdite v chat.deepseek.com.
echo Posle uspeshnogo vhoda okno zakroetsya samo. Zatem zapustite start-deepseek.bat
call npm run auth -- --login
echo Gotovo. Teper zapustite start-deepseek.bat
pause
