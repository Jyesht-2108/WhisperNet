# ──────────────────────────────────────────────────────
# WhisperNet Backend — Start Script (Windows PowerShell)
# ──────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "       WhisperNet Backend Launcher        " -ForegroundColor Cyan
Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── Check Docker ──
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Docker is not installed or not in PATH." -ForegroundColor Red
    Write-Host "        Please install Docker Desktop: https://docs.docker.com/get-docker/"
    exit 1
}
Write-Host "[OK] Docker found" -ForegroundColor Green

# ── Check Docker Compose V2 ──
try {
    docker compose version | Out-Null
    Write-Host "[OK] Docker Compose found" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker Compose is not available." -ForegroundColor Red
    Write-Host "        Please install Docker Desktop which includes Compose V2."
    exit 1
}

# ── Check Docker daemon ──
try {
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Daemon not running" }
    Write-Host "[OK] Docker daemon is running" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker daemon is not running." -ForegroundColor Red
    Write-Host "        Please start Docker Desktop."
    exit 1
}

# ── Create .env if missing ──
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $ProjectRoot "backend\.env"
$EnvExample = Join-Path $ProjectRoot "backend\.env.example"

if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-Host "[WARN] Created .env from .env.example — please update with your API keys." -ForegroundColor Yellow
    } else {
        Write-Host "[ERROR] No .env or .env.example found in backend\" -ForegroundColor Red
        exit 1
    }
}
Write-Host "[OK] Environment file exists" -ForegroundColor Green

Write-Host ""
Write-Host "Starting WhisperNet backend..." -ForegroundColor Cyan
Write-Host ""

Set-Location $ProjectRoot
docker compose up --build @args
