-- Migration 008: Separate Advanced Stats into 4 Tables
-- Created: 2025-10-23
-- Purpose: Replace single advanced_stats table with 4 separate tables
-- Reason: INSERT OR REPLACE was destroying data across file types

-- Drop old combined table
DROP TABLE IF EXISTS advanced_stats;

-- ============================================================================
-- PASS STATS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS pass_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT NOT NULL,
    team TEXT NOT NULL,
    position TEXT NOT NULL,
    week INTEGER NOT NULL,
    
    -- Core passing stats
    cpoe REAL,                  -- Completion % Over Expected
    adot REAL,                  -- Average Depth of Target
    deep_throw_pct REAL,        -- Deep Throw %
    
    -- Additional metrics (flexible for different file versions)
    att INTEGER,                -- Attempts
    cmp INTEGER,                -- Completions
    cmp_pct REAL,              -- Completion %
    yds INTEGER,               -- Yards
    ypa REAL,                  -- Yards Per Attempt
    td INTEGER,                -- Touchdowns
    int INTEGER,               -- Interceptions
    rate REAL,                 -- Passer Rating
    sack INTEGER,              -- Sacks
    sack_pct REAL,             -- Sack %
    any_a REAL,                -- Adjusted Net Yards Per Attempt
    read1_pct REAL,            -- 1st Read %
    acc_pct REAL,              -- Accuracy %
    press_pct REAL,            -- Pressure %
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- One record per player per week
    UNIQUE(player_name, team, position, week)
);

CREATE INDEX IF NOT EXISTS idx_pass_stats_week ON pass_stats(week);
CREATE INDEX IF NOT EXISTS idx_pass_stats_player_week ON pass_stats(player_name, week);

-- ============================================================================
-- RUSH STATS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS rush_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT NOT NULL,
    team TEXT NOT NULL,
    position TEXT NOT NULL,
    week INTEGER NOT NULL,
    
    -- Core rushing stats
    yaco_att REAL,              -- Yards After Contact per Attempt
    success_rate REAL,          -- Success Rate %
    mtf_att REAL,               -- Missed Tackles Forced per Attempt
    
    -- Additional metrics
    att INTEGER,                -- Attempts
    yds INTEGER,               -- Yards
    ypc REAL,                  -- Yards Per Carry
    td INTEGER,                -- Touchdowns
    fum INTEGER,               -- Fumbles
    first_downs INTEGER,       -- 1st Downs
    stuff_pct REAL,            -- Stuff %
    mtf INTEGER,               -- Missed Tackles Forced
    yaco INTEGER,              -- Yards After Contact
    yaco_pct REAL,             -- YACO %
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(player_name, team, position, week)
);

CREATE INDEX IF NOT EXISTS idx_rush_stats_week ON rush_stats(week);
CREATE INDEX IF NOT EXISTS idx_rush_stats_player_week ON rush_stats(player_name, week);

-- ============================================================================
-- RECEIVING STATS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS receiving_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT NOT NULL,
    team TEXT NOT NULL,
    position TEXT NOT NULL,
    week INTEGER NOT NULL,
    
    -- Core receiving stats
    tprr REAL,                  -- Targets Per Route Run
    yprr REAL,                  -- Yards Per Route Run
    rte_pct REAL,               -- Route Participation %
    
    -- Additional metrics
    rte INTEGER,                -- Routes
    tgt INTEGER,                -- Targets
    tgt_pct REAL,              -- Target %
    rec INTEGER,                -- Receptions
    cr_pct REAL,               -- Catch Rate %
    yds INTEGER,               -- Yards
    ypr REAL,                  -- Yards Per Reception
    yac INTEGER,               -- Yards After Catch
    yac_rec REAL,              -- YAC per Reception
    td INTEGER,                -- Touchdowns
    read1_pct REAL,            -- 1st Read %
    mtf INTEGER,               -- Missed Tackles Forced
    mtf_rec REAL,              -- MTF per Reception
    first_downs INTEGER,       -- 1st Downs
    drops INTEGER,             -- Drops (renamed from 'drop' - SQL reserved word)
    drop_pct REAL,             -- Drop %
    adot REAL,                 -- Average Depth of Target
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(player_name, team, position, week)
);

CREATE INDEX IF NOT EXISTS idx_receiving_stats_week ON receiving_stats(week);
CREATE INDEX IF NOT EXISTS idx_receiving_stats_player_week ON receiving_stats(player_name, week);

-- ============================================================================
-- SNAP STATS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS snap_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT NOT NULL,
    team TEXT NOT NULL,
    position TEXT NOT NULL,
    week INTEGER NOT NULL,
    
    -- Core snap stats (flexible for different file formats)
    snaps INTEGER,              -- Total Snaps
    snap_pct REAL,              -- Snap %
    
    -- Week 7 format columns
    tm_snaps INTEGER,           -- Team Snaps
    off_snaps INTEGER,          -- Offensive Snaps
    off_snap_pct REAL,          -- Offensive Snap %
    def_snaps INTEGER,          -- Defensive Snaps
    def_snap_pct REAL,          -- Defensive Snap %
    st_snaps INTEGER,           -- Special Teams Snaps
    st_snap_pct REAL,           -- Special Teams Snap %
    
    -- Week 8 format columns
    snaps_per_gp REAL,          -- Snaps per Game Played
    rush_per_snap REAL,         -- Rush per Snap
    rush_share REAL,            -- Rush Share
    tgt_per_snap REAL,          -- Target per Snap
    tgt_share REAL,             -- Target Share
    touch_per_snap REAL,        -- Touch per Snap
    util_per_snap REAL,         -- Utilization per Snap
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(player_name, team, position, week)
);

CREATE INDEX IF NOT EXISTS idx_snap_stats_week ON snap_stats(week);
CREATE INDEX IF NOT EXISTS idx_snap_stats_player_week ON snap_stats(player_name, week);

-- ============================================================================
-- TRIGGERS FOR TIMESTAMP UPDATES
-- ============================================================================

CREATE TRIGGER IF NOT EXISTS update_pass_stats_timestamp 
AFTER UPDATE ON pass_stats
BEGIN
    UPDATE pass_stats 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_rush_stats_timestamp 
AFTER UPDATE ON rush_stats
BEGIN
    UPDATE rush_stats 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_receiving_stats_timestamp 
AFTER UPDATE ON receiving_stats
BEGIN
    UPDATE receiving_stats 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_snap_stats_timestamp 
AFTER UPDATE ON snap_stats
BEGIN
    UPDATE snap_stats 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;

