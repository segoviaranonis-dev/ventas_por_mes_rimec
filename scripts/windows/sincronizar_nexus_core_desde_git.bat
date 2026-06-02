@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=C:\Users\hecto\Nexus_Core"

echo.
echo ============================================================
echo  Nexus Core - sincronizacion segura desde GitHub
echo ============================================================
echo.
echo Este script NO borra cambios locales.
echo Si encuentra archivos modificados, se detiene en ese repo.
echo.

call :sync_repo "ventas_por_mes_rimec" || goto :error
call :sync_repo "report" || goto :error
call :sync_repo "rimec-web" || goto :error
call :sync_repo "bazzar-web" || goto :error
call :sync_repo "info_ventas_fotos" || goto :error

echo.
echo ============================================================
echo  OK - Todos los repos revisados y sincronizados.
echo ============================================================
echo.
pause
exit /b 0

:sync_repo
set "REPO=%~1"
set "DIR=%ROOT%\%REPO%"

echo.
echo ------------------------------------------------------------
echo  Revisando %REPO%
echo ------------------------------------------------------------

if not exist "%DIR%\.git" (
  echo ERROR: No encontre repo Git en "%DIR%".
  echo Revisa si la carpeta existe o si tiene otro nombre.
  exit /b 1
)

pushd "%DIR%" >nul

for /f "delims=" %%b in ('git branch --show-current') do set "BRANCH=%%b"
echo Rama actual: !BRANCH!

git status --short
for /f "delims=" %%s in ('git status --porcelain') do (
  echo.
  echo ATENCION: %REPO% tiene cambios locales.
  echo No hago pull para no pisar tu trabajo.
  echo.
  echo Comandos utiles:
  echo   cd "%DIR%"
  echo   git status
  echo   git diff --stat
  echo.
  popd >nul
  exit /b 1
)

echo Sin cambios locales. Trayendo ultimo Git...
git fetch origin
if errorlevel 1 (
  echo ERROR: fallo git fetch en %REPO%.
  popd >nul
  exit /b 1
)

git pull --ff-only
if errorlevel 1 (
  echo ERROR: fallo git pull --ff-only en %REPO%.
  echo Puede haber divergencia de ramas. Pedir ayuda antes de forzar.
  popd >nul
  exit /b 1
)

echo OK: %REPO% sincronizado.
popd >nul
exit /b 0

:error
echo.
echo ============================================================
echo  Sincronizacion detenida.
echo ============================================================
echo.
echo No se borro nada. Revisa el mensaje anterior y pedi ayuda.
echo.
pause
exit /b 1
