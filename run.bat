@echo off
REM run.bat — start the AI Resume Screening API using this project's own venv.
REM Run setup.bat first if venv\ doesn't exist yet.

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

if not exist venv (
    echo No venv found. Run setup.bat first.
    exit /b 1
)

call venv\Scripts\activate.bat
set "PYTHONPATH=%PROJECT_DIR%"

echo Starting API at http://127.0.0.1:8000  (docs at /docs) - Ctrl+C to stop.
uvicorn src.main:app --reload
