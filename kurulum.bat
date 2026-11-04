@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  === Robi kuruluyor ===
echo.
where python >nul 2>nul || (echo [!] Python bulunamadi. python.org adresinden kur, "Add to PATH" kutusunu isaretle. & pause & exit /b)
where ollama >nul 2>nul || (echo [!] Ollama bulunamadi. ollama.com adresinden indir, kur, sonra bunu tekrar calistir. & pause & exit /b)
echo [1/2] Python paketleri kuruluyor...
python -m pip install -r requirements.txt
echo.
echo [2/2] Yapay zeka modeli indiriliyor (bir kere, yaklasik 9 GB)...
ollama pull qwen2.5:14b
echo.
echo  Kurulum bitti! baslat.bat ile Robiyi acabilirsin.
pause
