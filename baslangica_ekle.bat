@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -c "import kimlik; kimlik.add_to_startup()"
echo Robi artik Windows acilinca otomatik baslayacak.
pause
