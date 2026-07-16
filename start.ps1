param(
  [switch]$NoNgrok,
  [switch]$NoMigrate,
  [int]$DaphnePort = 5000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CAUFA Portal — Launching" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] Activating virtual environment..." -ForegroundColor Yellow
if (Test-Path $VenvActivate) {
  . $VenvActivate
  Write-Host "  -> Virtual env activated." -ForegroundColor Green
} else {
  Write-Host "  -> Virtual env not found at $VenvActivate" -ForegroundColor Red
  exit 1
}

Write-Host "[2/4] Checking dependencies..." -ForegroundColor Yellow
$pipResult = & $VenvPython -m pip install -q -r "$ProjectRoot\requirements.txt" 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "  -> pip reported issues (shown below), but continuing..." -ForegroundColor Yellow
  $pipResult | ForEach-Object { Write-Host "     $_" -ForegroundColor DarkGray }
} else {
  Write-Host "  -> Dependencies up to date." -ForegroundColor Green
}

if (-not $NoMigrate) {
  Write-Host "[3/4] Applying database migrations..." -ForegroundColor Yellow
  & $VenvPython "$ProjectRoot\manage.py" migrate 2>&1
  if ($LASTEXITCODE -eq 0) {
    Write-Host "  -> Migrations applied." -ForegroundColor Green
  } else {
    Write-Host "  -> Migration failed. Check errors above." -ForegroundColor Red
    exit 1
  }
} else {
  Write-Host "[3/4] Skipping migrations (-NoMigrate)." -ForegroundColor Gray
}

Write-Host "[4/4] Launching service terminals..." -ForegroundColor Yellow
$pidList = @()

# --- Terminal A: Daphne ASGI + uvicorn auto-reload ---
$reloadCmd = @"
cd '$ProjectRoot'
.\.venv\Scripts\Activate.ps1
`$Host.UI.RawUI.WindowTitle = 'DAPHNE (:$DaphnePort)'
Write-Host 'Daphne ASGI + auto-reload — Ctrl+C to stop' -ForegroundColor Cyan
python reload.py $DaphnePort
"@
$p = Start-Process powershell -WindowStyle Normal -PassThru -ArgumentList "-NoExit", "-Command", $reloadCmd
$pidList += $p.Id
Write-Host "  -> Daphne terminal launched (PID $($p.Id))" -ForegroundColor Green
Start-Sleep -Seconds 2

# --- Terminal B: Ngrok tunnel ---
if (-not $NoNgrok) {
  $p = Start-Process powershell -WindowStyle Normal -PassThru -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle = 'NGROK'; & { Write-Host 'ngrok tunnel — Ctrl+C to stop' -ForegroundColor Cyan; ngrok http $DaphnePort }"
  $pidList += $p.Id
  Write-Host "  -> Ngrok terminal launched (PID $($p.Id))" -ForegroundColor Green
  Start-Sleep -Seconds 4
  try {
    $ngrokUrl = (Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -ErrorAction Stop).tunnels[0].public_url
    Write-Host "  -> Public URL: $ngrokUrl" -ForegroundColor Green
  } catch {
    Write-Host "  -> ngrok status UI: http://127.0.0.1:4040" -ForegroundColor Gray
  }
} else {
  Write-Host "  -> Ngrok skipped (-NoNgrok)." -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All services launched!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Local:   http://127.0.0.1:$DaphnePort" -ForegroundColor Green
if (-not $NoNgrok) {
  Write-Host "  ngrok:   http://127.0.0.1:4040" -ForegroundColor Green
}
Write-Host ""
Write-Host "  Close terminals individually, or run:" -ForegroundColor Gray
Write-Host "  Get-Process -Id $($pidList -join ',') | Stop-Process" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
