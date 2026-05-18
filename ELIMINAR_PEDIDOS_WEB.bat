@echo off
cd /d "%~dp0"
echo.
echo  Elimina TODOS los pedidos de prueba de la web (Pedidos / PVR-...)
echo  y devuelve el stock reservado. Unos segundos.
echo.
python scripts\limpieza_pedidos_viejos.py --todos --yes
if errorlevel 1 (
  echo.
  py scripts\limpieza_pedidos_viejos.py --todos --yes
)
echo.
echo Listo. Recarga http://localhost:3001/pedidos — debe decir "Sin pedidos".
pause
