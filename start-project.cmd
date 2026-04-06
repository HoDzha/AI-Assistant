@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found in .venv
    echo Create or restore the virtual environment before starting the project.
    exit /b 1
)

set "PYTHONUTF8=1"

echo Starting backend on http://127.0.0.1:8000 ...
start "Freelance Flow Backend" cmd /k ""%PYTHON_EXE%" -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000"

timeout /t 2 /nobreak >nul

echo Starting frontend on http://127.0.0.1:5500 ...
start "Freelance Flow Frontend" cmd /k ""%PYTHON_EXE%" -m http.server 5500 --directory frontend --bind 127.0.0.1"

echo.
echo Project started.
echo Backend:  http://127.0.0.1:8000/api/health
echo Frontend: http://127.0.0.1:5500
echo.
echo Close the opened terminal windows to stop the project.

endlocal
