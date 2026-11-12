@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title MasterForge AI - Build Windows Setup Installer

echo ===================================================
echo          MASTERFORGE AI - Setup Builder
echo ===================================================
echo Builds a per-user Windows installer from the verified EXE.
echo No GitHub, Node.js, or Electron needed.
echo.

if not exist "installer\MasterForgeAI.iss" (
  echo [ERROR] Installer recipe missing: installer\MasterForgeAI.iss
  goto :fail
)

if not exist "dist\MasterForge-AI.exe" (
  echo No portable EXE found. Building one with PyInstaller first...
  call "%~dp0BUILD-WINDOWS-EXE.bat" --no-pause
  if errorlevel 1 goto :fail
)

if not exist "dist\MasterForge-AI.exe" (
  echo [ERROR] No dist\MasterForge-AI.exe was produced.
  goto :fail
)

echo.
echo Verifying portable EXE and bundled audio engine...
set "SMOKE_REPORT=%CD%\dist\masterforge-installer-check.txt"
if exist "%SMOKE_REPORT%" del /q "%SMOKE_REPORT%"
start "" /wait "%CD%\dist\MasterForge-AI.exe" --self-test "%SMOKE_REPORT%"
if errorlevel 1 goto :smoke_failed
if not exist "%SMOKE_REPORT%" goto :smoke_failed
findstr /B /C:"READY:" "%SMOKE_REPORT%" >nul
if errorlevel 1 goto :smoke_failed

echo Passed executable self-test.
echo.

set "ISCC="
if defined MASTERFORGE_ISCC if exist "%MASTERFORGE_ISCC%" set "ISCC=%MASTERFORGE_ISCC%"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 7\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC for /f "delims=" %%P in ('where ISCC.exe 2^>nul') do if not defined ISCC set "ISCC=%%P"

if not defined ISCC (
  echo [ERROR] Inno Setup compiler was not found.
  echo Download and install Inno Setup from https://jrsoftware.org/isdl.php
  echo Or use: winget install --id JRSoftware.InnoSetup -e -s winget -i
  echo Then run this builder again. You do not need to rebuild the portable EXE.
  goto :fail
)

echo Using compiler: "%ISCC%"
echo Building the branded setup wizard and uninstaller...
"%ISCC%" "installer\MasterForgeAI.iss"
if errorlevel 1 goto :fail

if not exist "dist\MasterForge-AI-Setup-0.9.2.exe" (
  echo [ERROR] Setup.exe not found in dist. See the compiler messages above.
  goto :fail
)

echo.
echo [SUCCESS] Windows installer created!
echo File: %CD%\dist\MasterForge-AI-Setup-0.9.2.exe
echo.
echo Run that installer to add MasterForge to Start menu and Installed Apps.
echo For verified publisher status, the installer must be code-signed separately.
echo.
pause
exit /b 0

:smoke_failed
echo [ERROR] Portable app failed its engine / bundled FFmpeg self-test.
if exist "%SMOKE_REPORT%" type "%SMOKE_REPORT%"
goto :fail

:fail
echo.
echo [ERROR] Installer build did not finish. See messages above.
pause
exit /b 1
