param(
  [switch]$NoNgrok,
  [switch]$NoMigrate,
  [switch]$NoNginx,
  [int]$DaphnePort = 5000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
$NginxDir = "C:\nginx"

# ──────────────────────────────────────────────
# PHASE 1 — Setup (in this terminal)
# ──────────────────────────────────────────────
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CAUFA Portal — Launching all services" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Virtual env
Write-Host "[1/5] Activating virtual environment..." -ForegroundColor Yellow
if (Test-Path $VenvActivate) {
  . $VenvActivate
  Write-Host "  -> Virtual env activated." -ForegroundColor Green
} else {
  Write-Host "  -> Virtual env not found at $VenvActivate" -ForegroundColor Red
  exit 1
}

# 2. Dependencies
Write-Host "[2/5] Checking dependencies..." -ForegroundColor Yellow
& $VenvPython -m pip install -q -r "$ProjectRoot\requirements.txt" 2>&1 | Out-Null
# Ensure watchfiles for --reload support
& $VenvPython -m pip install -q watchfiles 2>&1 | Out-Null
Write-Host "  -> Dependencies up to date." -ForegroundColor Green

# 3. Migrations
if (-not $NoMigrate) {
  Write-Host "[3/5] Applying database migrations..." -ForegroundColor Yellow
  & $VenvPython "$ProjectRoot\manage.py" migrate 2>&1
  if ($LASTEXITCODE -eq 0) {
    Write-Host "  -> Migrations applied." -ForegroundColor Green
  } else {
    Write-Host "  -> Migration failed. Check errors above." -ForegroundColor Red
    exit 1
  }
} else {
  Write-Host "[3/5] Skipping migrations (-NoMigrate)." -ForegroundColor Gray
}

# 4. System checks
Write-Host "[4/5] Running system checks..." -ForegroundColor Yellow
& $VenvPython "$ProjectRoot\manage.py" check 2>&1
if ($LASTEXITCODE -eq 0) {
  Write-Host "  -> System checks passed." -ForegroundColor Green
} else {
  Write-Host "  -> System checks found issues." -ForegroundColor Red
}

Write-Host "[5/5] Launching service terminals..." -ForegroundColor Yellow

# ──────────────────────────────────────────────
# PHASE 2 — Launch each service in its own terminal
# ──────────────────────────────────────────────
$pidList = @()

# --- Terminal A: Nginx (:80) ---
if (-not $NoNginx) {
  $p = Start-Process powershell -WindowStyle Normal -PassThru -ArgumentList @"
-NoExit -Command `$Host.UI.RawUI.WindowTitle = 'NGINX (:80)'; & {
  Write-Host 'Nginx reverse-proxy — press Ctrl+C to stop' -ForegroundColor Cyan
  C:/nginx/nginx.exe -g 'daemon off;' -p C:/nginx
}
"@
  $pidList += $p.Id
  Write-Host "  -> Nginx terminal launched (PID $($p.Id))" -ForegroundColor Green
  Start-Sleep -Seconds 1
} else {
  Write-Host "  -> Nginx skipped (-NoNginx)." -ForegroundColor Gray
}

# --- Terminal B: Daphne ASGI (127.0.0.1:$DaphnePort) with watchfiles reload ---
$reloadCmd = @"
cd '$ProjectRoot'
.\.venv\Scripts\Activate.ps1
`$Host.UI.RawUI.WindowTitle = 'DAPHNE RELOAD (:$DaphnePort)'
Write-Host 'Daphne ASGI server — watching for file changes (watchfiles)' -ForegroundColor Cyan
python reload.py $DaphnePort
"@
$p = Start-Process powershell -WindowStyle Normal -PassThru -ArgumentList "-NoExit", "-Command", $reloadCmd
$pidList += $p.Id
Write-Host "  -> Daphne (--reload) terminal launched (PID $($p.Id))" -ForegroundColor Green
Start-Sleep -Seconds 1

# --- Terminal C: Ngrok (tunnel to nginx :80, or Daphne directly if no nginx) ---
if (-not $NoNgrok) {
  $targetPort = if ($NoNginx) { $DaphnePort } else { 80 }
  $p = Start-Process powershell -WindowStyle Normal -PassThru -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle = 'NGROK (-> :$targetPort)'; & { Write-Host 'ngrok tunnel — press Ctrl+C to stop' -ForegroundColor Cyan; ngrok http $targetPort }"
  $pidList += $p.Id
  Write-Host "  -> Ngrok terminal launched (PID $($p.Id))" -ForegroundColor Green
  Start-Sleep -Seconds 4
  try {
    $ngrokUrl = (Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -ErrorAction Stop).tunnels[0].public_url
    Write-Host "  -> ngrok URL: $ngrokUrl" -ForegroundColor Green
  } catch {
    Write-Host "  -> ngrok status UI: http://127.0.0.1:4040" -ForegroundColor Gray
  }
} else {
  Write-Host "  -> Ngrok skipped (-NoNgrok)." -ForegroundColor Gray
}

# ──────────────────────────────────────────────
# DONE
# ──────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All services launched!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Nginx:   http://localhost" -ForegroundColor Green
Write-Host "  Daphne:  127.0.0.1:$DaphnePort" -ForegroundColor Green
if (-not $NoNgrok) {
  Write-Host "  ngrok:   http://127.0.0.1:4040" -ForegroundColor Green
}
Write-Host ""
Write-Host "  Close terminals individually, or run:" -ForegroundColor Gray
Write-Host "  Get-Process -Id $($pidList -join ',') | Stop-Process" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
