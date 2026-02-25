@echo off
:: ============================================================
::  build_exe.bat — Package K++ into a standalone Windows .exe
::
::  REQUIREMENTS
::  ────────────
::  pip install pyinstaller
::
::  USAGE
::  ─────
::  1. Open a Command Prompt in the folder containing kpp\
::  2. Run:  build_exe.bat
::  3. Find kpp.exe in the dist\ folder
::
::  AFTER BUILDING
::  ──────────────
::  To associate .kpp files with the standalone exe (run as Admin):
::    assoc .kpp=KppScript
::    ftype KppScript="C:\path\to\dist\kpp.exe" "%1"
:: ============================================================

title Building K++ Standalone Executable

echo.
echo  Building K++ standalone executable with PyInstaller...
echo.

:: PyInstaller bundles all Python files into a single .exe
pyinstaller --onefile --icon=kpp.ico kpp_launcher.py

if %ERRORLEVEL%==0 (
    echo.
    echo  ╔═══════════════════════════════════════════════════════════╗
    echo  ║  Build SUCCESS!                                            ║
    echo  ║  Executable: dist\kpp.exe                                 ║
    echo  ║                                                            ║
    echo  ║  To register file association (run as Administrator):     ║
    echo  ║    assoc .kpp=KppScript                                   ║
    echo  ║    ftype KppScript="dist\kpp.exe" "%%1"                  ║
    echo  ╚═══════════════════════════════════════════════════════════╝
) else (
    echo.
    echo  Build FAILED. Check errors above.
    echo  Ensure PyInstaller is installed:  pip install pyinstaller
)

echo.
pause
