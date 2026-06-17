-- Schema for Kleinanzeigen Market Activity Tracker

-- 1. Categories table
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    category_code VARCHAR(50) UNIQUE NOT NULL,
    category_name VARCHAR(100) NOT NULL,
    category_url TEXT NOT NULL
);

-- 2. Category snapshots table
CREATE TABLE IF NOT EXISTS category_snapshots (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    total_listings INTEGER NOT NULL,
    avg_price_sample NUMERIC(10, 2),
    min_price_sample NUMERIC(10, 2),
    max_price_sample NUMERIC(10, 2),
    sample_size INTEGER NOT NULL
);

-- Index for category snapshots query performance
CREATE INDEX IF NOT EXISTS idx_cat_snapshots_cat_scraped ON category_snapshots(category_id, scraped_at DESC);

-- 3. Listings table (for tracking repeated titles over time)
CREATE TABLE IF NOT EXISTS listings (
    listing_id VARCHAR(50) PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    price NUMERIC(10, 2),
    location VARCHAR(150),
    listing_url TEXT NOT NULL,
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'active' NOT NULL,
    last_position INTEGER,
    is_topad BOOLEAN DEFAULT FALSE NOT NULL,
    reposted_as_id VARCHAR(50) REFERENCES listings(listing_id) ON DELETE SET NULL,
    thumbnail_url TEXT
);

-- Index for repeated titles search
CREATE INDEX IF NOT EXISTS idx_listings_title ON listings(title);

-- 4. Search keywords table
CREATE TABLE IF NOT EXISTS search_keywords (
    id SERIAL PRIMARY KEY,
    keyword VARCHAR(100) UNIQUE NOT NULL,
    active BOOLEAN DEFAULT TRUE NOT NULL
);

-- 5. Search snapshots table
CREATE TABLE IF NOT EXISTS search_snapshots (
    id SERIAL PRIMARY KEY,
    keyword_id INTEGER NOT NULL REFERENCES search_keywords(id) ON DELETE CASCADE,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    result_count INTEGER NOT NULL,
    avg_price_sample NUMERIC(10, 2)
);

-- Index for search snapshots query performance
CREATE INDEX IF NOT EXISTS idx_search_snapshots_kw_scraped ON search_snapshots(keyword_id, scraped_at DESC);

-- 6. Scrape runs table
CREATE TABLE IF NOT EXISTS scrape_runs (
    id SERIAL PRIMARY KEY,
    run_type VARCHAR(50) NOT NULL, -- 'categories' or 'keywords'
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    finished_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL, -- 'success', 'partial', 'failed'
    items_processed INTEGER DEFAULT 0 NOT NULL,
    error_message TEXT
);


-- =========================================================================
-- Seed Data
-- =========================================================================

-- Seed Categories
INSERT INTO categories (category_code, category_name, category_url) VALUES
('c161', 'Electronics', 'https://www.kleinanzeigen.de/s-elektronik/c161'),
('c80', 'Furniture & House', 'https://www.kleinanzeigen.de/s-haus-garten/c80'),
('c153', 'Fashion & Beauty', 'https://www.kleinanzeigen.de/s-kleidung-kosmetik/c153'),
('c217', 'Bicycles & Accessories', 'https://www.kleinanzeigen.de/s-fahrraeder/c217'),
('c23', 'Toys', 'https://www.kleinanzeigen.de/s-spielzeug/c23'),
('c73', 'Books, Movies & Music', 'https://www.kleinanzeigen.de/s-musik-filme-buecher/c73'),
('c17', 'Baby & Child', 'https://www.kleinanzeigen.de/s-familie-kind-baby/c17'),
('c74', 'Musical Instruments', 'https://www.kleinanzeigen.de/s-musikinstrumente/c74'),
('c185', 'Sports & Leisure', 'https://www.kleinanzeigen.de/s-freizeit-hobby-nachbarschaft/c185'),
('c223', 'Auto Parts & Tires', 'https://www.kleinanzeigen.de/s-autoteile-reifen/c223'),
('c210', 'Pets', 'https://www.kleinanzeigen.de/s-haustiere/c210'),
('c195', 'Real Estate', 'https://www.kleinanzeigen.de/s-immobilien/c195'),
('c216', 'Cars', 'https://www.kleinanzeigen.de/s-autos/c216'),
('c225', 'Services', 'https://www.kleinanzeigen.de/s-dienstleistungen/c225'),
('c231', 'Tickets', 'https://www.kleinanzeigen.de/s-eintrittskarten-tickets/c231'),
('c268', 'Lessons & Courses', 'https://www.kleinanzeigen.de/s-unterricht-kurse/c268'),
('c192', 'Free & Swap', 'https://www.kleinanzeigen.de/s-zu-verschenken-tauschen/c192'),
('c102', 'Jobs', 'https://www.kleinanzeigen.de/s-jobs/c102'),
('c228', 'Beauty & Health', 'https://www.kleinanzeigen.de/s-beauty-gesundheit/c228'),
('c282', 'Caravans & Motorhomes', 'https://www.kleinanzeigen.de/s-wohnwagen-mobile/c282')
ON CONFLICT (category_code) DO UPDATE 
SET category_name = EXCLUDED.category_name, category_url = EXCLUDED.category_url;

