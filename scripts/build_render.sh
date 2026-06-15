#!/usr/bin/env bash
# Render build script — Node (frontend) + Poetry (API)
set -euo pipefail

echo "=== Building React frontend ==="
npm run build:frontend

echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install poetry
poetry config virtualenvs.create false
poetry install --without dev --no-interaction

echo "=== Build complete ==="
