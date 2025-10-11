-- Migration 003: Add Game Boxscore Tables
-- Created: 2025-10-10
-- Purpose: Store historical game data and player stats for trend analysis

-- Table: game_boxscores
-- Stores game-level data (date, teams, scores, weather, etc.)
CREATE TABLE IF NOT EXISTS game_boxscores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL UNIQUE,  -- Format: YYYYMMDD-AWAY-HOME or numeric ID
    season TEXT NOT NULL,           -- e.g., "2024-2025-regular", "2024-playoff"
    week INTEGER,                   -- NULL for playoff games
    game_date TEXT NOT NULL,        -- YYYY-MM-DD format
    start_time TEXT,                -- HH:MM:SS format
    
    -- Teams
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    
    -- Scores
    home_score INTEGER,
    away_score INTEGER,
    
    -- Game status
    game_status TEXT CHECK(game_status IN ('scheduled', 'in_progress', 'final', 'postponed', 'cancelled')),
    
    -- Venue/conditions
    venue TEXT,
    weather_conditions TEXT,
    temperature INTEGER,            -- Fahrenheit
    wind_speed INTEGER,             -- MPH
    
    -- Metadata
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CHECK(home_score IS NULL OR home_score >= 0),
    CHECK(away_score IS NULL OR away_score >= 0)
);

-- Indexes for game_boxscores
CREATE INDEX IF NOT EXISTS idx_game_boxscores_game_id 
ON game_boxscores(game_id);

CREATE INDEX IF NOT EXISTS idx_game_boxscores_season_week 
ON game_boxscores(season, week);

CREATE INDEX IF NOT EXISTS idx_game_boxscores_team 
ON game_boxscores(home_team, away_team);

CREATE INDEX IF NOT EXISTS idx_game_boxscores_date 
ON game_boxscores(game_date);


-- Table: player_game_stats
-- Stores player-level statistics from each game
CREATE TABLE IF NOT EXISTS player_game_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    player_id TEXT,                 -- MySportsFeeds player ID
    player_name TEXT NOT NULL,
    team TEXT NOT NULL,
    position TEXT NOT NULL,
    
    -- Playing time
    played BOOLEAN DEFAULT 1,       -- 1 if player participated
    started BOOLEAN DEFAULT 0,      -- 1 if player started
    
    -- Passing stats (QB)
    pass_attempts INTEGER DEFAULT 0,
    pass_completions INTEGER DEFAULT 0,
    pass_yards INTEGER DEFAULT 0,
    pass_touchdowns INTEGER DEFAULT 0,
    pass_interceptions INTEGER DEFAULT 0,
    pass_sacks INTEGER DEFAULT 0,
    pass_rating REAL,
    
    -- Rushing stats (RB, QB, WR)
    rush_attempts INTEGER DEFAULT 0,
    rush_yards INTEGER DEFAULT 0,
    rush_touchdowns INTEGER DEFAULT 0,
    rush_long INTEGER DEFAULT 0,
    rush_fumbles INTEGER DEFAULT 0,
    
    -- Receiving stats (WR, TE, RB)
    targets INTEGER DEFAULT 0,
    receptions INTEGER DEFAULT 0,
    receiving_yards INTEGER DEFAULT 0,
    receiving_touchdowns INTEGER DEFAULT 0,
    receiving_long INTEGER DEFAULT 0,
    receiving_fumbles INTEGER DEFAULT 0,
    
    -- Defense/Special Teams
    tackles INTEGER DEFAULT 0,
    sacks REAL DEFAULT 0,
    interceptions INTEGER DEFAULT 0,
    forced_fumbles INTEGER DEFAULT 0,
    fumble_recoveries INTEGER DEFAULT 0,
    defensive_touchdowns INTEGER DEFAULT 0,
    special_teams_touchdowns INTEGER DEFAULT 0,
    
    -- Kicking (K)
    field_goal_attempts INTEGER DEFAULT 0,
    field_goals_made INTEGER DEFAULT 0,
    extra_point_attempts INTEGER DEFAULT 0,
    extra_points_made INTEGER DEFAULT 0,
    
    -- Fantasy scoring (calculated)
    fantasy_points_draftkings REAL,
    fantasy_points_fanduel REAL,
    fantasy_points_yahoo REAL,
    
    -- Metadata
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (game_id) REFERENCES game_boxscores(game_id) ON DELETE CASCADE,
    
    CHECK(pass_attempts >= 0),
    CHECK(pass_completions >= 0),
    CHECK(pass_completions <= pass_attempts),
    CHECK(pass_touchdowns >= 0),
    CHECK(pass_interceptions >= 0),
    CHECK(rush_attempts >= 0),
    CHECK(rush_touchdowns >= 0),
    CHECK(targets >= 0),
    CHECK(receptions >= 0),
    CHECK(receptions <= targets),
    CHECK(receiving_touchdowns >= 0)
);

-- Indexes for player_game_stats
CREATE INDEX IF NOT EXISTS idx_player_game_stats_game_id 
ON player_game_stats(game_id);

CREATE INDEX IF NOT EXISTS idx_player_game_stats_player_name 
ON player_game_stats(player_name);

CREATE INDEX IF NOT EXISTS idx_player_game_stats_player_team 
ON player_game_stats(player_name, team);

CREATE INDEX IF NOT EXISTS idx_player_game_stats_position 
ON player_game_stats(position);

-- Unique constraint: one stat line per player per game
CREATE UNIQUE INDEX IF NOT EXISTS idx_player_game_stats_unique 
ON player_game_stats(game_id, player_name, team);


-- Table: team_game_stats
-- Stores team-level statistics from each game
CREATE TABLE IF NOT EXISTS team_game_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    team TEXT NOT NULL,
    opponent TEXT NOT NULL,
    is_home BOOLEAN NOT NULL,
    
    -- Score
    points_scored INTEGER DEFAULT 0,
    points_allowed INTEGER DEFAULT 0,
    
    -- Offense
    total_yards INTEGER DEFAULT 0,
    passing_yards INTEGER DEFAULT 0,
    rushing_yards INTEGER DEFAULT 0,
    first_downs INTEGER DEFAULT 0,
    third_down_conversions INTEGER DEFAULT 0,
    third_down_attempts INTEGER DEFAULT 0,
    fourth_down_conversions INTEGER DEFAULT 0,
    fourth_down_attempts INTEGER DEFAULT 0,
    
    -- Turnovers
    turnovers INTEGER DEFAULT 0,
    fumbles_lost INTEGER DEFAULT 0,
    interceptions_thrown INTEGER DEFAULT 0,
    
    -- Time of possession
    time_of_possession_seconds INTEGER,
    
    -- Penalties
    penalties INTEGER DEFAULT 0,
    penalty_yards INTEGER DEFAULT 0,
    
    -- Defense
    sacks REAL DEFAULT 0,
    tackles_for_loss INTEGER DEFAULT 0,
    qb_hits INTEGER DEFAULT 0,
    
    -- Metadata
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (game_id) REFERENCES game_boxscores(game_id) ON DELETE CASCADE,
    
    CHECK(points_scored >= 0),
    CHECK(total_yards >= 0),
    CHECK(turnovers >= 0)
);

-- Indexes for team_game_stats
CREATE INDEX IF NOT EXISTS idx_team_game_stats_game_id 
ON team_game_stats(game_id);

CREATE INDEX IF NOT EXISTS idx_team_game_stats_team 
ON team_game_stats(team);

-- Unique constraint: one stat line per team per game
CREATE UNIQUE INDEX IF NOT EXISTS idx_team_game_stats_unique 
ON team_game_stats(game_id, team);

