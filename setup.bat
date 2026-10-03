@echo off
REM setup.bat — one-shot environment setup for the AI Resume Screening System
REM on Windows. Mirrors setup.sh: installs the required Python version (via
REM the "py" launcher), creates ./venv inside this project folder, and
REM installs requirements.txt into it. Everything for this project stays in
REM this one folder.

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

set /p REQUIRED_VERSION=<.python-version
for /f "tokens=1,2 delims=." %%a in ("%REQUIRED_VERSION%") do (
    set "REQ_MAJOR=%%a"
    set "REQ_MINOR=%%b"
)
set "REQ_MM=%REQ_MAJOR%.%REQ_MINOR%"

echo ==============================================
echo  AI Resume Screening System - environment setup
echo ==============================================
echo Project folder : %PROJECT_DIR%
echo Required Python: %REQUIRED_VERSION%
echo.

REM --------------------------------------------------------------------
REM Step 1: locate the required Python version via the py launcher
REM --------------------------------------------------------------------
echo [1/4] Looking for Python %REQ_MM% via the "py" launcher...
py -%REQ_MM% --version >nul 2>&1
if %errorlevel%==0 (
    echo       Found Python %REQ_MM%.
    set "PYTHON_CMD=py -%REQ_MM%"
) else (
    echo       Python %REQ_MM% is not installed.
    echo       Attempting to install it automatically via "py --install"...
    py --install %REQ_MM% >nul 2>&1
    py -%REQ_MM% --version >nul 2>&1
    if %errorlevel%==0 (
        echo       Installed Python %REQ_MM% successfully.
        set "PYTHON_CMD=py -%REQ_MM%"
    ) else (
        echo.
        echo       Could not auto-install Python %REQ_MM%.
        echo       Please download it from:
        echo         https://www.python.org/downloads/release/python-31210/
        echo       then re-run this script. Falling back to default "python" for now.
        set "PYTHON_CMD=python"
    )
)
echo.

REM --------------------------------------------------------------------
REM Step 2: create the project-local virtual environment
REM --------------------------------------------------------------------
if "%1"=="--recreate" if exist venv (
    echo [2/4] --recreate passed - removing existing venv\ ...
    rmdir /s /q venv
)

if exist venv (
    echo [2/4] venv\ already exists - reusing it ^(pass --recreate to force a rebuild^).
) else (
    echo [2/4] Creating virtual environment at .\venv ...
    %PYTHON_CMD% -m venv venv
)
echo.

REM --------------------------------------------------------------------
REM Step 3: activate it and install dependencies
REM --------------------------------------------------------------------
echo [3/4] Installing dependencies from requirements.txt ...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo       Done.
echo.

REM --------------------------------------------------------------------
REM Step 4: quick self-check
REM --------------------------------------------------------------------
echo [4/4] Verifying the environment with a quick import check ...
python -c "import fastapi, sklearn, numpy, pydantic; print('      All core packages import OK.')"
echo.

echo ==============================================
echo  Setup complete.
echo ==============================================
echo Everything for this project - code, data, venv - lives in:
echo   %PROJECT_DIR%
echo.
echo Next steps:
echo   venv\Scripts\activate.bat      (activate the environment manually)
echo   run.bat                        (or just run this to start the API)
echo   set PYTHONPATH=. ^&^& pytest tests\ -v
echo ==============================================

endlocal
