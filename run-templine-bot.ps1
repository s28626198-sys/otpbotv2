param(
    [switch]$SkipConnectivityCheck
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "Stopping previous bot instances (if any)..." -ForegroundColor Yellow
Get-CimInstance Win32_Process |
Where-Object {
    $_.Name -match '^python(\.exe)?$' -and
    $_.CommandLine -match 'smsbower_premium_bot\.py'
} |
ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}

if (-not $env:ADMIN_USER_ID) {
    $env:ADMIN_USER_ID = "5742928021"
}

if (-not $env:SUPABASE_URL) {
    $env:SUPABASE_URL = "https://zpavyjdtbydfceamfzwg.supabase.co"
}

if (-not $env:SUPABASE_SERVICE_ROLE_KEY -and -not $env:SUPABASE_KEY -and -not $env:SUPABASE_SECRET_KEY) {
    Write-Host "Set SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY or SUPABASE_SECRET_KEY before running." -ForegroundColor Red
    exit 1
}

if (-not $SkipConnectivityCheck) {
    Write-Host "Checking connectivity to api.telegram.org:443 ..." -ForegroundColor Yellow
    $conn = Test-NetConnection api.telegram.org -Port 443 -WarningAction SilentlyContinue
    if (-not $conn.TcpTestSucceeded) {
        Write-Host "Network check failed (api.telegram.org:443). Bot may not receive/send updates." -ForegroundColor Red
    } else {
        Write-Host "Network check passed." -ForegroundColor Green
    }
}

Write-Host "Starting Templine bot..." -ForegroundColor Green
python .\smsbower_premium_bot.py
