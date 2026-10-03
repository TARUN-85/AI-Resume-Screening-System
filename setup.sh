#!/usr/bin/env bash
#
# setup.sh — one-shot environment setup for the AI Resume Screening System.
#
# What this script does, in order:
#   1. Reads the required Python version from .python-version (3.12.10).
#   2. Makes sure that EXACT Python version is available:
#        - uses pyenv to install it if pyenv is present (recommended), or
#        - falls back to a system `python3.12` if one exists, or
#        - warns and offers to install pyenv for you.
#   3. Creates a virtual environment at ./venv — INSIDE this project
#      folder, so the whole project (code + data + venv) stays self-contained
#      in one directory and never touches your global Python packages.
#   4. Installs every dependency from requirements.txt into that venv.
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
#
# Re-running this script is safe — it skips steps that are already done,
# unless you pass --recreate to force a clean rebuild of the venv.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

REQUIRED_VERSION="$(cat .python-version 2>/dev/null || echo "3.12.10")"
REQUIRED_MAJOR_MINOR="$(echo "$REQUIRED_VERSION" | cut -d. -f1,2)"
VENV_DIR="$PROJECT_DIR/venv"
RECREATE=false

for arg in "$@"; do
  if [ "$arg" = "--recreate" ]; then
    RECREATE=true
  fi
done

echo "=============================================="
echo " AI Resume Screening System — environment setup"
echo "=============================================="
echo "Project folder : $PROJECT_DIR"
echo "Required Python: $REQUIRED_VERSION"
echo ""

# --------------------------------------------------------------------------
# Step 1: locate (or install) the exact required Python version
# --------------------------------------------------------------------------
PYTHON_BIN=""

if command -v pyenv >/dev/null 2>&1; then
  echo "[1/4] pyenv found — using it to install Python $REQUIRED_VERSION (if needed)..."
  pyenv install -s "$REQUIRED_VERSION"
  pyenv local "$REQUIRED_VERSION"
  PYTHON_BIN="$(pyenv root)/versions/$REQUIRED_VERSION/bin/python"

elif command -v "python$REQUIRED_MAJOR_MINOR" >/dev/null 2>&1; then
  echo "[1/4] Found python$REQUIRED_MAJOR_MINOR on PATH — using it directly."
  PYTHON_BIN="$(command -v "python$REQUIRED_MAJOR_MINOR")"

else
  echo "[1/4] pyenv is not installed and python$REQUIRED_MAJOR_MINOR was not found on PATH."
  echo ""
  if [ -t 0 ]; then
    read -r -p "      Install pyenv now so this script can get the exact Python version? [y/N] " ans
  else
    echo "      (non-interactive shell detected — skipping the pyenv install prompt)"
    ans="n"
  fi
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    curl -fsSL https://pyenv.run | bash
    export PATH="$HOME/.pyenv/bin:$PATH"
    eval "$(pyenv init -)"
    pyenv install -s "$REQUIRED_VERSION"
    pyenv local "$REQUIRED_VERSION"
    PYTHON_BIN="$(pyenv root)/versions/$REQUIRED_VERSION/bin/python"
  else
    echo ""
    echo "      Falling back to whatever 'python3' resolves to on this machine."
    SYS_VERSION="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "none")"
    if [ "$SYS_VERSION" != "$REQUIRED_MAJOR_MINOR" ]; then
      echo "      WARNING: system python3 is $SYS_VERSION, not $REQUIRED_MAJOR_MINOR."
      echo "      The project may still work (requirements.txt targets 3.10-3.12)"
      echo "      but results/behaviour are only guaranteed on $REQUIRED_VERSION."
    fi
    PYTHON_BIN="$(command -v python3)"
  fi
fi

if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: could not locate a usable Python interpreter. Aborting."
  exit 1
fi

echo "      Using interpreter: $PYTHON_BIN ($("$PYTHON_BIN" --version))"
echo ""

# --------------------------------------------------------------------------
# Step 2: create the project-local virtual environment
# --------------------------------------------------------------------------
if [ "$RECREATE" = true ] && [ -d "$VENV_DIR" ]; then
  echo "[2/4] --recreate passed — removing existing venv/ ..."
  rm -rf "$VENV_DIR"
fi

if [ -d "$VENV_DIR" ]; then
  echo "[2/4] venv/ already exists — reusing it (pass --recreate to force a rebuild)."
else
  echo "[2/4] Creating virtual environment at ./venv ..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
echo ""

# --------------------------------------------------------------------------
# Step 3: activate it and install dependencies
# --------------------------------------------------------------------------
echo "[3/4] Installing dependencies from requirements.txt ..."
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "      Done."
echo ""

# --------------------------------------------------------------------------
# Step 4: quick self-check
# --------------------------------------------------------------------------
echo "[4/4] Verifying the environment with a quick import check ..."
python -c "import fastapi, sklearn, numpy, pydantic; print('      All core packages import OK.')"
echo ""

echo "=============================================="
echo " Setup complete."
echo "=============================================="
echo "Everything for this project — code, data, venv — lives in:"
echo "  $PROJECT_DIR"
echo ""
echo "Next steps:"
echo "  source venv/bin/activate     # activate the environment manually"
echo "  ./run.sh                     # or just run this to start the API"
echo "  PYTHONPATH=. pytest tests/ -v"
echo "=============================================="
