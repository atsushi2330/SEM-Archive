# SEM-Archive Windows ビルドスクリプト (PyInstaller, onedir)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> Installing build deps"
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
pip install pyinstaller

Write-Host "==> Detecting Python DLL (WinPython 対策)"
$pyDll = python -c @"
import sys
from pathlib import Path
base = Path(sys.base_prefix)
candidates = [
    base / f'python{sys.version_info.major}{sys.version_info.minor}.dll',
    base / 'python3.dll',
]
for p in candidates:
    if p.exists():
        print(p.resolve())
        break
"@

$dist = Join-Path (Get-Location) "dist\SEM-Archive"
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }

$pyiArgs = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--onedir",
    "--name", "SEM-Archive",
    "--paths", "src",
    "--collect-all", "PySide6",
    "--collect-all", "pptx"
)

if ($pyDll) {
    Write-Host "Including: $pyDll"
    $pyiArgs += @("--add-binary", "$pyDll;.")
} else {
    Write-Warning "python3*.dll not found under Python prefix. Build may fail on other PCs."
}

$pyiArgs += "src/sem_archive/app.py"

Write-Host "==> Building EXE"
python -m PyInstaller @pyiArgs

Write-Host "==> Verifying bundle"
$exe = Join-Path $dist "SEM-Archive.exe"
if (-not (Test-Path $exe)) {
    throw "Build failed: $exe not found"
}

$bundledDll = Get-ChildItem -Path $dist -Recurse -Filter "python3*.dll" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($bundledDll) {
    Write-Host "Bundled Python DLL: $($bundledDll.FullName)"
} elseif ($pyDll) {
    Write-Warning "python3*.dll missing in dist. Copying manually..."
    Copy-Item $pyDll (Join-Path $dist "_internal") -ErrorAction SilentlyContinue
    Copy-Item $pyDll $dist -ErrorAction SilentlyContinue
}

$zip = Join-Path (Get-Location) "SEM-Archive-windows.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $dist -DestinationPath $zip

Write-Host ""
Write-Host "==> Done"
Write-Host "  Folder: $dist"
Write-Host "  EXE:    $exe"
Write-Host "  ZIP:    $zip"
Write-Host ""
Write-Host "配布時は ZIP ごと渡すこと（exe 単体では動きません）。"
Write-Host "起動先PCに Microsoft Visual C++ 2015-2022 x64 再頒布可能パッケージが必要な場合があります。"
