@echo off
cd /d "%~dp0"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if exist "%VENV_PY%" (
	"%VENV_PY%" -m streamlit run Web_Gui_Demo.py
) else (
	echo [WARN] .venv not found, falling back to system python.
	python -m streamlit run Web_Gui_Demo.py
)

pause
