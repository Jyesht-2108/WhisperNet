#!/usr/bin/env bash
# ──────────────────────────────────────────────────────
# WhisperNet Backend — Start Script (macOS / Linux)
# ──────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       WhisperNet Backend Launcher        ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── Check Docker ──
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker is not installed or not in PATH.${NC}"
    echo "  Please install Docker Desktop: https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}✓ Docker found${NC}"

# ── Check Docker Compose (V2 plugin or standalone) ──
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    echo -e "${GREEN}✓ Docker Compose (V2 plugin) found${NC}"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    echo -e "${GREEN}✓ Docker Compose (standalone) found${NC}"
else
    echo -e "${RED}✗ Docker Compose is not installed.${NC}"
    echo "  Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# ── Check Docker daemon is running ──
if ! docker info &> /dev/null 2>&1; then
    echo -e "${RED}✗ Docker daemon is not running.${NC}"
    echo "  Please start Docker Desktop or the Docker daemon."
    exit 1
fi
echo -e "${GREEN}✓ Docker daemon is running${NC}"

# ── Create .env if it doesn't exist ──
ENV_FILE="$PROJECT_ROOT/backend/.env"
ENV_EXAMPLE="$PROJECT_ROOT/backend/.env.example"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        echo -e "${YELLOW}⚠ Created .env from .env.example — please update with your API keys.${NC}"
    else
        echo -e "${RED}✗ No .env or .env.example found in backend/.${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓ Environment file exists${NC}"

echo ""
echo -e "${CYAN}Starting WhisperNet backend...${NC}"
echo ""

cd "$PROJECT_ROOT"
$COMPOSE_CMD up --build "$@"
