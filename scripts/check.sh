#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/../backend"
python -m pytest tests -q

cd ../frontend
npm run build

cd ..
python scripts/e2e_check.py
