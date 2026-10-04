@echo off
setlocal enabledelayedexpansion
title SubFlow AI - 1-Click Build & Package Studio

echo =====================================================================
echo           SubFlow AI Studio - Quy Trinh Dong Goi Tu Dong
echo =====================================================================
echo.

:: 1. Activate Python Virtual Environment
if exist "venv\Scripts\activate.bat" (
    echo [*] Kich hoat moi truong Python venv...
    call venv\Scripts\activate.bat
) else (
    echo [ERROR] Khong tim thay thu muc moi truong 'venv'.
    echo Vui long tao moi truong ao va cai dat thu vien: python -m venv venv
    pause
    exit /b 1
)

:: 2. Check PyInstaller
where pyinstaller >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [*] Cai dat PyInstaller vao moi truong venv...
    pip install pyinstaller
)

:: 3. Check bundled FFmpeg
if not exist "ffmpeg_bin\ffmpeg.exe" (
    echo [!] CANH BAO: Khong tim thay 'ffmpeg_bin\ffmpeg.exe'.
    echo Ban can sao chep ffmpeg.exe vao thu muc ffmpeg_bin truoc khi dong goi
    echo de dam bao ung dung co the hoat dong doc lap tren moi may tinh.
    echo.
    set /p CONTINUE_BUILD="Ban co muon tiep tuc khong? (Y/N): "
    if /i not "!CONTINUE_BUILD!"=="Y" (
        echo Huy qua trinh dong goi.
        pause
        exit /b 1
    )
) else (
    echo [OK] Da tim thay bo giai ma FFmpeg bundled: ffmpeg_bin\ffmpeg.exe
)

:: 4. Clean previous build artifacts
echo [*] Don dep du lieu cac ban build cu...
if exist "build" rd /s /q "build"
if exist "dist\SubFlowAI" rd /s /q "dist\SubFlowAI"
if exist "dist_installer" rd /s /q "dist_installer"

:: 5. Execute PyInstaller
echo.
echo =====================================================================
echo  BUOC 1: Dong goi ma nguon thanh chuong trinh chay (PyInstaller)
echo =====================================================================
echo Dang bien dich va tao thu muc dist\SubFlowAI...
echo Qua trinh nay co the mat tu 1 - 3 phut tuy thuoc vao toc do CPU va SSD.
echo.

pyinstaller --clean SubFlowAI.spec --noconfirm

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] PyInstaller gap loi trong qua trinh dong goi.
    echo Vui long kiem tra lai thong bao loi o tren.
    pause
    exit /b 1
)

echo.
echo [OK] PyInstaller da hoan tat thanh cong!
echo Duong dan thu muc: dist\SubFlowAI\SubFlowAI.exe
echo.

:: 6. Locate Inno Setup Compiler (ISCC.exe)
echo =====================================================================
echo  BUOC 2: Dong goi thanh bo cai dat Setup duy nhat (Inno Setup)
echo =====================================================================

set "ISCC_PATH="

if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
) else if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
) else (
    for /f "tokens=*" %%i in ('where ISCC.exe 2^>nul') do set "ISCC_PATH=%%i"
)

if defined ISCC_PATH (
    echo [*] Phat hien Inno Setup Compiler tai: "!ISCC_PATH!"
    echo [*] Dang tao bo cai dat dist_installer\SubFlowAI_Setup_v2.0.exe...
    
    if not exist "dist_installer" mkdir "dist_installer"
    "!ISCC_PATH!" installer.iss
    
    if %ERRORLEVEL% equ 0 (
        echo.
        echo =====================================================================
        echo               DONG GOI THANH CONG HOAN TAT!
        echo =====================================================================
        echo  Tep cai dat: dist_installer\SubFlowAI_Setup_v2.0.exe
        echo  San sang de phan phoi cho nguoi dung Windows 64-bit.
        echo =====================================================================
    ) else (
        echo.
        echo [ERROR] Inno Setup bien dich that bai. Kiem tra thong tin o tren.
    )
) else (
    echo.
    echo [THONG BAO] Khong tim thay trinh bien dich Inno Setup (ISCC.exe).
    echo Ban chay doc lap da duoc tao thanh cong tai:
    echo   dist\SubFlowAI\SubFlowAI.exe
    echo.
    echo De tao file setup duy nhat (SubFlowAI_Setup_v2.0.exe), vui long tai
    echo va cai dat Inno Setup 6 tu: https://jrsoftware.org/isdl.php
    echo sau do chay lai file build_app.bat nay.
)

echo.
pause
