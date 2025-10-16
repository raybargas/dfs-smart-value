-- Migration 004: Historical Intelligence System
-- Date: 2024-10-16
-- Description: Add tables for historical data persistence, backtesting, and injury pattern learning

-- ============================================================================
-- 1. SLATES TABLE
-- ============================================================================
-- Multi-site, multi-contest type slate metadata

CREATE TABLE IF NOT EXISTS slates (
    slate_id TEXT PRIMARY KEY,           -- e.g., "2024-W6-DK-CLASSIC"
    week INTEGER NOT NULL,
    season INTEGER NOT NULL,
    site TEXT NOT NULL,                  -- 'DraftKings', 'FanDuel'
    contest_type TEXT NOT NULL,          -- 'Classic', 'Showdown', 'Thanksgiving'
    slate_date DATE NOT NULL,
    games_in_slate TEXT,                 -- JSON array of game IDs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_slates_week_season ON slates(week, season);
CREATE INDEX IF NOT EXISTS idx_slates_site ON slates(site);
CREATE INDEX IF NOT EXISTS idx_slates_date ON slates(slate_date);

-- ============================================================================
-- 2. HISTORICAL PLAYER POOL
-- ============================================================================
-- Complete weekly snapshot for perfect replay

CREATE TABLE IF NOT EXISTS historical_player_pool (
    slate_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    position TEXT NOT NULL,
    team TEXT NOT NULL,
    opponent TEXT NOT NULL,
    salary INTEGER NOT NULL,
    projection REAL NOT NULL,
    ceiling REAL,
    ownership REAL,
    actual_points REAL,                   -- Fetched Monday from boxscore
    smart_value REAL,
    smart_value_profile TEXT,             -- 'GPP_Balanced_v3.0'
    projection_source TEXT,               -- 'rotogrinders_v1', 'manual'
    ownership_source TEXT,                -- 'fantasylabs', 'manual'
    data_source TEXT NOT NULL,            -- 'mysportsfeeds_dfs', 'manual_upload'
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (slate_id, player_id),
    FOREIGN KEY (slate_id) REFERENCES slates(slate_id)
);

CREATE INDEX IF NOT EXISTS idx_hpp_player_name ON historical_player_pool(player_name);
CREATE INDEX IF NOT EXISTS idx_hpp_position ON historical_player_pool(position);
CREATE INDEX IF NOT EXISTS idx_hpp_actual_points ON historical_player_pool(actual_points);
CREATE INDEX IF NOT EXISTS idx_hpp_smart_value ON historical_player_pool(smart_value DESC);

-- ============================================================================
-- 3. SMART VALUE PROFILES HISTORY
-- ============================================================================
-- Profile versioning and performance tracking

CREATE TABLE IF NOT EXISTS smart_value_profiles_history (
    profile_id TEXT PRIMARY KEY,          -- 'GPP_Balanced_v3.0_W10'
    profile_name TEXT NOT NULL,           -- 'GPP_Balanced'
    version TEXT NOT NULL,                -- 'v3.0'
    week_used INTEGER NOT NULL,
    season INTEGER NOT NULL,
    weights JSON NOT NULL,                -- Full weight configuration
    performance_score REAL,               -- Avg % of optimal
    avg_lineup_score REAL,                -- Avg actual points
    top_lineup_score REAL,                -- Best lineup actual points
    lineups_generated INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_svph_profile_name ON smart_value_profiles_history(profile_name);
CREATE INDEX IF NOT EXISTS idx_svph_week ON smart_value_profiles_history(week, season);
CREATE INDEX IF NOT EXISTS idx_svph_performance ON smart_value_profiles_history(performance_score DESC);

-- ============================================================================
-- 4. INJURY PATTERNS
-- ============================================================================
-- Learned injury intelligence

CREATE TABLE IF NOT EXISTS injury_patterns (
    pattern_id TEXT PRIMARY KEY,          -- 'ankle_sprain_WR_LP-FP'
    injury_type TEXT NOT NULL,            -- 'ankle_sprain', 'hamstring_strain'
    position TEXT NOT NULL,               -- Position-specific impacts
    practice_status TEXT,                 -- 'DNP/DNP/LP', 'LP/FP/FP', etc.
    games_played INTEGER DEFAULT 0,       -- How many times played through
    games_missed INTEGER DEFAULT 0,       -- How many times sat out
    total_projection_diff REAL DEFAULT 0, -- Sum of (actual - projection)
    avg_points_impact REAL,               -- Calculated: total_diff / games_played
    sample_size INTEGER DEFAULT 0,        -- games_played + games_missed
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ip_injury_position ON injury_patterns(injury_type, position);
CREATE INDEX IF NOT EXISTS idx_ip_sample_size ON injury_patterns(sample_size DESC);
CREATE INDEX IF NOT EXISTS idx_ip_practice_status ON injury_patterns(practice_status);

-- ============================================================================
-- 5. BACKTEST RESULTS
-- ============================================================================
-- Backtest run artifacts

CREATE TABLE IF NOT EXISTS backtest_results (
    backtest_id TEXT PRIMARY KEY,         -- UUID
    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    weeks_tested TEXT NOT NULL,           -- JSON array [10, 11, 12]
    profile_name TEXT NOT NULL,
    profile_weights JSON NOT NULL,
    
    -- Results per week (JSON objects)
    week_results JSON NOT NULL,           -- [{week: 10, avg: 142, top: 156, optimal: 165}, ...]
    
    -- Summary metrics
    overall_avg_score REAL,
    overall_top_score REAL,
    overall_optimal_score REAL,
    avg_gap_from_optimal REAL,            -- Avg % below perfect lineup
    
    notes TEXT                             -- User notes
);

CREATE INDEX IF NOT EXISTS idx_br_profile ON backtest_results(profile_name);
CREATE INDEX IF NOT EXISTS idx_br_timestamp ON backtest_results(run_timestamp DESC);

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- Total tables added: 5
-- Total indexes added: 12
--
-- Note: Enhancement to injury_reports table (data_fetched_at column) will be
-- handled separately if needed in future migration or directly in code.

