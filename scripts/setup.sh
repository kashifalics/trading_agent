#!/usr/bin/env bash
# macOS / Linux / Git-Bash setup. Safe to re-run. Costs nothing, creates no accounts.
#   ./scripts/setup.sh              # .env + backend venv/deps + frontend deps + DB migration
#   ./scripts/setup.sh --docker-only
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

check() { if command -v "$2" >/dev/null 2>&1; then echo "[ok]   $1"; return 0; else echo "[miss] $1 -> $3"; return 1; fi; }
secret() { python3 - "$1" <<'EOF' 2>/dev/null || head -c "$1" /dev/urandom | base64 | tr -d '+/=\n'
import secrets, sys
print(secrets.token_urlsafe(int(sys.argv[1])))
EOF
}

echo "== Checking prerequisites =="
check "Docker" docker "install Docker (free for personal use) to use 'docker compose up'" || true
PY=python3; command -v python3 >/dev/null || PY=python
check "Python 3.11+" "$PY" "https://www.python.org/downloads/" && HAVE_PY=1 || HAVE_PY=0
check "Node.js 20+" node "https://nodejs.org/" && HAVE_NODE=1 || HAVE_NODE=0
check "Tesseract OCR (optional)" tesseract "optional: apt install tesseract-ocr / brew install tesseract" || true

if [ ! -f .env ]; then
  sed -e "s|^APP_SECRET_KEY=.*|APP_SECRET_KEY=$(secret 48)|" -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(secret 24)|" .env.example > .env
  echo "Created .env with generated secrets (never committed)."
else
  echo ".env already exists - left untouched."
fi
[ "${1:-}" = "--docker-only" ] && { echo "Next: docker compose up --build"; exit 0; }

if [ "$HAVE_PY" = 1 ]; then
  echo "== Backend =="
  cd "$ROOT/backend"
  [ -d .venv ] || "$PY" -m venv .venv
  VPY=.venv/bin/python; [ -x "$VPY" ] || VPY=.venv/Scripts/python
  "$VPY" -m pip install --quiet --upgrade pip
  "$VPY" -m pip install --quiet -r requirements-dev.txt
  [ -f .env ] || cp .env.example .env
  "$VPY" -m alembic upgrade head
fi
if [ "$HAVE_NODE" = 1 ]; then
  echo "== Frontend =="
  cd "$ROOT/frontend"
  npm ci --no-audit --no-fund
  [ -f .env.local ] || cp .env.example .env.local
fi
echo
echo "Done. Without Docker:  (cd backend && .venv/bin/python -m uvicorn app.main:app --reload --port 8000)  and  (cd frontend && npm run dev)"
echo "With Docker: docker compose up --build"
echo "XAUUSD needs a free Twelve Data key in TWELVE_DATA_API_KEY (https://twelvedata.com/pricing)."
