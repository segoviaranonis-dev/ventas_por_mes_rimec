# Fase 1 — Carga real pilares (línea + L+R) — Importadora RIMEC
# Ejecutar en PowerShell desde la raíz del repo.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Linea = "C:\Users\hecto\Downloads\hasta el 15052026\linea.xlsx"
$Lr    = "C:\Users\hecto\Downloads\hasta el 15052026\linea_referencia.xlsx"

Write-Host "`n=== FASE 1 — CARGA REAL PILARES ===" -ForegroundColor Cyan

Write-Host "`n1) Conteo ANTES..." -ForegroundColor Yellow
python scripts/carga_real_fase1_conteo.py --etiqueta ANTES

if (-not (Test-Path $Linea)) { throw "No existe: $Linea" }
if (-not (Test-Path $Lr))    { throw "No existe: $Lr" }

Write-Host "`n2) Import linea + linea_referencia (latido cada 60s en consola)..." -ForegroundColor Yellow
python scripts/import_pilares_linea_lr_excel.py --linea $Linea --lr $Lr --proveedor-id 654

Write-Host "`n3) Conteo DESPUES..." -ForegroundColor Yellow
python scripts/carga_real_fase1_conteo.py --etiqueta DESPUES_IMPORT

Write-Host "`nListo. Revisá scripts/carga_real_conteo.log" -ForegroundColor Green
