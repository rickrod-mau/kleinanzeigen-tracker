-- Migration SQL script to add lifecycle tracking columns to listings table
-- Execute this on your CockroachDB database instance to apply changes without dropping existing data.

ALTER TABLE listings ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active' NOT NULL;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS last_position INTEGER;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS is_topad BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS reposted_as_id VARCHAR(50) REFERENCES listings(listing_id) ON DELETE SET NULL;
ALTER TABLE listings ADD COLUMN IF NOT EXISTS thumbnail_url TEXT;
