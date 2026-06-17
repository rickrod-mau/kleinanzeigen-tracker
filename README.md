# Kleinanzeigen.de Market Activity Tracker

A fully local, free, self-hosted pipeline that periodically collects proxy data for "most active/popular categories" and "most searched keywords" on kleinanzeigen.de (Germany's largest classifieds site), stores it in a PostgreSQL database, and exposes it via a Metabase reporting dashboard.

---

## ⚠️ Important Caveats & Reality Check

1. **No Public API**: Kleinanzeigen.de has **no public API** for sales data, search volume, or trending items. This tracker uses **proxies** to approximate market activity:
   - **Category Listing Counts** (scraped from category pages) act as a proxy for category size/activity.
   - **Search Result Counts** (scraped from keyword search results) act as a proxy for overall demand/supply volume.
   - **Repeated Listing Titles** (sampled from the first page of category results) act as a rough proxy for high-volume item types (e.g., dealers, mass listings, or highly popular items).
2. **Polite Scraping**: Scraping HTML can violate terms of service and trigger automated blocks. This tracker implements polite scraping features:
   - **Randomized Delays** (2 to 5 seconds) between page requests.
   - **Rotating User-Agents** representing modern web browsers.
   - **Exponential Backoff** and retries when encountering HTTP `429` (Rate Limited) or `5xx` (Server Error) status codes.
3. **HTML Selector Maintenance**: Since we parse static HTML, if Kleinanzeigen.de changes its website design or class names, the scrapers **will break**. Refer to the [Maintenance & Troubleshooting](#maintenance--troubleshooting) section on how to fix selectors when they break.

---

## Project Structure

```text
kleinanzeigen-tracker/
├── docker-compose.yml       # PostgreSQL & Metabase orchestration
├── init-db.sql              # Initialization script (creates Metabase app database)
├── schema.sql               # Database schema, seed data, and SQL views
├── requirements.txt         # Python libraries
├── scraper/
│   ├── __init__.py
│   ├── helper.py            # Shared HTTP helper and DB connector
│   ├── scrape_categories.py # Scrapes category listings and samples ads
│   └── scrape_keywords.py   # Scrapes keyword counts and samples prices
└── scripts/
    ├── run_tracker.sh       # Orchestration shell script (Linux/macOS/WSL)
    ├── run_tracker.ps1      # Orchestration PowerShell script (Windows)
    └── crontab.txt          # Example cron job schedules
```

---

## Getting Started

### 1. Docker Services Startup
Ensure [Docker Desktop](https://www.docker.com/products/docker-desktop/) is installed and running on your local machine.

In the project root directory, run the following command to spin up PostgreSQL and Metabase:
```bash
docker compose up -d
```

#### What happens under the hood?
1. The PostgreSQL container starts up.
2. It executes `init-db.sql` to create a separate database `metabase_db` for Metabase's internal configuration.
3. It executes `schema.sql` on the default database `kleinanzeigen_tracker` to set up tables, views, and seed data.
4. Metabase starts up once PostgreSQL reports healthy, and connects to its own database.

---

### 2. Python Environment Setup
We recommend setting up a virtual environment to manage dependencies:

#### On Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

#### On Linux / macOS / WSL (Bash):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### 3. Manual Test Run
You can run the scraper pipeline manually to test if it populates the database correctly.

#### On Windows (PowerShell):
```powershell
# This runs both scrapers sequentially and saves logs to the logs/ directory
.\scripts\run_tracker.ps1
```

#### On Linux / macOS / WSL (Bash):
Make the script executable and run it:
```bash
chmod +x scripts/run_tracker.sh
./scripts/run_tracker.sh
```

A log file will be generated in `logs/run_YYYYMMDD_HHMMSS.log` showing details of the run. Old logs will automatically be pruned (retaining the last 30 runs).

---

## Orchestration & Scheduling

To automate the pipeline, you can schedule the wrapper script to run periodically (e.g. daily or every 6 hours).

### Linux / macOS / WSL (Cron)
1. Open your crontab editor:
   ```bash
   crontab -e
   ```
2. Add one of the following entries (make sure to replace `/absolute/path/to/` with your actual directory path):
   ```text
   # Run daily at 03:15 AM
   15 3 * * * /bin/bash /absolute/path/to/kleinanzeigen-tracker/scripts/run_tracker.sh >/dev/null 2>&1
   
   # Alternative: Run every 6 hours (at 15 minutes past the hour)
   15 */6 * * * /bin/bash /absolute/path/to/kleinanzeigen-tracker/scripts/run_tracker.sh >/dev/null 2>&1
   ```

### Windows (Task Scheduler)
To run the tracker periodically on Windows:
1. Open **Task Scheduler**.
2. Click **Create Basic Task** and name it (e.g., `Kleinanzeigen Tracker`).
3. Set the trigger to **Daily** and set a start time (e.g., `03:15 AM`).
4. Select **Start a program** as the action.
5. In the **Program/script** field, type `powershell.exe`.
6. In **Add arguments**, type:
   `-ExecutionPolicy Bypass -File "C:\path\to\kleinanzeigen-tracker\scripts\run_tracker.ps1"`
7. Click **Finish**.

---

## Metabase Reporting & Dashboards

Metabase is hosted locally at [http://localhost:3000](http://localhost:3000).

### Initial Configuration
1. Open [http://localhost:3000](http://localhost:3000) in your web browser and click **Let's go**.
2. Create an admin account.
3. When prompted to **Add your data**, select **PostgreSQL** and enter the following details:
   - **Display name**: `Kleinanzeigen Tracker`
   - **Host**: `db` (or `localhost` if connecting from external tools outside Docker)
   - **Port**: `5432`
   - **Database name**: `kleinanzeigen_tracker`
   - **Database username**: `tracker_user`
   - **Database password**: `tracker_password`
4. Click **Save** and finish setup.

### SQL Views Available
The database includes pre-configured SQL views that you can use to build dashboards:

| View Name | Purpose | Suggested Visualization |
| :--- | :--- | :--- |
| `v_latest_category_snapshots` | Shows the current listing counts and average prices for each category. | **Bar Chart** / **Table** (Current Size) |
| `v_category_trends` | Tracks category size (`total_listings`) and average price samples over time. | **Line Chart** (Trends over time) |
| `v_latest_keyword_snapshots` | Shows current result counts and average price samples for keywords. | **Table** (Keyword popularity) |
| `v_keyword_trends` | Tracks search volume (`result_count`) and average price trends per keyword. | **Line Chart** (Keyword volume trends) |
| `v_top_repeated_listing_titles` | Shows listing titles that appear multiple times in the first pages. | **Table / Word Cloud** (Popular products/dealers) |
| `v_scrape_job_health` | Tracks execution health, running times, and error messages. | **Status Indicators** / **Table** (Scraping Health) |

---

## Maintenance & Troubleshooting

### HTML Selector Breaks
Websites frequently update their frontend structures, changing IDs or classes. If a scraper fails to parse count or listing details, follow these steps:

1. Open a web browser, go to a tracked category page or search page, and open developer tools (`F12`).
2. **Finding the Total Listings Count selector**:
   - Inspect the element displaying the listing count (e.g., "(12.435 Ergebnisse)").
   - Identify its class name or parent selector.
   - Update `parse_total_count(soup)` in [scrape_categories.py](file:///C:/Users/ricar/.gemini/antigravity/scratch/kleinanzeigen-tracker/scraper/scrape_categories.py) or [scrape_keywords.py](file:///C:/Users/ricar/.gemini/antigravity/scratch/kleinanzeigen-tracker/scraper/scrape_keywords.py).
3. **Finding Listing Container selectors**:
   - Inspect a listing container on the page. In Kleinanzeigen.de, it's typically an `<article class="aditem">` or `<li>` tag.
   - If class names have changed, update `scrape_category_page` or `scrape_keyword` search selectors:
     - Container: `article.aditem`
     - Title/URL: `.aditem-main--title-line a`
     - Price: `.aditem-main--middle--price-shipping--price`
     - Location: `.aditem-main--bottom--left`

### IP Blocks / Cloudflare / HTTP 403
If you receive `HTTP 403 Forbidden` and the log outputs warning messages about bot detection:
1. Increase the minimum delay inside `make_request()` in [helper.py](file:///C:/Users/ricar/.gemini/antigravity/scratch/kleinanzeigen-tracker/scraper/helper.py) (e.g., change `random.uniform(2.0, 5.0)` to `random.uniform(5.0, 10.0)`).
2. Configure proxy rotation in `make_request()` by passing a `proxies` dictionary to `requests.get()`.
3. If pages block static HTTP clients completely, a headless browser solution like **Playwright** or **Selenium** will be required to execute JavaScript and pass anti-bot challenges.
