#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not in PATH." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running." >&2
  exit 1
fi

cd "$ROOT_DIR"

echo "Building and starting SightTalk AI with Docker Compose..."
echo "Frontend: http://127.0.0.1:5173"
echo "Backend health: http://127.0.0.1:8000/api/v1/health"
echo "Press Ctrl+C to stop."

docker compose up --build

