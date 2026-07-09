@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem =============================================================================
rem SEM-Archive EXE build (WinPython)
rem
rem Usage:
rem   1. Edit WPYTHON_ROOT below if your WinPython path differs
rem   2. Double-click this file, or run from cmd:
rem        scripts\build_windows_winpython.bat
rem
rem Output:
rem   dist\SEM-Archive\          … 配布フォルダ（このフォルダごと渡す）
rem   SEM-Archive-windows.zip    … ZIP 版
rem =============================================================================

if not defined WPYTHON_ROOT set "WPYTHON_ROOT=C:\WPy64-31450"
set "PYTHON=%WPYTHON_ROOT%\python\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] WinPython の python.exe が見つかりません:
    echo         %PYTHON%
    echo.
    echo 対処:
    echo   - WinPython をインストールする
    echo   - この bat の先頭付近の WPYTHON_ROOT を正しいパスに変更する
    echo   - または環境変数 WPYTHON_ROOT を設定してから再実行する
    echo     例: set WPYTHON_ROOT=C:\WPy64-31450
    pause
    exit /b 1
)

cd /d "%~dp0\.."
echo ==^> Repo: %CD%
echo ==^> Python: %PYTHON%
"%PYTHON%" --version
if errorlevel 1 (
    echo [ERROR] Python の起動に失敗しました
    pause
    exit /b 1
)

echo.
echo ==^> Installing build dependencies
"%PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :fail
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto :fail
"%PYTHON%" -m pip install -e .
if errorlevel 1 goto :fail
"%PYTHON%" -m pip install pyinstaller
if errorlevel 1 goto :fail

echo.
echo ==^> Detecting Python DLL (WinPython)
for /f "delims=" %%D in ('"%PYTHON%" -c "import sys; from pathlib import Path; b=Path(sys.base_prefix); c=[b / f'python{sys.version_info.major}{sys.version_info.minor}.dll', b / 'python3.dll']; print(next((str(p.resolve()) for p in c if p.exists()), ''))"') do set "PY_DLL=%%D"
if defined PY_DLL (
    echo Including: !PY_DLL!
    set "PYI_BINARY=--add-binary=!PY_DLL!;."
) else (
    echo [WARN] python3*.dll が見つかりません。別 PC で起動できない場合があります。
    set "PYI_BINARY="
)

set "DIST=%CD%\dist\SEM-Archive"
if exist "%DIST%" (
    echo ==^> Removing old dist
    rmdir /s /q "%DIST%"
)

echo.
echo ==^> Building EXE with PyInstaller
"%PYTHON%" -m PyInstaller --noconfirm --clean --windowed --onedir --name SEM-Archive --paths src --collect-all PySide6 --collect-all pptx !PYI_BINARY! src/sem_archive/app.py
if errorlevel 1 goto :fail

set "EXE=%DIST%\SEM-Archive.exe"
if not exist "%EXE%" (
    echo [ERROR] Build failed: %EXE% not found
    goto :fail
)

if defined PY_DLL (
    dir /s /b "%DIST%\python3*.dll" >nul 2>&1
    if errorlevel 1 (
        echo [WARN] dist に python3*.dll がありません。手動コピーします...
        if exist "%DIST%\_internal\" copy /y "!PY_DLL!" "%DIST%\_internal\" >nul
        copy /y "!PY_DLL!" "%DIST%\" >nul
    )
)

set "ZIP=%CD%\SEM-Archive-windows.zip"
if exist "%ZIP%" del /f /q "%ZIP%"

echo.
echo ==^> Creating ZIP
powershell -NoProfile -Command "Compress-Archive -Path '%DIST%' -DestinationPath '%ZIP%' -Force"
if errorlevel 1 goto :fail

echo.
echo ========================================
echo  Build complete
echo   Folder: %DIST%
echo   EXE:    %EXE%
echo   ZIP:    %ZIP%
echo ========================================
echo.
echo 配布時は ZIP ごと渡すこと（exe 単体では動きません）。
echo 起動先 PC に Visual C++ 2015-2022 x64 再頒布可能パッケージが必要な場合があります。
echo.
pause
exit /b 0

:fail
echo.
echo [ERROR] ビルドに失敗しました
pause
exit /b 1
