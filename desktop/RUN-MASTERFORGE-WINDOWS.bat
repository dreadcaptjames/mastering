@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title MasterForge AI - Native Python Desktop

echo ================================================
echo    MasterForge AI - Native Python Desktop
echo ================================================
echo    No GitHub, Node.js or Electron required.
echo.

where py >nul 2>nul
if not errorlevel 1 (
  set "PYCMD=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] Python is not installed or is not on PATH.
    echo Install Python from https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )
  set "PYCMD=python"
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python environment...
  %PYCMD% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Could not create a Python environment.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -c "import tkinter" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Tkinter is unavailable. Reinstall Python with the Tcl/Tk feature enabled.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "from masterforge_python.engine import ffmpeg_binary; ffmpeg_binary()" >nul 2>nul
if errorlevel 1 (
  echo FFmpeg is not installed. Installing a local FFmpeg binary...
  ".venv\Scripts\python.exe" -m pip install imageio-ffmpeg
  if errorlevel 1 (
    echo [ERROR] FFmpeg installation failed. Check your connection or install FFmpeg manually.
    pause
    exit /b 1
  )
)
echo Starting MasterForge AI...
".venv\Scripts\python.exe" -m masterforge_python
if errorlevel 1 (
  echo.
  echo [ERROR] MasterForge encountered a Python error. Review the lines above.
  pause
)
endlocal
