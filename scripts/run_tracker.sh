#!/bin/bash
# Kleinanzeigen Tracker Orchestration Wrapper Script (Bash)

# Get directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR" || exit 1

# Create logs directory if it doesn't exist
mkdir -p logs

# Generate timestamped log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/run_${TIMESTAMP}.log"

echo "=== Kleinanzeigen Tracker Run started at $(date) ===" > "$LOG_FILE"

# Set Database Connection Environment Variables conditionally
if [ -z "$DATABASE_URL" ]; then
    export PGHOST="${PGHOST:-localhost}"
    export PGPORT="${PGPORT:-5432}"
    export PGDATABASE="${PGDATABASE:-kleinanzeigen_tracker}"
    export PGUSER="${PGUSER:-tracker_user}"
    export PGPASSWORD="${PGPASSWORD:-tracker_password}"
fi

# Activate Python virtual environment if it exists
if [ -d ".venv" ]; then
    echo "Activating virtualenv in .venv..." >> "$LOG_FILE"
    source .venv/bin/activate >> "$LOG_FILE" 2>&1
elif [ -d "venv" ]; then
    echo "Activating virtualenv in venv..." >> "$LOG_FILE"
    source venv/bin/activate >> "$LOG_FILE" 2>&1
else
    echo "WARNING: No virtualenv (.venv or venv) found. Using system python." >> "$LOG_FILE"
fi

# Run Scrapers
echo "Running Category Scraper..." >> "$LOG_FILE"
python scraper/scrape_categories.py >> "$LOG_FILE" 2>&1
CAT_EXIT=$?

echo "Running Keyword Scraper..." >> "$LOG_FILE"
python scraper/scrape_keywords.py >> "$LOG_FILE" 2>&1
KEY_EXIT=$?

echo "=== Run finished at $(date) ===" >> "$LOG_FILE"

# Prune old logs (keep last 30 log files)
# Find logs matching run_*.log, sort oldest first, skip the newest 30, and delete
if [ -d "logs" ]; then
    ls -1tr logs/run_*.log 2>/dev/null | head -n -30 | xargs rm -f 2>/dev/null
fi

# Exit with status code of scrapers (non-zero if either failed)
if [ $CAT_EXIT -ne 0 ] || [ $KEY_EXIT -ne 0 ]; then
    echo "Tracker run completed with errors. Check $LOG_FILE for details."
    exit 1
else
    echo "Tracker run completed successfully. Log saved to $LOG_FILE"
    exit 0
fi
