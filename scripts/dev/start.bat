@echo off
chcp 65001 >nul
title ScopePilot
set "ROOT_DIR=%~dp0..\.."
set "BACKEND_DIR=%ROOT_DIR%\backend"
if exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
    set "BACKEND_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"
) else (
    set "BACKEND_PYTHON=python"
)

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
cd /d "%ROOT_DIR%\frontend"
call npm install
if errorlevel 1 goto failed
echo [2/3] Building frontend...
call npm run build
if errorlevel 1 goto failed
echo [3/3] Build complete!
echo.
echo Frontend output: frontend\dist\
goto end

:prod
echo [*] Production mode - http://localhost:8000
echo.
call "%~dp0start.bat" build
if errorlevel 1 goto failed
call :check_backend
if errorlevel 1 goto failed
echo.
echo [*] Starting backend server...
cd /d "%BACKEND_DIR%"
"%BACKEND_PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
goto end

:dev
echo [*] Development mode
echo     Frontend: http://localhost:5173
echo     Backend:  http://localhost:8000
echo.
call :check_backend
if errorlevel 1 goto failed
echo [1/2] Starting backend (port 8000)...
start "ScopePilot-Backend" /B cmd /c "cd /d ""%BACKEND_DIR%"" && ""%BACKEND_PYTHON%"" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo [2/2] Starting frontend (port 5173)...
start "ScopePilot-Frontend" /B cmd /c "cd /d ""%ROOT_DIR%\frontend"" && npm run dev"
echo.
echo Both servers are starting in the background.
echo Close this window to stop both servers.
timeout /t 5 >nul
echo.
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
goto end

:check_backend
pushd "%BACKEND_DIR%"
"%BACKEND_PYTHON%" -c "import app.main" >nul 2>&1
if errorlevel 1 (
    popd
    echo [ERROR] Backend environment is not ready.
    echo Run: uv sync --project backend
    echo Or create backend\.venv and run: backend\.venv\Scripts\python -m pip install -e . -e backend
    echo Also ensure backend\.env or root .env contains SECRET_KEY.
    exit /b 1
)
popd
exit /b 0

:failed
echo.
echo Startup aborted.
exit /b 1

:end
echo.
echo Done.
