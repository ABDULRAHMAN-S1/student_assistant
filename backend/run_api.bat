@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"

set "VENV_ACTIVATE=%SCRIPT_DIR%venv\Scripts\activate.bat"

if not exist "%VENV_ACTIVATE%" (
    echo [ERROR] Virtual environment activation script not found at "%VENV_ACTIVATE%".
    echo [ERROR] Create it with "py -3.13 -m venv venv" from the backend directory.
    popd
    exit /b 1
)

call "%VENV_ACTIVATE%"

python -m uvicorn app.api:app --host 127.0.0.1 --port 8000 --reload %*
set "EXIT_CODE=%ERRORLEVEL%"

popd
exit /b %EXIT_CODE%