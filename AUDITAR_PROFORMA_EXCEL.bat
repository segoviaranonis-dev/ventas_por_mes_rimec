@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo === Auditoria Proforma Excel vs BD (7320/239) ===
echo.
python scripts\auditar_proforma_excel_pp.py "C:\Users\hecto\Downloads\faturaProforma_7447_2026.xlsx SIN DESC.xlsx" --linea 7320 --ref 239 --proforma 744
echo.
pause
