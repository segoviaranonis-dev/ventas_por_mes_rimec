# Nexus Core — arranque Streamlit (evita streamlit.exe con ruta de venv vieja)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "venv no encontrado. Ejecutá: powershell -File .\run_local.ps1"
    exit 1
}
& $py -m streamlit run main.py @args
