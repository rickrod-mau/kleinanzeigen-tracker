import sys
import re
import traceback
import urllib.parse
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from helper import get_db_connection, make_request, logger

def parse_price(price_str):
    """
    Parses Kleinanzeigen price strings into floats.
    Handles 'Zu verschenken', 'Tauschen', 'VB', and standard prices like '150 €' or '1.250,50 € VB'.
    """
    if not price_str:
        return None
    
    price_str_lower = price_str.lower().strip()
    
    if "verschenken" in price_str_lower:
        return 0.00
    
    if "tauschen" in price_str_lower or "tausche" in price_str_lower:
        return None
        
    if price_str_lower == "vb":
        return None

    match = re.search(r'([0-9\.,]+)', price_str)
    if not match:
        return None
        
    num_str = match.group(1)
    
    if ',' in num_str:
        clean_num = num_str.replace('.', '').replace(',', '.')
    else:
        if '.' in num_str:
            parts = num_str.split('.')
            if len(parts[-1]) == 3:
                clean_num = num_str.replace('.', '')
            else:
                clean_num = num_str
        else:
            clean_num = num_str
            
    try:
        return float(clean_num)
    except ValueError:
        return None

def parse_total_count(soup):
    """
    Extracts the total listing count from the keyword search results HTML page.
    """
    selectors = [
        'span.breadcrumb-title-count',
        'span.ad-count',
        'h1.breadcrumb-title-count',
        '.margin-bottom-five h1',
        '.margin-bottom-five span',
        'span.counter-info',
        'h1'
    ]
    
    for sel in selectors:
        elements = soup.select(sel)
        for el in elements:
            text = el.text.strip()
            
            # Match 'von X'
            match_von = re.search(r'von\s+([0-9\.\s]+)', text, re.IGNORECASE)
            if match_von:
                num_str = match_von.group(1).replace('.', '').replace(' ', '')
                try:
                    return int(num_str)
                except ValueError:
                    pass
            
            # Match 'X Ergebnisse' or 'X Anzeigen'
            match_ergebnisse = re.search(r'([0-9\.\s]+)\s+(?:Ergebnisse|Anzeigen)', text, re.IGNORECASE)
            if match_ergebnisse:
                num_str = match_ergebnisse.group(1).replace('.', '').replace(' ', '')
                try:
                    return int(num_str)
                except ValueError:
                    pass
            
            # Fallback if class specifically indicates count
            if 'breadcrumb-title-count' in sel or 'ad-count' in sel:
                num_str = re.sub(r'[^\d]', '', text)
                if num_str:
                    try:
                        return int(num_str)
                    except ValueError:
                        pass
                        
    # Page text search fallback
    body_text = soup.get_text()
    match = re.search(r'([0-9\.\s]+)\s+(?:Ergebnisse|Anzeigen)', body_text, re.IGNORECASE)
    if match:
        num_str = match.group(1).replace('.', '').replace(' ', '')
        try:
            return int(num_str)
        except ValueError:
            pass
            
    return 0

def scrape_keyword(keyword):
    """
    Fetches search results for a keyword and extracts total count and average price.
    """
    quoted_keyword = urllib.parse.quote_plus(keyword)
    search_url = f"https://www.kleinanzeigen.de/s-suchanfrage.html?keywords={quoted_keyword}"
    
    logger.info(f"Scraping keyword '{keyword}' using URL: {search_url}")
    response = make_request(search_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    total_results = parse_total_count(soup)
    logger.info(f"Extracted total search results: {total_results}")
    
    # Locate listing containers for price sampling
    listings_elems = soup.select('article.aditem') or soup.select('li.aditem') or soup.find_all('article', class_='aditem')
    logger.info(f"Found {len(listings_elems)} listing elements on the first page for price sampling.")
    
    prices_list = []
    for idx, item in enumerate(listings_elems, 1):
        try:
            price_el = (
                item.select_one('.aditem-main--middle--price-shipping--price') or 
                item.select_one('.aditem-main--middle--price') or 
                item.select_one('.aditem-detail-price')
            )
            if price_el:
                price_str = price_el.text.strip()
                price = parse_price(price_str)
                if price is not None:
                    prices_list.append(price)
        except Exception as e:
            logger.warning(f"Error parsing price for item {idx}: {str(e)}")
            continue

    avg_price = None
    if prices_list:
        avg_price = round(sum(prices_list) / len(prices_list), 2)
        
    logger.info(f"Keyword '{keyword}' Stats -> Count: {total_results}, Avg Price: {avg_price} (sampled from {len(prices_list)} items)")
    return {
        'result_count': total_results,
        'avg_price_sample': avg_price
    }

def main():
    start_time = datetime.now(timezone.utc)
    status = "success"
    items_processed = 0
    error_msg = None
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Log start of scrape run
        cur.execute(
            """
            INSERT INTO scrape_runs (run_type, started_at, status)
            VALUES (%s, %s, %s) RETURNING id;
            """,
            ('keywords', start_time, 'running')
        )
        run_id = cur.fetchone()[0]
        conn.commit()
        
        # Get active keywords to scrape
        cur.execute("SELECT id, keyword FROM search_keywords WHERE active = true ORDER BY id;")
        keywords = cur.fetchall()
        
        success_count = 0
        total_keywords = len(keywords)
        
        for kw_id, keyword in keywords:
            try:
                res = scrape_keyword(keyword)
                
                # Insert search snapshot
                cur.execute(
                    """
                    INSERT INTO search_snapshots (
                        keyword_id, scraped_at, result_count, avg_price_sample
                    ) VALUES (%s, %s, %s, %s);
                    """,
                    (
                        kw_id, datetime.now(timezone.utc), res['result_count'], res['avg_price_sample']
                    )
                )
                
                conn.commit()
                success_count += 1
                items_processed += 1
                logger.info(f"Successfully processed keyword: {keyword}")
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error scraping keyword '{keyword}': {str(e)}")
                current_err = f"Keyword '{keyword}': {str(e)}"
                error_msg = f"{error_msg}\n{current_err}" if error_msg else current_err
                status = "partial"
                
        # Finalize run status
        if success_count == 0:
            status = "failed"
        elif success_count < total_keywords:
            status = "partial"
        else:
            status = "success"
            
        end_time = datetime.now(timezone.utc)
        cur.execute(
            """
            UPDATE scrape_runs
            SET finished_at = %s, status = %s, items_processed = %s, error_message = %s
            WHERE id = %s;
            """,
            (end_time, status, items_processed, error_msg, run_id)
        )
        conn.commit()
        logger.info(f"Finished scrape run. Status: {status}, processed: {items_processed}/{total_keywords}")
        
    except Exception as e:
        logger.critical(f"Critical error in keyword scraper: {str(e)}")
        traceback.print_exc()
        if conn:
            try:
                cur = conn.cursor()
                end_time = datetime.now(timezone.utc)
                cur.execute(
                    """
                    UPDATE scrape_runs
                    SET finished_at = %s, status = %s, error_message = %s
                    WHERE id = %s;
                    """,
                    (end_time, 'failed', str(e), run_id)
                )
                conn.commit()
            except Exception as inner_e:
                logger.error(f"Failed to write critical error to database: {str(inner_e)}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
