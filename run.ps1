Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "             SubFlow AI Studio               " -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "Mở trình duyệt tại: http://localhost:8000`n" -ForegroundColor Yellow

& ".\venv\Scripts\uvicorn.exe" backend.app:app --host 0.0.0.0 --port 8000 --reload
