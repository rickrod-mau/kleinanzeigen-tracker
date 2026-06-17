-- SQL migration to clean and update your search keywords on CockroachDB
-- Run this in your CockroachDB SQL Console to update the tracking keywords.

DELETE FROM search_keywords;

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
    ('rolex', true);
