@echo off
echo =======================================================
echo   SubFlow AI Studio - Dong goi ung dung Desktop (.EXE)
echo =======================================================
echo.

if not exist "venv\Scripts\pyinstaller.exe" (
    echo [!] Chua cai dat PyInstaller trong virtualenv.
    echo Dang tien hanh cai dat PyInstaller...
    .\venv\Scripts\pip.exe install pyinstaller
)

echo [*] Bat dau build bang PyInstaller...
echo Thoi gian build co the mat 1-3 phut tuy thuoc vao may tinh.
echo.

.\venv\Scripts\pyinstaller.exe SubFlowAI.spec --noconfirm

if %ERRORLEVEL% equ 0 (
    echo.
    echo =======================================================
    echo   [OK] Dong goi thanh cong!
    echo   File chay nam tai: dist\SubFlowAI\SubFlowAI.exe
    echo =======================================================
) else (
    echo.
    echo [ERROR] Qua trinh dong goi gap loi. Vui long kiem tra log o tren.
)

pause
