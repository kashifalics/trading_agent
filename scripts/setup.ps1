# Windows PowerShell setup. Safe to re-run. Costs nothing, creates no accounts.
#   .\scripts\setup.ps1            # .env + backend venv/deps + frontend deps + DB migration
#   .\scripts\setup.ps1 -DockerOnly # only create .env (then: docker compose up --build)
param([switch]$DockerOnly)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Test-Tool($name, $cmd, $hint) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) { Write-Host "[ok]   $name" -ForegroundColor Green; return $true }
    Write-Host "[miss] $name -> $hint" -ForegroundColor Yellow; return $false
}
function New-Secret([int]$bytes = 32) {
    $b = New-Object byte[] $bytes; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    return ([Convert]::ToBase64String($b) -replace '[+/=]', 'x')
}

Write-Host "== Checking prerequisites =="
$docker = Test-Tool "Docker" "docker" "install Docker Desktop (free for personal use) to use 'docker compose up'"
$py = Test-Tool "Python 3.11+" "python" "https://www.python.org/downloads/"
$node = Test-Tool "Node.js 20+" "node" "https://nodejs.org/"
Test-Tool "Tesseract OCR (optional)" "tesseract" "optional: enables reading symbol/timeframe/price axis from screenshots (https://github.com/UB-Mannheim/tesseract/wiki)" | Out-Null

if (-not (Test-Path ".env")) {
    $content = Get-Content ".env.example" -Raw
    $content = $content -replace 'APP_SECRET_KEY=.*', "APP_SECRET_KEY=$(New-Secret 48)"
    $content = $content -replace 'POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$(New-Secret 24)"
    Set-Content -Path ".env" -Value $content -Encoding utf8
    Write-Host "Created .env with generated secrets (never committed)." -ForegroundColor Green
} else { Write-Host ".env already exists - left untouched." }

if ($DockerOnly) { Write-Host "Next: docker compose up --build"; exit 0 }

if ($py) {
    Write-Host "== Backend =="
    Set-Location "$root\backend"
    if (-not (Test-Path ".venv")) { python -m venv .venv }
    & .\.venv\Scripts\python -m pip install --quiet --upgrade pip
    & .\.venv\Scripts\python -m pip install --quiet -r requirements-dev.txt
    if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
    & .\.venv\Scripts\python -m alembic upgrade head
    Set-Location $root
}
if ($node) {
    Write-Host "== Frontend =="
    Set-Location "$root\frontend"
    npm ci --no-audit --no-fund
    if (-not (Test-Path ".env.local")) { Copy-Item ".env.example" ".env.local" }
    Set-Location $root
}
Write-Host ""
Write-Host "Done. Run without Docker:" -ForegroundColor Green
Write-Host "  backend : cd backend; .\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000"
Write-Host "  frontend: cd frontend; npm run dev"
Write-Host "Or with Docker: docker compose up --build"
Write-Host "XAUUSD needs a free Twelve Data key: put it in .env / backend\.env as TWELVE_DATA_API_KEY (https://twelvedata.com/pricing)."
