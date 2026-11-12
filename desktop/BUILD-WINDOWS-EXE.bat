@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title MasterForge AI - Build Native Windows EXE

echo ================================================
echo      MASTERFORGE AI - Windows EXE Builder
echo ================================================
echo First build downloads Python packages and FFmpeg.
echo No GitHub, Electron or Node.js required.
echo.
where py >nul 2>nul
if not errorlevel 1 (
  set "PYCMD=py -3"
) else (
  set "PYCMD=python"
)
if not exist ".venv\Scripts\python.exe" (
  %PYCMD% -m venv .venv
  if errorlevel 1 goto :fail
)
".venv\Scripts\python.exe" -m pip install --upgrade pyinstaller imageio-ffmpeg
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto :fail

echo.
echo Packaging MasterForge as a Python package (engine included)...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name MasterForge-AI --icon "masterforge_python\assets\icon.ico" --add-data "masterforge_python\assets;masterforge_python\assets" --paths "%CD%" --hidden-import masterforge_python.engine --collect-all imageio_ffmpeg "run_masterforge.py"
if errorlevel 1 goto :fail
if not exist "dist\MasterForge-AI.exe" goto :fail

echo.
echo Testing the finished executable (not only the source code)...
set "SMOKE_REPORT=%CD%\dist\masterforge-build-check.txt"
if exist "%SMOKE_REPORT%" del /q "%SMOKE_REPORT%"
start "" /wait "%CD%\dist\MasterForge-AI.exe" --self-test "%SMOKE_REPORT%"
if errorlevel 1 goto :smokefail
if not exist "%SMOKE_REPORT%" goto :smokefail
findstr /B /C:"READY:" "%SMOKE_REPORT%" >nul
if errorlevel 1 goto :smokefail

type "%SMOKE_REPORT%"
echo.
echo [SUCCESS] Built and verified dist\MasterForge-AI.exe
echo This EXE can also be packaged using BUILD-WINDOWS-INSTALLER.bat.
echo Mastering runs fully locally; FFplay may be needed for A/B preview.
if /i not "%~1"=="--no-pause" pause
exit /b 0
:smokefail
echo.
echo [ERROR] The packaged EXE did not pass its engine and FFmpeg checks.
if exist "%SMOKE_REPORT%" type "%SMOKE_REPORT%"
echo Please report the message above so we can pinpoint the missing component.
goto :fail
:fail
echo.
echo [ERROR] The build failed; inspect the messages above.
if /i not "%~1"=="--no-pause" pause
exit /b 1
