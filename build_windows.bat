@echo off
setlocal enabledelayedexpansion

REM ==========================================================
REM YKA Calipri - Windows build script (PyInstaller)
REM Recommended: run on Windows 10 x64 with Python 3.10 x64
REM Output: dist\YKA_Calipri_to_PDF\YKA_Calipri_to_PDF.exe
REM ==========================================================

cd /d "%~dp0"

echo [1/7] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python was not found in PATH.
  echo Please install Python 3.10 x64 and try again.
  exit /b 1
)

echo [2/7] Creating virtual environment...
if not exist ".venv" (
  python -m venv .venv
  if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    exit /b 1
  )
)

echo [3/7] Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo ERROR: Failed to activate virtual environment.
  exit /b 1
)

echo [4/7] Installing/upgrading build dependencies...
python -m pip install --upgrade pip wheel setuptools
if errorlevel 1 (
  echo ERROR: Failed to upgrade pip tooling.
  exit /b 1
)

echo [5/7] Installing project dependencies...
pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: Failed to install project dependencies.
  exit /b 1
)

echo [6/7] Installing PyInstaller...
pip install pyinstaller
if errorlevel 1 (
  echo ERROR: Failed to install PyInstaller.
  exit /b 1
)

echo [7/7] Building executable (one-folder mode)...
pyinstaller --noconfirm --clean --windowed --name YKA_Calipri_to_PDF app\main.py
if errorlevel 1 (
  echo ERROR: Build failed.
  exit /b 1
)

echo.
echo Build completed successfully.
echo EXE folder: %cd%\dist\YKA_Calipri_to_PDF
if exist "dist\YKA_Calipri_to_PDF\YKA_Calipri_to_PDF.exe" (
  echo EXE file:   %cd%\dist\YKA_Calipri_to_PDF\YKA_Calipri_to_PDF.exe
)

echo.
echo IMPORTANT:
echo - Copy the whole folder "dist\YKA_Calipri_to_PDF" to target server.
echo - If run issues occur on server, install VC++ Redistributable 2015-2022 x64.

exit /b 0
