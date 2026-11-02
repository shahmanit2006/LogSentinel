@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found. Create it with: py -3.11 -m venv .venv
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python -m streamlit run app.py
