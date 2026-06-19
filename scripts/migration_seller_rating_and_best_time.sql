-- Migration to add seller_rating column, alter VARCHAR columns to TEXT, and create/update views in CockroachDB

-- 1. Drop dependent views first to allow altering column types
DROP VIEW IF EXISTS v_top_repeated_listing_titles CASCADE;
DROP VIEW IF EXISTS v_sold_listings_analysis CASCADE;

-- 2. Alter columns to TEXT type to avoid VARCHAR(255) value too long errors
ALTER TABLE listings ALTER COLUMN listing_url TYPE TEXT;
ALTER TABLE listings ALTER COLUMN title TYPE TEXT;
ALTER TABLE listings ALTER COLUMN thumbnail_url TYPE TEXT;
ALTER TABLE listings ALTER COLUMN location TYPE TEXT;

-- 3. Add column to track seller ratings on listings if it doesn't exist
ALTER TABLE listings ADD COLUMN IF NOT EXISTS seller_rating VARCHAR(50);

-- 4. Recreate view: v_top_repeated_listing_titles
CREATE OR REPLACE VIEW v_top_repeated_listing_titles AS
SELECT 
    c.category_name,
    LOWER(TRIM(l.title)) as clean_title,
    COUNT(*) as appearance_count,
    MIN(l.price) as min_price,
    MAX(l.price) as max_price,
    ROUND(AVG(l.price), 2) as avg_price,
    MIN(l.first_seen_at) as earliest_seen,
    MAX(l.last_seen_at) as latest_seen
FROM listings l
JOIN categories c ON l.category_id = c.id
GROUP BY c.category_name, clean_title
HAVING COUNT(*) > 1
ORDER BY appearance_count DESC;

-- 5. Recreate view: v_sold_listings_analysis
CREATE OR REPLACE VIEW v_sold_listings_analysis AS
SELECT 
    listing_id,
    category_id,
    title,
    price,
    location,
    first_seen_at,
    last_seen_at,
    -- Calculate active duration
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

-- 6. Create or replace view for analyzing average time-to-sell by hour and day of week
CREATE OR REPLACE VIEW v_best_time_to_post_analysis AS
SELECT 
    EXTRACT(DOW FROM first_seen_at) AS post_day_of_week,
    CASE EXTRACT(DOW FROM first_seen_at)
        WHEN 0 THEN 'Sunday'
        WHEN 1 THEN 'Monday'
        WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday'
        WHEN 4 THEN 'Thursday'
        WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday'
    END AS post_day_name,
    EXTRACT(HOUR FROM first_seen_at) AS post_hour,
    COUNT(*) AS total_sold_listings,
    ROUND(AVG(EXTRACT(EPOCH FROM (last_seen_at - first_seen_at)) / 3600.0)::NUMERIC, 2) AS avg_hours_to_sell,
    ROUND(MIN(EXTRACT(EPOCH FROM (last_seen_at - first_seen_at)) / 3600.0)::NUMERIC, 2) AS min_hours_to_sell,
    ROUND(MAX(EXTRACT(EPOCH FROM (last_seen_at - first_seen_at)) / 3600.0)::NUMERIC, 2) AS max_hours_to_sell
FROM listings
WHERE status = 'sold' AND last_seen_at > first_seen_at
GROUP BY post_day_of_week, post_hour
ORDER BY avg_hours_to_sell ASC;
