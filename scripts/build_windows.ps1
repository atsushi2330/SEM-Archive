# SEM-Archive Windows ビルドスクリプト (PyInstaller)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> Installing build deps"
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

Write-Host "==> Building EXE"
$dist = Join-Path (Get-Location) "dist\SEM-Archive"
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }

pyinstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name SEM-Archive `
  --paths src `
  --collect-all PySide6 `
  --collect-all pptx `
  src/sem_archive/app.py

Write-Host "==> Done: dist\SEM-Archive\SEM-Archive.exe"
Write-Host "Zip the dist\SEM-Archive folder and upload it to GitHub Releases."
