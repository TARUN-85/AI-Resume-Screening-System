#!/usr/bin/env bash
#
# run.sh — start the AI Resume Screening API using this project's own venv.
# Run ./setup.sh first if ./venv doesn't exist yet.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -d "venv" ]; then
  echo "No venv/ found. Run ./setup.sh first."
  exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate
export PYTHONPATH="$PROJECT_DIR"

echo "Starting API at http://127.0.0.1:8000  (docs at /docs) — Ctrl+C to stop."
uvicorn src.main:app --reload
