@echo off
title FileSeek
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [FileSeek] First run: creating virtual environment...
    python -m venv --system-site-packages venv
    if errorlevel 1 (
        echo [FileSeek] ERROR: Could not create venv. Make sure Python 3.10+ is installed.
        pause
        exit /b 1
    )
    echo [FileSeek] Installing dependencies...
    "venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    "venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo [FileSeek] Starting FileSeek at http://127.0.0.1:7860
start "" "http://127.0.0.1:7860"
"venv\Scripts\python.exe" src\app.py
pause
