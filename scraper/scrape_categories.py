import sys
import re
import traceback
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
    
    # "Zu verschenken" (free)
    if "verschenken" in price_str_lower:
        return 0.00
    
    # "Tauschen" (swap) or "tausche"
    if "tauschen" in price_str_lower or "tausche" in price_str_lower:
        return None
        
    # VB only without numbers (rare, but possible)
    if price_str_lower == "vb":
        return None

    # Extract digits, dots, and commas
    match = re.search(r'([0-9\.,]+)', price_str)
    if not match:
        return None
        
    num_str = match.group(1)
    
    # German formatting uses "." for thousands and "," for decimals
    if ',' in num_str:
        # e.g., "1.250,50" -> "1250.50" or "12,50" -> "12.50"
        clean_num = num_str.replace('.', '').replace(',', '.')
    else:
        # e.g., "1.250" or "125"
        # If dot is present but no comma, we check if it is a thousands separator.
        # Generally on Kleinanzeigen, "1.250 €" is 1250, not 1.25.
        if '.' in num_str:
            parts = num_str.split('.')
            if len(parts[-1]) == 3:  # thousands separator
                clean_num = num_str.replace('.', '')
            else:  # decimal point (less common on German site, but possible)
                clean_num = num_str
        else:
            clean_num = num_str
            
    try:
        return float(clean_num)
    except ValueError:
        return None

