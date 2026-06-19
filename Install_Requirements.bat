@echo off
cd /d "%~dp0"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if exist "%VENV_PY%" (
    "%VENV_PY%" -m pip install -r requirements.txt
) else (
    echo [WARN] .venv not found, falling back to system python.
    python -m pip install -r requirements.txt
)

pause
