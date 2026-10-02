@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    echo Create a virtual environment and install requirements first.
    echo See README.md for setup instructions.
    pause
)