-- Seed Search Keywords
INSERT INTO search_keywords (keyword, active) VALUES
    -- Wearables & Smart Tech
    ('apple watch', true),
    ('galaxy watch', true),
    ('garmin', true),
    ('huawei', true),
    ('airpods', true),
    ('jbl', true),
    
    -- Tech & Gadgets
    ('iphone', true),
    ('macbook', true),
    ('ipad', true),
    ('playstation', true),
    ('playstation 5', true),
    ('nintendo switch', true),
    ('gameboy', true),
    ('dron', true),
    ('dji', true),
    ('steam deck', true),
    
    -- Household & Electronics (German popular brands)
    ('staubsauger', true),
    ('waschmaschine', true),
    ('kühlschrank', true),
    ('Bosch', true),
    ('Miele', true),
    ('Siemens', true),
    ('Braun', true),
    ('ikea', true),
    ('sofa', true),
    
    -- Fashion, Shoes & Brands
    ('nike', true),
    ('adidas', true),
    ('puma', true),
    ('jordan', true),
    ('air force 1', true),
    ('samba', true),
    ('gazelle', true),
    ('timberland', true),
    ('schuhe', true),
    ('H&M', true),
    ('Zara', true),
    ('vintage', true),
    ('herren', true),
    ('frau', true),
    ('uhr', true),
    
    -- Teenager Trends & Streetwear
    ('supreme', true),
    ('yeezy', true),
    ('stussy', true),
    ('carhartt', true),
    ('crocs', true),
    ('pokemon', true),
    ('anime', true),
    ('manga', true),
    ('funko pop', true),
    
    -- Mobility, Outdoor & Sports
    ('fahrrad', true),
    ('trekkingrad', true),
    ('rennrad', true),
    ('snowboard', true),
    ('zelt', true),
    ('schlafsack', true),
    ('baby', true),
    
    -- Gaming & Collectibles
    ('lego', true),
    ('fifa', true),
    ('rolex', true)
ON CONFLICT (keyword) DO NOTHING;


-- =========================================================================
-- SQL Views for Reporting
-- =========================================================================

-- 1. Latest snapshot per category
CREATE OR REPLACE VIEW v_latest_category_snapshots AS
WITH ranked_snapshots AS (
    SELECT 
        cs.*,
        ROW_NUMBER() OVER (PARTITION BY cs.category_id ORDER BY cs.scraped_at DESC) as rn
    FROM category_snapshots cs
)
SELECT 
    c.id AS category_id,
    c.category_name,
    c.category_code,
    c.category_url,
    rs.scraped_at,
    rs.total_listings,
    rs.avg_price_sample,
    rs.min_price_sample,
    rs.max_price_sample,
    rs.sample_size
FROM categories c
LEFT JOIN ranked_snapshots rs ON c.id = rs.category_id AND rs.rn = 1;

-- 2. Category trends over time
CREATE OR REPLACE VIEW v_category_trends AS
SELECT 
    cs.id AS snapshot_id,
    c.id AS category_id,
    c.category_name,
    c.category_code,
    cs.scraped_at,
    cs.total_listings,
    cs.avg_price_sample,
    cs.min_price_sample,
    cs.max_price_sample,
    cs.sample_size
FROM category_snapshots cs
JOIN categories c ON cs.category_id = c.id
ORDER BY cs.scraped_at ASC;

-- 3. Latest snapshot per keyword
CREATE OR REPLACE VIEW v_latest_keyword_snapshots AS
WITH ranked_snapshots AS (
    SELECT 
        ss.*,
        ROW_NUMBER() OVER (PARTITION BY ss.keyword_id ORDER BY ss.scraped_at DESC) as rn
    FROM search_snapshots ss
)
SELECT 
    k.id AS keyword_id,
    k.keyword,
    k.active,
    rs.scraped_at,
    rs.result_count,
    rs.avg_price_sample
FROM search_keywords k
LEFT JOIN ranked_snapshots rs ON k.id = rs.keyword_id AND rs.rn = 1;

-- 4. Keyword trends over time
CREATE OR REPLACE VIEW v_keyword_trends AS
SELECT 
    ss.id AS snapshot_id,
    k.id AS keyword_id,
    k.keyword,
    ss.scraped_at,
    ss.result_count,
    ss.avg_price_sample
FROM search_snapshots ss
JOIN search_keywords k ON ss.keyword_id = k.id
ORDER BY ss.scraped_at ASC;

-- 5. Top repeated listing titles (Proxy for popular items/demand)
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

-- 6. Scrape job health
CREATE OR REPLACE VIEW v_scrape_job_health AS
SELECT 
    id AS run_id,
    run_type,
    started_at,
    finished_at,
    (finished_at - started_at) AS duration,
    status,
    items_processed,
    error_message
FROM scrape_runs
ORDER BY started_at DESC;
