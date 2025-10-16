-- Migration 006: Make opponent column nullable in historical_player_pool
-- 
-- Issue: Some players from MySportsFeeds API don't have opponent data
-- The opponent field should be optional, not required
-- 
-- Date: 2025-10-16

-- SQLite doesn't support ALTER COLUMN, so we need to recreate the table
PRAGMA foreign_keys=OFF;

-- Create new table with opponent as nullable
CREATE TABLE historical_player_pool_new (
    slate_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    position TEXT NOT NULL,
    team TEXT NOT NULL,
    opponent TEXT,                            -- NOW NULLABLE
    salary INTEGER NOT NULL,
    projection REAL NOT NULL,
    ceiling REAL,
    ownership REAL,
    actual_points REAL,
    smart_value REAL,
    smart_value_profile TEXT,
    projection_source TEXT,
    ownership_source TEXT,
    data_source TEXT NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (slate_id, player_id),
    FOREIGN KEY (slate_id) REFERENCES slates(slate_id)
);

-- Copy existing data (if any)
INSERT INTO historical_player_pool_new 
SELECT * FROM historical_player_pool;

-- Drop old table
DROP TABLE historical_player_pool;

-- Rename new table
ALTER TABLE historical_player_pool_new RENAME TO historical_player_pool;

-- Recreate indexes
CREATE INDEX IF NOT EXISTS idx_hpp_player_name ON historical_player_pool(player_name);
CREATE INDEX IF NOT EXISTS idx_hpp_position ON historical_player_pool(position);
CREATE INDEX IF NOT EXISTS idx_hpp_actual_points ON historical_player_pool(actual_points);
CREATE INDEX IF NOT EXISTS idx_hpp_smart_value ON historical_player_pool(smart_value DESC);

PRAGMA foreign_keys=ON;

