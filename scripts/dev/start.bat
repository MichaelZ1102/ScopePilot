@echo off
chcp 65001 >nul
title ScopePilot

echo ========================================
echo   ScopePilot - AI Sprint Analysis
echo ========================================
echo.

if "%1"=="prod" goto prod
if "%1"=="dev" goto dev
if "%1"=="build" goto build

echo Usage:
echo   scripts\dev\start.bat prod    - Production mode (single port)
echo   scripts\dev\start.bat dev     - Development mode (hot reload)
echo   scripts\dev\start.bat build   - Build frontend only
goto end

:build
echo [1/3] Installing frontend dependencies...
cd /d "%~dp0..\..\frontend"
call npm install 2>nul
echo [2/3] Building frontend...
call npm run build
echo [3/3] Build complete!
echo.
echo Frontend output: frontend\dist\
goto end

:prod
echo [*] Production mode — http://localhost:8000
echo.
call "%~dp0start.bat" build
echo.
echo [*] Starting backend server...
cd /d "%~dp0..\..\backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
goto end

:dev
echo [*] Development mode
echo     Frontend: http://localhost:5173
echo     Backend:  http://localhost:8000
echo.
echo [1/2] Starting backend (port 8000)...
start "ScopePilot-Backend" /B cmd /c "cd /d ""%~dp0..\..\backend"" && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo [2/2] Starting frontend (port 5173)...
start "ScopePilot-Frontend" /B cmd /c "cd /d ""%~dp0..\..\frontend"" && npm run dev"
echo.
echo Both servers starting in background windows...
echo Close this window to stop both servers.
timeout /t 5 >nul
tasklist /fi "windowtitle eq ScopePilot*" 2>nul
echo.
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
goto end

:end
echo.
echo Done.
