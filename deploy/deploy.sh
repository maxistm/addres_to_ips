#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required" >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "docker compose is required" >&2
    exit 1
fi

cd "$SCRIPT_DIR"
docker compose up -d --build

echo "Deployment finished locally from: $PROJECT_ROOT"
