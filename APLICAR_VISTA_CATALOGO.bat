@echo off
cd /d "%~dp0"
echo Recreando vista v_stock_rimec para el catalogo web...
python scripts\aplicar_vista_stock_cli.py
if errorlevel 1 (
  echo.
  echo Si fallo python, probando py...
  py scripts\aplicar_vista_stock_cli.py
)
echo.
echo Revisa scripts\aplicar_vista_stock_cli.log si hubo error.
pause
