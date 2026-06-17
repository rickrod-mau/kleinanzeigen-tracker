import os
import time
import random
import logging
import requests
import psycopg2

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
    - Exponential backoff retry logic for 429 (Rate Limited) and 5xx errors.
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
        try:
            logger.info(f"Fetching: {url} (Attempt {attempt}/{max_retries})")
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 200:
                return response
            
            elif response.status_code == 429:
                # Rate limit / Too many requests
                backoff = base_backoff * (2 ** (attempt - 1)) + random.uniform(2.0, 5.0)
                logger.warning(f"HTTP 429 (Too Many Requests) received. Backing off for {backoff:.2f} seconds.")
                time.sleep(backoff)
                
            elif response.status_code >= 500:
                # Server error
                backoff = base_backoff * (2 ** (attempt - 1)) + random.uniform(2.0, 5.0)
                logger.warning(f"HTTP {response.status_code} received. Retrying in {backoff:.2f} seconds.")
                time.sleep(backoff)
                
            elif response.status_code == 403:
                logger.error("HTTP 403 Forbidden. The site's anti-scraping systems (e.g. Akamai/DataDome) might be blocking the request.")
                response.raise_for_status()
                
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
