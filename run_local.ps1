# Nexus Core — Streamlit en localhost
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$pySystem = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe"
if (-not (Test-Path $pySystem)) {
    $pySystem = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $pySystem) { throw "No se encontró Python. Instálalo o ajusta la ruta en run_local.ps1." }

$venvPy = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
$needVenv = -not (Test-Path $venvPy)
if (-not $needVenv) {
    try {
        & $venvPy -c "import streamlit" 2>$null
        if ($LASTEXITCODE -ne 0) { $needVenv = $true }
    } catch { $needVenv = $true }
}

if ($needVenv) {
    Write-Host "Recreando venv..."
    if (Test-Path "venv") { Remove-Item -Recurse -Force "venv" }
    & $pySystem -m venv venv
    & $venvPy -m pip install --upgrade pip
    & $venvPy -m pip install -r requirements.txt
}

Write-Host "Iniciando Nexus Core (usa python -m streamlit; evita streamlit.exe roto)"
Write-Host "URL tipica: http://localhost:8501"
& $venvPy -m streamlit run main.py --server.headless true
