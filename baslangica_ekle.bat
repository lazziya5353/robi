@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath(Startup)+\Robi.lnk); $s.TargetPath=(Get-Command pythonw).Source; $s.Arguments=\"%~dp0app.py\"; $s.WorkingDirectory=%~dp0; $s.Save()"
echo Robi artik Windows acilinca otomatik baslayacak.
pause
