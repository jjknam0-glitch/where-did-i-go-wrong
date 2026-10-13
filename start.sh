#!/usr/bin/env bash
# One-command start for Mac and Linux: installs what's missing, then runs the
# API (port 8000) and the web app (port 5173). Press Ctrl+C to stop both.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

say() { printf '\n\033[1m%s\033[0m\n' "$1"; }
fail() { printf '\n\033[31m%s\033[0m\n' "$1" >&2; exit 1; }

# 1. Check the tools
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || fail "Python 3.11 or newer is needed. Install it from https://www.python.org/downloads/ and run this again."
command -v node >/dev/null 2>&1 || fail "Node.js is needed. Install the LTS version from https://nodejs.org/ and run this again."
node -e 'process.exit(+process.versions.node.split(".")[0] >= 20 ? 0 : 1)' || fail "Node.js 20 or newer is needed (you have $(node -v)). Install the LTS version from https://nodejs.org/."

# 2. Backend: virtual environment, packages, settings file
cd "$ROOT/backend"
if [ ! -x .venv/bin/python ]; then
  say "Creating the Python environment (first run only)..."
  "$PY" -m venv .venv
fi
if [ ! -f .venv/.installed ] || [ requirements.txt -nt .venv/.installed ]; then
  say "Installing Python packages (first run takes a few minutes)..."
  .venv/bin/python -m pip install --upgrade pip --quiet
  .venv/bin/python -m pip install -r requirements.txt --quiet
  touch .venv/.installed
fi
if [ ! -f .env ]; then
  cp .env.example .env
  say "Created backend/.env. Add an API key there to read handwriting from your own photos (see GETTING_STARTED.md)."
fi

# 3. Frontend packages
cd "$ROOT/frontend"
if [ ! -d node_modules ] || [ package-lock.json -nt node_modules ]; then
  say "Installing web app packages (first run takes a minute)..."
  npm install --no-audit --no-fund
  touch node_modules
fi

# 4. Run both, and stop both on Ctrl+C
port_busy() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
for port in 8000 5173; do
  port_busy "$port" && fail "Port $port is already in use. The app may already be running in another window; close it and try again."
done
cd "$ROOT/backend"
.venv/bin/python -m uvicorn app.main:app --port 8000 &
API_PID=$!
cleanup() { kill "$API_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

for _ in $(seq 1 60); do
  curl -sf http://localhost:8000/api/health >/dev/null 2>&1 && break
  kill -0 "$API_PID" 2>/dev/null || fail "The API stopped while starting. Read the error above."
  sleep 0.5
done

say "Ready. Open http://localhost:5173 in your browser. Press Ctrl+C to stop."
cd "$ROOT/frontend"
npx vite --port 5173 --strictPort
