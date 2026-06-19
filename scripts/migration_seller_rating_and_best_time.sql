-- Migration to add seller_rating column and create best time to post analysis view in CockroachDB

-- 1. Add column to track seller ratings on listings if it doesn't exist
ALTER TABLE listings ADD COLUMN IF NOT EXISTS seller_rating VARCHAR(50);

-- 2. Create or replace view for analyzing average time-to-sell by hour and day of week
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
