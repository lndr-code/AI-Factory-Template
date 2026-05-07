#!/usr/bin/env bash
set -e

UI_PORT=$(grep -E '^UI_PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]' || echo "3000")

echo "Stopping any existing containers..."
docker compose down 2>/dev/null || true

echo "Starting AI Factory (UI on port $UI_PORT)..."
docker compose up -d
