@echo off
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" -m streamlit run main.py %*
