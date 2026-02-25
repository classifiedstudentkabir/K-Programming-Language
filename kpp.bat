@echo off
chcp 65001 >nul

title K++ Programming Language

set "KPP_DIR=%~dp0"

if "%~1"=="" (
echo Usage: kpp.bat yourprogram.kpp
pause
exit /b
)

python "%KPP_DIR%kpp\main.py" "%~1"

echo.
echo K++ Program Finished
pause
