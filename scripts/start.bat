@echo off
REM ──────────────────────────────────────────────────────
REM WhisperNet Backend — Start Script (Windows CMD)
REM ──────────────────────────────────────────────────────

echo ══════════════════════════════════════════
echo        WhisperNet Backend Launcher
echo ══════════════════════════════════════════
echo.

REM ── Check Docker ──
where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is not installed or not in PATH.
    echo         Please install Docker Desktop: https://docs.docker.com/get-docker/
    exit /b 1
)
echo [OK] Docker found

REM ── Check Docker Compose V2 ──
docker compose version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker Compose is not available.
    echo         Please install Docker Desktop which includes Compose V2.
    exit /b 1
)
echo [OK] Docker Compose found

REM ── Check Docker daemon ──
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker daemon is not running.
    echo         Please start Docker Desktop.
    exit /b 1
)
echo [OK] Docker daemon is running

REM ── Create .env if missing ──
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
set "ENV_FILE=%PROJECT_ROOT%\backend\.env"
set "ENV_EXAMPLE=%PROJECT_ROOT%\backend\.env.example"

if not exist "%ENV_FILE%" (
    if exist "%ENV_EXAMPLE%" (
        copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        echo [WARN] Created .env from .env.example — please update with your API keys.
    ) else (
        echo [ERROR] No .env or .env.example found in backend\
        exit /b 1
    )
)
echo [OK] Environment file exists

echo.
echo Starting WhisperNet backend...
echo.

cd /d "%PROJECT_ROOT%"
docker compose up --build %*
