@echo off
title SubFlow AI
echo =============================================
echo               SubFlow AI Studio
echo =============================================
echo Dang khoi dong may chu...
echo Truy cap tai: http://localhost:8000
echo.
.\venv\Scripts\uvicorn.exe backend.app:app --host 0.0.0.0 --port 8000 --reload
pause
