#!/usr/bin/env bash
# Render build script — Node (frontend) + pip (API) + ML model cache
set -euo pipefail

echo "=== Building React frontend ==="
npm run build:frontend

echo "=== Installing Python dependencies ==="
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "=== Pre-downloading ML models (avoids Render port-detection timeout) ==="
PYTHONPATH=. python scripts/warmup_models.py

echo "=== Build complete ==="