def parse_total_count(soup):
    """
    Extracts the total listing count from the category HTML page using various selectors.
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
            # Try to match 'von X' e.g. "1 - 25 von 14.234"
            match_von = re.search(r'von\s+([0-9\.\s]+)', text, re.IGNORECASE)
            if match_von:
                num_str = match_von.group(1).replace('.', '').replace(' ', '')
                try:
                    return int(num_str)
                except ValueError:
                    pass
            
            # Try to match 'X Ergebnisse' or 'X Anzeigen'
            match_ergebnisse = re.search(r'([0-9\.\s]+)\s+(?:Ergebnisse|Anzeigen)', text, re.IGNORECASE)
            if match_ergebnisse:
                num_str = match_ergebnisse.group(1).replace('.', '').replace(' ', '')
                try:
                    return int(num_str)
                except ValueError:
                    pass
            
            # If the class specifically indicates count (e.g. breadcrumb-title-count)
            if 'breadcrumb-title-count' in sel or 'ad-count' in sel:
                num_str = re.sub(r'[^\d]', '', text)
                if num_str:
                    try:
                        return int(num_str)
                    except ValueError:
                        pass
                        
    # Final fallback: search the page text for 'Ergebnisse'
    body_text = soup.get_text()
    match = re.search(r'([0-9\.\s]+)\s+(?:Ergebnisse|Anzeigen)', body_text, re.IGNORECASE)
    if match:
        num_str = match.group(1).replace('.', '').replace(' ', '')
        try:
            return int(num_str)
        except ValueError:
            pass
            
    return 0

def scrape_category_page(category_name, category_url, num_pages=1):
    """
    Fetches the category page(s) and extracts listing counts and details of listings.
    Supports multi-page scraping if num_pages > 1.
    """
    total_listings = 0
    parsed_listings = []
    prices_list = []
    
    for page_num in range(1, num_pages + 1):
        if page_num == 1:
            current_url = category_url
        else:
            if '/c' in category_url:
                parts = category_url.rsplit('/', 1)
                current_url = f"{parts[0]}/seite:{page_num}/{parts[1]}"
            else:
                current_url = f"{category_url}?seite={page_num}"
                
        logger.info(f"Scraping category '{category_name}' - Page {page_num}/{num_pages} from URL: {current_url}")
        
        try:
            response = make_request(current_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Only parse the total listings count from the first page
            if page_num == 1:
                total_listings = parse_total_count(soup)
                logger.info(f"Extracted total listings count: {total_listings}")
            
            # Locate listing containers: article.aditem or li.aditem
            listings_elems = soup.select('article.aditem') or soup.select('li.aditem') or soup.find_all('article', class_='aditem')
            logger.info(f"Found {len(listings_elems)} listing elements on page {page_num}.")
            
            if not listings_elems:
                logger.info(f"No listings found on page {page_num}. Ending pagination early.")
                break
                
            for idx, item in enumerate(listings_elems, 1):
                try:
                    # 1. Listing ID (usually in data-adid attribute of container)
                    listing_id = item.get('data-adid')
                    
                    # 2. Title and URL
                    title_el = (
                        item.select_one('.aditem-main--title-line a') or 
                        item.select_one('h2 a') or 
                        item.select_one('.text-module-begin a')
                    )
                    if not title_el:
                        logger.warning(f"Could not find title element for item {idx} on page {page_num}. Skipping.")
                        continue
                        
                    title = title_el.text.strip()
                    href = title_el.get('href', '')
                    
                    # Prepend domain to relative URLs
                    listing_url = href
                    if href and not href.startswith('http'):
                        listing_url = f"https://www.kleinanzeigen.de{href}"
                        
                    # If listing ID not found in data-adid, extract from URL
                    if not listing_id and href:
                        id_match = re.search(r'/s-anzeige/.*/(\d+)-', href)
                        if id_match:
                            listing_id = id_match.group(1)
                    
                    if not listing_id:
                        logger.warning(f"Could not extract listing ID for item {idx} on page {page_num}. Skipping.")
                        continue
                        
                    # 3. Price
                    price_el = (
                        item.select_one('.aditem-main--middle--price-shipping--price') or 
                        item.select_one('.aditem-main--middle--price') or 
                        item.select_one('.aditem-detail-price')
                    )
                    price_str = price_el.text.strip() if price_el else None
                    price = parse_price(price_str)
                    
                    if price is not None:
                        prices_list.append(price)
                        
                    # 4. Location
                    loc_el = (
                        item.select_one('.aditem-main--bottom--left') or 
                        item.select_one('.aditem-main--bottom') or 
                        item.select_one('.aditem-details')
                    )
                    location = loc_el.text.strip() if loc_el else None
                    if location:
                        location = re.sub(r'\s+', ' ', location).strip()
                        
                    # 5. Check if it is a sponsored/top ad
                    is_topad = bool(item.select_one('.badge-topad') or 'is-topad' in item.get('class', []))
                    
                    # 6. Extract thumbnail image URL (Hack 1)
                    img_el = item.select_one('.aditem-image img') or item.select_one('img')
                    thumbnail_url = None
                    if img_el:
                        thumbnail_url = img_el.get('src') or img_el.get('data-src')
                    
                    parsed_listings.append({
                        'listing_id': listing_id,
                        'title': title,
                        'price': price,
                        'location': location,
                        'listing_url': listing_url,
                        'is_topad': is_topad,
                        'thumbnail_url': thumbnail_url
                    })
                    
                except Exception as e:
                    logger.error(f"Error parsing listing item {idx} on page {page_num}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error requesting page {page_num} for category {category_name}: {str(e)}")
            # If page 1 fails, we raise exception to mark run as failed/partial.
            # If page 2+ fails, we can just keep whatever we scraped so far.
            if page_num == 1:
                raise e
            else:
                break

    # Calculate statistics over all pages
    sample_size = len(prices_list)
    if sample_size > 0:
        avg_price = round(sum(prices_list) / sample_size, 2)
        min_price = min(prices_list)
        max_price = max(prices_list)
    else:
        avg_price = None
        min_price = None
        max_price = None
        
    return {
        'total_listings': total_listings,
        'avg_price_sample': avg_price,
        'min_price_sample': min_price,
        'max_price_sample': max_price,
        'sample_size': sample_size,
        'listings': parsed_listings
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
            ('categories', start_time, 'running')
        )
        run_id = cur.fetchone()[0]
        conn.commit()
        
        # Get active categories to scrape
        cur.execute("SELECT id, category_name, category_url FROM categories ORDER BY id;")
        categories = cur.fetchall()
        
        success_count = 0
        total_categories = len(categories)
        
        for cat_id, cat_name, cat_url in categories:
            try:
                # Scrape 20 pages for top 3 categories, otherwise scrape 5 pages
                TOP_CATEGORIES = {"Baby & Child", "Fashion & Beauty", "Furniture & House"}
                num_pages = 20 if cat_name in TOP_CATEGORIES else 5
                res = scrape_category_page(cat_name, cat_url, num_pages=num_pages)
                
                # 1. Insert category snapshot
                cur.execute(
                    """
                    INSERT INTO category_snapshots (
                        category_id, scraped_at, total_listings, 
                        avg_price_sample, min_price_sample, max_price_sample, sample_size
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        cat_id, datetime.now(timezone.utc), res['total_listings'],
                        res['avg_price_sample'], res['min_price_sample'], res['max_price_sample'], res['sample_size']
                    )
                )
                
                # Assign organic ranks to listings (excluding top ads)
                organic_rank = 0
                for listing in res['listings']:
                    if not listing['is_topad']:
                        organic_rank += 1
                        listing['last_position'] = organic_rank
                    else:
                        listing['last_position'] = None

                # 2. Upsert sampled listings
                for listing in res['listings']:
                    cur.execute(
                        """
                        INSERT INTO listings (
                            listing_id, category_id, title, price, location, listing_url, 
                            first_seen_at, last_seen_at, status, last_position, is_topad, thumbnail_url
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (listing_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            price = EXCLUDED.price,
                            location = EXCLUDED.location,
                            last_seen_at = EXCLUDED.last_seen_at,
                            status = 'active',
                            last_position = EXCLUDED.last_position,
                            is_topad = EXCLUDED.is_topad,
                            thumbnail_url = EXCLUDED.thumbnail_url;
                        """,
                        (
                            listing['listing_id'], cat_id, listing['title'], listing['price'],
                            listing['location'], listing['listing_url'], datetime.now(timezone.utc), datetime.now(timezone.utc),
                            'active', listing['last_position'], listing['is_topad'], listing['thumbnail_url']
                        )
                    )
                
                # 3. Post-scrape lifecycle analysis for this category
                # Find listings that were active before this run but missing now
                cur.execute(
                    """
                    SELECT listing_id, title, price, location, last_position, is_topad, thumbnail_url
                    FROM listings
                    WHERE category_id = %s AND status = 'active' AND last_seen_at < %s;
                    """,
                    (cat_id, start_time)
                )
                missing_listings = cur.fetchall()
                
                # Count newly added organic listings in this run (inserted at top)
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM listings
                    WHERE category_id = %s AND first_seen_at >= %s AND is_topad = FALSE;
                    """,
                    (cat_id, start_time)
                )
                new_listings_count = cur.fetchone()[0]
                
                for m_id, m_title, m_price, m_loc, m_pos, m_is_top, m_thumb in missing_listings:
                    # Filter/skip top ads from organic push analysis
                    if m_is_top:
                        cur.execute(
                            "UPDATE listings SET status = 'pushed_out' WHERE listing_id = %s;",
                            (m_id,)
                        )
                        continue
                        
                    if m_pos is None:
                        m_pos = num_pages * 25 # fallback
                        
                    # Deduplication check: check if reposted (first check image URL, then fallback to title+price+location)
                    dup = None
                    if m_thumb:
                        cur.execute(
                            """
                            SELECT listing_id 
                            FROM listings 
                            WHERE category_id = %s 
                              AND first_seen_at >= %s 
                              AND listing_id != %s 
                              AND thumbnail_url = %s
                            LIMIT 1;
                            """,
                            (cat_id, start_time, m_id, m_thumb)
                        )
                        dup = cur.fetchone()
                        
                    if not dup:
                        # Fallback to Title + Price + Location matching
                        cur.execute(
                            """
                            SELECT listing_id 
                            FROM listings 
                            WHERE category_id = %s 
                              AND first_seen_at >= %s 
                              AND listing_id != %s 
                              AND LOWER(title) = LOWER(%s) 
                              AND (price = %s OR (price IS NULL AND %s IS NULL)) 
                              AND (location = %s OR (location IS NULL AND %s IS NULL))
                            LIMIT 1;
                            """,
                            (cat_id, start_time, m_id, m_title, m_price, m_price, m_loc, m_loc)
                        )
                        dup = cur.fetchone()
                    
                    if dup:
                        dup_id = dup[0]
                        cur.execute(
                            """
                            UPDATE listings 
                            SET status = 'reposted', reposted_as_id = %s 
                            WHERE listing_id = %s;
                            """,
                            (dup_id, m_id)
                        )
                        logger.info(f"Inferred REPOST: Listing {m_id} reposted as {dup_id}")
                    else:
                        # expected position push
                        expected_pos = m_pos + new_listings_count
                        max_scraped_pos = num_pages * 25
                        
                        if expected_pos <= max_scraped_pos:
                            cur.execute(
                                "UPDATE listings SET status = 'sold' WHERE listing_id = %s;",
                                (m_id,)
                            )
                            logger.info(f"Inferred SOLD: Listing {m_id} (last pos: {m_pos}, new posts: {new_listings_count}, expected pos: {expected_pos} <= {max_scraped_pos})")
                        else:
                            cur.execute(
                                "UPDATE listings SET status = 'pushed_out' WHERE listing_id = %s;",
                                (m_id,)
                            )
                            logger.info(f"Inferred PUSHED OUT: Listing {m_id} (expected pos: {expected_pos} > {max_scraped_pos})")
                
                conn.commit()
                success_count += 1
                items_processed += 1
                logger.info(f"Successfully processed category: {cat_name}")
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Error scraping category {cat_name}: {str(e)}")
                # Append to error message
                current_err = f"Category '{cat_name}': {str(e)}"
                error_msg = f"{error_msg}\n{current_err}" if error_msg else current_err
                status = "partial"
                
        # Finalize run status
        if success_count == 0:
            status = "failed"
        elif success_count < total_categories:
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
        logger.info(f"Finished scrape run. Status: {status}, processed: {items_processed}/{total_categories}")
        
    except Exception as e:
        logger.critical(f"Critical error in scraper: {str(e)}")
        traceback.print_exc()
        if conn:
            try:
                # Try to log the failure in DB
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
