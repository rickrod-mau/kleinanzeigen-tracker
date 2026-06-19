# Kleinanzeigen Tracker - Cloud Deployment Guide

This guide contains everything you need to run your tracker fully in the cloud (using CockroachDB Serverless + GitHub Actions) and explains the lifecycle and deduplication features.

---

## 1. Cloud Database Setup (CockroachDB Serverless)

### A. Initializing Schema
To set up or reset your CockroachDB schema, execute the following command from your local terminal (ensure your virtual environment is active):
```bash
python scripts/init_cloud_db.py "postgresql://<username>:<password>@<host>:<port>/defaultdb?sslmode=require"
```
*(Note: We use `sslmode=require` to bypass local certificates checks on Windows/Linux while keeping all connection traffic fully encrypted).*

### B. Applying Schema Migration
If your database already contains data and you need to add lifecycle tracking columns, run these queries in your CockroachDB console:
```sql
ALTER TABLE listings ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active' NOT NULL;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS last_position INTEGER;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS is_topad BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS reposted_as_id VARCHAR(50) REFERENCES listings(listing_id) ON DELETE SET NULL;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS thumbnail_url TEXT;
```

### C. Updating Search Keywords
To update the search keywords in your cloud database to the new curated list (adding trendiest products and eliminating unwanted ones like dyson and thermomix), run this command:
```bash
python scripts/apply_keyword_update.py "postgresql://<username>:<password>@<host>:<port>/defaultdb?sslmode=require"
```
Or if you have the `DATABASE_URL` environment variable set:
```bash
python scripts/apply_keyword_update.py
```

---

## 2. GitHub Actions Automation

### A. Secret Configuration
To fully unlock the capabilities of the tracker, add the following repository secrets in GitHub under **Settings > Secrets and variables > Actions** (or set them in your local terminal environment):

1. **Database Connection:**
   * **Name:** `DATABASE_URL`
   * **Value:** `postgresql://<username>:<password>@<host>:<port>/defaultdb?sslmode=require`

2. **Proxy Rotation (Akamai Bypass):**
   * **Name:** `PROXY_URL`
   * **Value:** A single rotating proxy URL or a comma-separated list of proxies (e.g., `http://username:password@proxy1.com:1234,http://username:password@proxy2.com:5678`). The scraper will cycle through these to avoid blocks.

3. **Deal Hunter Bot Webhooks (Optional - Configure any or all):**
   * **Name:** `DISCORD_WEBHOOK_URL` -> Link for triggering Discord channel embeds.
   * **Name:** `TELEGRAM_BOT_TOKEN` -> Bot token from BotFather.
   * **Name:** `TELEGRAM_CHAT_ID` -> Target chat or channel ID.
   * **Name:** `SLACK_WEBHOOK_URL` -> Incoming Webhook URL for your Slack workspace.
   * **Name:** `DEAL_THRESHOLD` -> The discount threshold decimal (e.g. `0.70` triggers alerts for listings 30%+ below average; `0.80` triggers for 20%+ off. Defaults to `0.70`).

### B. Trigger & Schedule
* The workflow file is located at `.github/workflows/scrape.yml`.
* It is configured with an **activity-based schedule (GMT+2 / CEST local time)**:
  - **Low Traffic (Midnight - 7 AM):** Runs once at 04:00 AM local (02:00 UTC).
  - **Moderate Traffic (7 AM - 5 PM):** Runs every 2 hours (06:00, 08:00, 10:00, 12:00, 14:00 UTC).
  - **Prime Time Peak (5 PM - 11 PM):** Runs hourly (15:00, 16:00, 17:00, 18:00, 19:00, 20:00, 21:00 UTC).
* GitHub Actions scheduled cron runs can be delayed by 10 to 30 minutes depending on server loads. This is normal.
* You can trigger runs manually anytime by clicking **Run workflow** in the **Actions** tab on GitHub.

---

## 3. How the Inferred Sales & Repost Model Works

Since transaction history is private, this project uses a **Chronological Push-Down Inference Model** to determine if an item has been sold or reposted:

1. **Top Ads Filter:** Sponsored top ads are identified (class `.badge-topad` or `.is-topad`) and flagged. They are excluded from organic rank calculations.
2. **Organic Position Tracking:** Every active item is saved with its organic position (index from top, excluding sponsored ads) in the `last_position` column.
3. **Pushed Down Calculation:** During a new run, we count how many newly added listings ($K$) appeared at the top of the category.
4. **Missing Items Life Cycle:** If an active item disappears in the new run, we calculate its expected position: $\text{Expected Position} = \text{last\_position} + K$.
   * **Deduplication Check (Hack 1):** We check if there is a new listing in the same category with the exact same **thumbnail image URL**. If yes, it is marked as `reposted` (reposted as a new listing ID). If image URL is missing, it falls back to matching identical Title (case-insensitive) + Price + Location.
   * **Sold:** If no duplicate is found and the expected position was $\le 500$ for top categories or $\le 125$ for minor categories (our maximum scraped depth), the item is flagged as `sold`.
   * **Pushed Out:** If expected position exceeds these limits, it has gone off our scraped pages. We flag it as `pushed_out` (unknown status).

---

## 4. Useful Local Commands

### Environment Setup
```bash
python -m venv .venv
# Activate (Windows): .venv\Scripts\Activate.ps1
# Activate (Linux): source .venv/bin/activate
pip install -r requirements.txt
```

### Local Scrapes (against cloud DB)
If you want to run the scraper manually from your computer writing to the cloud:
```bash
# Set your env variable
$env:DATABASE_URL="postgresql://<username>:<password>@<host>:<port>/defaultdb?sslmode=require"

# Run it
.\scripts\run_tracker.ps1
```

### Download Cloud Logs to Local CSV
To download execution history from the cloud database to a local file:
```bash
python scripts/download_db_logs.py
```

---

## 5. Advanced Sales Reporting & Analytics View

To calculate active listing velocity and differentiate actual transactions from natural expirations, create this reporting view in your CockroachDB:

```sql
CREATE OR REPLACE VIEW v_sold_listings_analysis AS
SELECT 
    listing_id,
    category_id,
    title,
    price,
    location,
    first_seen_at,
    last_seen_at,
    -- Calculate active duration (Time Published Until Sell)
    (last_seen_at - first_seen_at) AS time_published_until_sell,
    -- Apply the business classification rules
    CASE 
        WHEN (last_seen_at - first_seen_at) < INTERVAL '2 hours' 
            THEN 'quick_deletion'
        WHEN (last_seen_at - first_seen_at) >= INTERVAL '29 days 23 hours' 
            THEN 'natural_expiration'
        ELSE 'probable_sale'
    END AS sales_classification
FROM listings
WHERE status = 'sold';
```

### Querying True Sales Velocity
Once the view is created, you can compute real sales volumes per category (excluding quick deletes and automatic 30-day listing timeouts):
```sql
SELECT 
    sales_classification,
    COUNT(*) as total_count,
    ROUND(AVG(price), 2) as average_sold_price
FROM v_sold_listings_analysis
GROUP BY sales_classification;
```

### 6. Best Time to Post Analytics View
To identify which days of the week and hours of the day listings are sold fastest, you can query the `v_best_time_to_post_analysis` view:

```sql
SELECT 
    post_day_name, 
    post_hour, 
    total_sold_listings, 
    avg_hours_to_sell
FROM v_best_time_to_post_analysis
ORDER BY avg_hours_to_sell ASC
LIMIT 10;
```
This query reveals the top 10 fastest-selling combinations of posting times, allowing you to optimize your own sales listings.


