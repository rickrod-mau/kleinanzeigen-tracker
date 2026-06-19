import os
import time
import random
import logging
import requests
import psycopg2
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("tracker_helper")

# List of modern browser User-Agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 OPR/109.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
]

# Proxy configuration loaded from PROXY_URL env variable
# Can be a single proxy or comma-separated list of proxies
PROXY_URLS = []
proxy_env = os.environ.get("PROXY_URL")
if proxy_env:
    PROXY_URLS = [p.strip() for p in proxy_env.split(",") if p.strip()]
    logger.info(f"Loaded {len(PROXY_URLS)} proxy server(s) for rotation.")

def get_db_connection():
    """
    Establish a connection to the PostgreSQL database.
    Uses DATABASE_URL, or individual PG environment variables, or falls back to defaults.
    """
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        logger.info("Connecting to database using DATABASE_URL")
        return psycopg2.connect(db_url)
    
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    dbname = os.environ.get("PGDATABASE", "kleinanzeigen_tracker")
    user = os.environ.get("PGUSER", "tracker_user")
    password = os.environ.get("PGPASSWORD", "tracker_password")
    sslmode = os.environ.get("PGSSLMODE", "prefer")
    sslrootcert = os.environ.get("PGSSLROOTCERT")
    
    logger.info(f"Connecting to database at {host}:{port}/{dbname} (sslmode={sslmode})")
    
    conn_params = {
        "host": host,
        "port": port,
        "database": dbname,
        "user": user,
        "password": password,
        "sslmode": sslmode
    }
    if sslrootcert:
        conn_params["sslrootcert"] = sslrootcert
        
    return psycopg2.connect(**conn_params)

def make_request(url, params=None, max_retries=3):
    """
    Executes an HTTP GET request with:
    - Random polite delays (2 to 5 seconds) before the request
    - Rotated User-Agents and browser-mimicking headers
    - Proxy rotation if configured
    - Exponential backoff retry logic for 403, 429, and 5xx errors.
    """
    # Polite scraping: random delay before making the request
    delay = random.uniform(2.0, 5.0)
    logger.info(f"Polite delay: sleeping for {delay:.2f} seconds before requesting {url}")
    time.sleep(delay)
    
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0"
    }
    
    base_backoff = 10  # starting backoff delay in seconds
    
    for attempt in range(1, max_retries + 1):
        proxies = None
        current_proxy = None
        if PROXY_URLS:
            current_proxy = PROXY_URLS[(attempt - 1) % len(PROXY_URLS)]
            proxies = {
                "http": current_proxy,
                "https": current_proxy
            }
            logger.info(f"Using proxy (Attempt {attempt}): {current_proxy}")
            
        try:
            logger.info(f"Fetching: {url} (Attempt {attempt}/{max_retries})")
            response = requests.get(url, params=params, headers=headers, timeout=15, proxies=proxies)
            
            if response.status_code == 200:
                return response
            
            elif response.status_code == 429:
                backoff = base_backoff * (2 ** (attempt - 1)) + random.uniform(2.0, 5.0)
                logger.warning(f"HTTP 429 (Too Many Requests) received. Backing off for {backoff:.2f} seconds.")
                if attempt == max_retries:
                    response.raise_for_status()
                time.sleep(backoff)
                
            elif response.status_code >= 500:
                backoff = base_backoff * (2 ** (attempt - 1)) + random.uniform(2.0, 5.0)
                logger.warning(f"HTTP {response.status_code} received. Retrying in {backoff:.2f} seconds.")
                if attempt == max_retries:
                    response.raise_for_status()
                time.sleep(backoff)
                
            elif response.status_code == 403:
                backoff = base_backoff * (2 ** (attempt - 1)) + random.uniform(2.0, 5.0)
                logger.warning(f"HTTP 403 Forbidden. The site's anti-scraping systems (e.g. Akamai/DataDome) might be blocking the request. Retrying in {backoff:.2f} seconds.")
                if attempt == max_retries:
                    response.raise_for_status()
                time.sleep(backoff)
                
            else:
                logger.error(f"Request failed with status code {response.status_code}.")
                response.raise_for_status()
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error on attempt {attempt}: {str(e)}")
            if attempt == max_retries:
                raise e
            backoff = base_backoff * (2 ** (attempt - 1)) + random.uniform(2.0, 5.0)
            time.sleep(backoff)
            
    raise Exception(f"Failed to fetch page {url} after {max_retries} attempts.")

