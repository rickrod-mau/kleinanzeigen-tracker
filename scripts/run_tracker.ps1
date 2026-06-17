# Kleinanzeigen Tracker Orchestration Wrapper Script (PowerShell)

# Resolve script paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

# Move into project directory
Set-Location -Path $ProjectDir

# Create logs directory
if (!(Test-Path -Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

# Timestamped log path
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = "logs/run_$Timestamp.log"

Write-Output "=== Kleinanzeigen Tracker Run started at $(Get-Date) ===" | Out-File -FilePath $LogFile -Encoding utf8

# Set Database Connection Environment Variables (Process level) conditionally
if (-not $env:DATABASE_URL) {
    if (-not $env:PGHOST) { $env:PGHOST = "localhost" }
    if (-not $env:PGPORT) { $env:PGPORT = "5432" }
    if (-not $env:PGDATABASE) { $env:PGDATABASE = "kleinanzeigen_tracker" }
    if (-not $env:PGUSER) { $env:PGUSER = "tracker_user" }
    if (-not $env:PGPASSWORD) { $env:PGPASSWORD = "tracker_password" }
}

# Activate Python Virtual Environment if it exists
if (Test-Path -Path ".venv\Scripts\Activate.ps1") {
    Write-Output "Activating virtualenv in .venv..." | Out-File -FilePath $LogFile -Append -Encoding utf8
    & .venv\Scripts\Activate.ps1
} elseif (Test-Path -Path "venv\Scripts\Activate.ps1") {
    Write-Output "Activating virtualenv in venv..." | Out-File -FilePath $LogFile -Append -Encoding utf8
    & venv\Scripts\Activate.ps1
} else {
    Write-Output "WARNING: No virtualenv (.venv or venv) found. Using system python." | Out-File -FilePath $LogFile -Append -Encoding utf8
}

# Run Scrapers and capture outputs
Write-Output "Running Category Scraper..." | Out-File -FilePath $LogFile -Append -Encoding utf8
python scraper/scrape_categories.py *>&1 | Out-File -FilePath $LogFile -Append -Encoding utf8
$CatExit = $LASTEXITCODE

Write-Output "Running Keyword Scraper..." | Out-File -FilePath $LogFile -Append -Encoding utf8
python scraper/scrape_keywords.py *>&1 | Out-File -FilePath $LogFile -Append -Encoding utf8
$KeyExit = $LASTEXITCODE

Write-Output "=== Run finished at $(Get-Date) ===" | Out-File -FilePath $LogFile -Append -Encoding utf8

# Prune old logs (keep last 30 log files)
if (Test-Path -Path "logs") {
    Get-ChildItem -Path "logs" -Filter "run_*.log" | 
        Sort-Object LastWriteTime -Descending | 
        Select-Object -Skip 30 | 
        Remove-Item -Force -ErrorAction SilentlyContinue
}

# Return exit status
if ($CatExit -ne 0 -or $KeyExit -ne 0) {
    Write-Host "Tracker run completed with errors. Check $LogFile for details." -ForegroundColor Red
    exit 1
} else {
    Write-Host "Tracker run completed successfully. Log saved to $LogFile" -ForegroundColor Green
    exit 0
}
