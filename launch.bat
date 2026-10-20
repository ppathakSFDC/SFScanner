@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>&1 || (
    echo Installing uv (first run only)...
    powershell -Command "irm https://astral.sh/uv/install.ps1 | iex"
)

if not exist backend\.venv (
    echo Creating Python environment (first run only)...
    uv venv --python 3.11 backend\.venv
)

echo Syncing Python dependencies...
uv pip install -q -r backend\requirements.txt --python backend\.venv\Scripts\python.exe

if exist frontend\package.json (
    where npm >nul 2>&1 && (
        if not exist frontend\dist\index.html (
            echo Building frontend bundle...
            pushd frontend
            call npm install --silent
            call npm run build --silent
            popd
        )
    ) || (
        echo npm not found. Using existing frontend\dist build if present.
    )
)

echo.
echo   SF Scanner -- Salesforce Best Practice Analyzer
echo   App URL: http://localhost:8765
echo.
start http://localhost:8765
backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
