-- Migration 002: Add Narrative Intelligence & Smart Pool Selection Tables
-- Created: 2025-10-10
-- Purpose: Support smart rules engine, Vegas lines integration, injury reports, and API tracking

-- Table: vegas_lines
-- Stores Vegas odds data (spread, total, calculated ITT) from The Odds API
CREATE TABLE IF NOT EXISTS vegas_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week INTEGER NOT NULL,
    game_id TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    home_spread REAL,
    away_spread REAL,
    total REAL,
    home_itt REAL,  -- Implied Team Total: (total/2) + (spread/2)
    away_itt REAL,  -- Implied Team Total: (total/2) - (spread/2)
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CHECK(total IS NULL OR total > 0),
    CHECK(home_itt IS NULL OR home_itt > 0),
    CHECK(away_itt IS NULL OR away_itt > 0),
    UNIQUE(week, game_id)
);

-- Index for week-based queries (most common access pattern)
CREATE INDEX IF NOT EXISTS idx_vegas_week 
ON vegas_lines(week);

-- Index for team lookups (to attach ITT to players)
CREATE INDEX IF NOT EXISTS idx_vegas_home_team 
ON vegas_lines(home_team);

CREATE INDEX IF NOT EXISTS idx_vegas_away_team 
ON vegas_lines(away_team);

-- Composite index for game queries
CREATE INDEX IF NOT EXISTS idx_vegas_week_teams 
ON vegas_lines(week, home_team, away_team);


-- Table: injury_reports
-- Stores NFL injury reports from MySportsFeeds API
CREATE TABLE IF NOT EXISTS injury_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    team TEXT NOT NULL,
    position TEXT,
    injury_status TEXT CHECK(injury_status IN ('Q', 'D', 'O', 'IR', 'PUP', 'NFI', NULL)),
    practice_status TEXT CHECK(practice_status IN ('Full', 'Limited', 'DNP', NULL)),
    body_part TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(week, player_name, team)
);

-- Index for week-based queries
CREATE INDEX IF NOT EXISTS idx_injury_week 
ON injury_reports(week);

-- Index for player lookups (to show injury badges)
CREATE INDEX IF NOT EXISTS idx_injury_player 
ON injury_reports(player_name, team);

-- Index for status filtering (find all Q/D/O players)
CREATE INDEX IF NOT EXISTS idx_injury_status 
ON injury_reports(injury_status);

-- Composite index for team + week queries
CREATE INDEX IF NOT EXISTS idx_injury_team_week 
ON injury_reports(team, week);


-- Table: narrative_flags
-- Stores smart rules evaluation results (flags for each player)
CREATE TABLE IF NOT EXISTS narrative_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week INTEGER NOT NULL,
    player_name TEXT NOT NULL,
    team TEXT NOT NULL,
    position TEXT NOT NULL,
    flag_type TEXT NOT NULL CHECK(flag_type IN ('optimal', 'caution', 'warning')),
    flag_category TEXT NOT NULL CHECK(flag_category IN (
        'itt', 'salary_ceiling', 'snap_count', 'routes', 'committee', 
        'regression', 'price_floor', 'stacking', 'matchup', 'other'
    )),
    message TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('green', 'yellow', 'red')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CHECK(LENGTH(message) > 0)
);

-- Index for player + week queries (most common: get all flags for player)
CREATE INDEX IF NOT EXISTS idx_flags_player_week 
ON narrative_flags(player_name, team, week);

-- Index for week-based queries (all flags for a slate)
CREATE INDEX IF NOT EXISTS idx_flags_week 
ON narrative_flags(week);

-- Index for severity filtering (show only red flags)
CREATE INDEX IF NOT EXISTS idx_flags_severity 
ON narrative_flags(severity);

-- Index for category analysis (count ITT warnings, etc.)
CREATE INDEX IF NOT EXISTS idx_flags_category 
ON narrative_flags(flag_category);


-- Table: api_call_log
-- Tracks API calls for rate limit management and debugging
CREATE TABLE IF NOT EXISTS api_call_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_name TEXT NOT NULL CHECK(api_name IN ('the_odds_api', 'mysportsfeeds', 'nfl_data_py', 'other')),
    endpoint TEXT NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    error_message TEXT,
    called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CHECK(status_code IS NULL OR (status_code >= 100 AND status_code < 600)),
    CHECK(response_time_ms IS NULL OR response_time_ms >= 0)
);

-- Index for API name queries (count calls per API)
CREATE INDEX IF NOT EXISTS idx_api_calls_name 
ON api_call_log(api_name);

-- Index for date-based queries (calls in last 24 hours)
CREATE INDEX IF NOT EXISTS idx_api_calls_date 
ON api_call_log(called_at);

-- Composite index for API + date queries (rate limit tracking)
CREATE INDEX IF NOT EXISTS idx_api_calls_name_date 
ON api_call_log(api_name, called_at);

-- Index for status code analysis (count 429 errors, etc.)
CREATE INDEX IF NOT EXISTS idx_api_calls_status 
ON api_call_log(status_code);


-- Trigger: Update updated_at timestamp on injury_reports
CREATE TRIGGER IF NOT EXISTS update_injury_reports_timestamp 
AFTER UPDATE ON injury_reports
BEGIN
    UPDATE injury_reports 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;


-- View: latest_vegas_lines (helper for quick access to most recent data)
CREATE VIEW IF NOT EXISTS latest_vegas_lines AS
SELECT 
    week,
    game_id,
    home_team,
    away_team,
    home_spread,
    total,
    home_itt,
    away_itt,
    fetched_at
FROM vegas_lines
WHERE week = (SELECT MAX(week) FROM vegas_lines)
ORDER BY game_id;


-- View: active_injuries (helper for quick access to current Q/D/O players)
CREATE VIEW IF NOT EXISTS active_injuries AS
SELECT 
    week,
    player_name,
    team,
    position,
    injury_status,
    practice_status,
    body_part,
    updated_at
FROM injury_reports
WHERE injury_status IN ('Q', 'D', 'O')
    AND week = (SELECT MAX(week) FROM injury_reports)
ORDER BY injury_status, team, player_name;


-- View: flag_summary (helper for aggregating flags by severity)
CREATE VIEW IF NOT EXISTS flag_summary AS
SELECT 
    week,
    severity,
    flag_category,
    COUNT(*) as flag_count
FROM narrative_flags
GROUP BY week, severity, flag_category
ORDER BY week DESC, severity, flag_count DESC;

