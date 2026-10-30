@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Khong tim thay Python trong venv. Hay tao moi moi truong ao hoac cai Python.
    pause
    exit /b 1
)
"venv\Scripts\python.exe" -m streamlit run app.py
pause
