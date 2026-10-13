@echo off
rem One-command start for Windows: installs what's missing, then runs the
rem API (port 8000) in its own window and the web app (port 5173) here.
setlocal
cd /d "%~dp0"
set "ROOT=%cd%"

rem 1. Check the tools
set "PY="
where py >nul 2>nul && py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo Python 3.11 or newer is needed. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" in the installer. Then run this again.
  pause & exit /b 1
)
where node >nul 2>nul || (
  echo.
  echo Node.js is needed. Install the LTS version from https://nodejs.org/ and run this again.
  pause & exit /b 1
)

rem 2. Backend: virtual environment, packages, settings file
cd /d "%ROOT%\backend"
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo Creating the Python environment ^(first run only^)...
  %PY% -m venv .venv || (pause & exit /b 1)
)
if not exist ".venv\.installed" (
  echo.
  echo Installing Python packages ^(first run takes a few minutes^)...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet || (pause & exit /b 1)
  type nul > ".venv\.installed"
)
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo.
  echo Created backend\.env. Add an API key there to read handwriting from your own photos.
)

rem 3. Frontend packages
cd /d "%ROOT%\frontend"
if not exist "node_modules" (
  echo.
  echo Installing web app packages ^(first run takes a minute^)...
  call npm install --no-audit --no-fund || (pause & exit /b 1)
)

rem 4. Run the API in its own window, the web app here
start "Where Did I Go Wrong? API" /d "%ROOT%\backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"
echo.
echo Ready. Open http://localhost:5173 in your browser.
echo To stop: press Ctrl+C here, and close the API window.
echo.
call npx vite --port 5173 --strictPort
