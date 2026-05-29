@echo off
echo Iniciando modulo de Aprobaciones de Pedidos...
cd /d "%~dp0"
streamlit run streamlit_apps\aprobaciones.py --server.port 8502
pause