def send_deal_alert(listing, keyword, avg_price):
    """
    Sends a deal notification to Discord, Telegram, and Slack webhooks if configured.
    """
    title = listing.get('title')
    price = listing.get('price')
    url = listing.get('listing_url')
    thumb = listing.get('thumbnail_url')
    loc = listing.get('location')
    rating = listing.get('seller_rating')
    
    # Calculate discount percent
    discount_pct = 0
    if avg_price and price:
        savings = float(avg_price) - float(price)
        discount_pct = round((savings / float(avg_price)) * 100)
    else:
        savings = 0
        
    rating_str = f"⭐ {rating}" if rating else "Not Rated"
    if rating and "naja" in rating.lower():
        rating_str += " ⚠️ LOW TRUST SELLER"

    logger.info(f"Triggering Deal Alert for '{title}' (Price: {price} €, Avg: {avg_price} €, Save: {discount_pct}%)")

    # 1. Discord Notification
    discord_webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if discord_webhook:
        try:
            embed = {
                "title": f"🚨 DEAL ALERT: {title}",
                "url": url,
                "color": 3066993, # Green
                "fields": [
                    {"name": "Price", "value": f"**{price:.2f} €**" if price is not None else "N/A", "inline": True},
                    {"name": "Avg Price", "value": f"{avg_price:.2f} €" if avg_price is not None else "N/A", "inline": True},
                    {"name": "Savings", "value": f"{savings:.2f} € ({discount_pct}% off)" if savings > 0 else "N/A", "inline": True},
                    {"name": "Location", "value": loc or "Unknown", "inline": True},
                    {"name": "Seller Rating", "value": rating_str, "inline": True},
                    {"name": "Matched Keyword", "value": keyword, "inline": True}
                ],
                "footer": {"text": "Kleinanzeigen Deal Hunter Bot"}
            }
            if thumb:
                embed["thumbnail"] = {"url": thumb}
                
            response = requests.post(discord_webhook, json={"embeds": [embed]}, timeout=10)
            if response.status_code not in (200, 204):
                logger.error(f"Failed to send Discord notification: HTTP {response.status_code}")
        except Exception as ex:
            logger.error(f"Error sending Discord notification: {str(ex)}")

    # 2. Telegram Notification
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if tg_token and tg_chat_id:
        try:
            msg = (
                f"🚨 <b>DEAL ALERT</b> 🚨\n\n"
                f"<b>Item:</b> <a href='{url}'>{title}</a>\n"
                f"<b>Price:</b> {price:.2f} €\n"
                f"<b>Keyword Avg Price:</b> {avg_price:.2f} €\n"
                f"<b>Savings:</b> {savings:.2f} € (<b>{discount_pct}% off</b>)\n"
                f"<b>Location:</b> {loc or 'Unknown'}\n"
                f"<b>Seller Rating:</b> {rating_str}\n"
                f"<b>Keyword:</b> #{keyword.replace(' ', '_')}"
            )
            if thumb:
                tg_url = f"https://api.telegram.org/bot{tg_token}/sendPhoto"
                payload = {
                    "chat_id": tg_chat_id,
                    "photo": thumb,
                    "caption": msg,
                    "parse_mode": "HTML"
                }
            else:
                tg_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
                payload = {
                    "chat_id": tg_chat_id,
                    "text": msg,
                    "parse_mode": "HTML"
                }
                
            response = requests.post(tg_url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Failed to send Telegram notification: HTTP {response.status_code} - {response.text}")
        except Exception as ex:
            logger.error(f"Error sending Telegram notification: {str(ex)}")

    # 3. Slack Notification
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if slack_webhook:
        try:
            payload = {
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"🚨 *DEAL ALERT* 🚨\n*<{url}|{title}>*\n*Price:* {price:.2f} € | *Avg:* {avg_price:.2f} € | *Savings:* {savings:.2f} € (*{discount_pct}% off*)"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Location:* {loc or 'Unknown'}"},
                            {"type": "mrkdwn", "text": f"*Seller Rating:* {rating_str}"},
                            {"type": "mrkdwn", "text": f"*Keyword:* `{keyword}`"}
                        ]
                    }
                ]
            }
            if thumb:
                payload["blocks"].append({
                    "type": "image",
                    "image_url": thumb,
                    "alt_text": title
                })
                
            response = requests.post(slack_webhook, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Failed to send Slack notification: HTTP {response.status_code}")
        except Exception as ex:
            logger.error(f"Error sending Slack notification: {str(ex)}")
