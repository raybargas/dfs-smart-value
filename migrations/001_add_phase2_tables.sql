-- Migration 001: Add Phase 2 Extended Data Models Tables
-- Created: 2025-10-09
-- Purpose: Support Monte Carlo simulations, game scenarios, and portfolio optimization

-- Table: player_projections
-- Extends player data with projection distribution fields for Monte Carlo simulation
CREATE TABLE IF NOT EXISTS player_projections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT NOT NULL,
    position TEXT NOT NULL,
    salary INTEGER NOT NULL,
    base_projection REAL NOT NULL,
    mean_projection REAL NOT NULL,
    std_deviation REAL NOT NULL CHECK(std_deviation >= 0),
    ceiling_95th REAL NOT NULL,
    floor_5th REAL NOT NULL,
    correlation_group TEXT,
    team TEXT NOT NULL,
    opponent TEXT NOT NULL,
    ownership REAL CHECK(ownership >= 0 AND ownership <= 100),
    player_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CHECK(ceiling_95th >= floor_5th),
    CHECK(mean_projection BETWEEN floor_5th AND ceiling_95th)
);

-- Index for fast player lookups
CREATE INDEX IF NOT EXISTS idx_player_projections_name 
ON player_projections(player_name);

-- Index for correlation group queries
CREATE INDEX IF NOT EXISTS idx_player_projections_correlation 
ON player_projections(correlation_group);

-- Index for team-based queries
CREATE INDEX IF NOT EXISTS idx_player_projections_team 
ON player_projections(team);


-- Table: game_scenarios
-- Stores game scenario definitions with adjustment factors
CREATE TABLE IF NOT EXISTS game_scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id TEXT NOT NULL UNIQUE,
    scenario_type TEXT NOT NULL CHECK(scenario_type IN (
        'blowout', 'shootout', 'weather', 'pace', 
        'revenge', 'primetime', 'divisional', 'custom'
    )),
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast scenario lookups
CREATE INDEX IF NOT EXISTS idx_game_scenarios_scenario_id 
ON game_scenarios(scenario_id);

-- Index for scenario type queries
CREATE INDEX IF NOT EXISTS idx_game_scenarios_type 
ON game_scenarios(scenario_type);


-- Table: scenario_adjustments
-- Stores individual adjustments within a scenario
CREATE TABLE IF NOT EXISTS scenario_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id TEXT NOT NULL,
    adjustment_key TEXT NOT NULL,  -- Format: "{POSITION}_{TEAM}" (e.g., "QB_KC")
    adjustment_factor REAL NOT NULL,
    
    FOREIGN KEY (scenario_id) REFERENCES game_scenarios(scenario_id) ON DELETE CASCADE
);

-- Index for fast adjustment lookups
CREATE INDEX IF NOT EXISTS idx_scenario_adjustments_scenario 
ON scenario_adjustments(scenario_id);

-- Index for key lookups
CREATE INDEX IF NOT EXISTS idx_scenario_adjustments_key 
ON scenario_adjustments(adjustment_key);


-- Table: lineup_portfolios
-- Stores portfolio metadata
CREATE TABLE IF NOT EXISTS lineup_portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id TEXT NOT NULL UNIQUE,
    lineup_count INTEGER NOT NULL CHECK(lineup_count > 0),
    average_projection REAL,
    portfolio_variance REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast portfolio lookups
CREATE INDEX IF NOT EXISTS idx_lineup_portfolios_portfolio_id 
ON lineup_portfolios(portfolio_id);


-- Table: portfolio_lineups
-- Links lineups to portfolios
CREATE TABLE IF NOT EXISTS portfolio_lineups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id TEXT NOT NULL,
    lineup_id INTEGER NOT NULL,
    lineup_position INTEGER NOT NULL,  -- Order within portfolio (1-N)
    
    FOREIGN KEY (portfolio_id) REFERENCES lineup_portfolios(portfolio_id) ON DELETE CASCADE
);

-- Index for fast portfolio lineup lookups
CREATE INDEX IF NOT EXISTS idx_portfolio_lineups_portfolio 
ON portfolio_lineups(portfolio_id);

-- Index for lineup queries
CREATE INDEX IF NOT EXISTS idx_portfolio_lineups_lineup 
ON portfolio_lineups(lineup_id);


-- Table: historical_lineups
-- Stores historical lineup performance for learning system
CREATE TABLE IF NOT EXISTS historical_lineups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lineup_id INTEGER NOT NULL,
    contest_date DATE NOT NULL,
    contest_type TEXT,
    projected_points REAL NOT NULL,
    actual_points REAL,
    scenario_id TEXT,
    portfolio_id TEXT,
    finished_position INTEGER,
    entries_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (scenario_id) REFERENCES game_scenarios(scenario_id),
    FOREIGN KEY (portfolio_id) REFERENCES lineup_portfolios(portfolio_id)
);

-- Index for date-based queries
CREATE INDEX IF NOT EXISTS idx_historical_lineups_date 
ON historical_lineups(contest_date);

-- Index for scenario correlation analysis
CREATE INDEX IF NOT EXISTS idx_historical_lineups_scenario 
ON historical_lineups(scenario_id);


-- Table: player_exposure
-- Tracks player exposure within portfolios
CREATE TABLE IF NOT EXISTS player_exposure (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    exposure_count INTEGER NOT NULL CHECK(exposure_count > 0),
    exposure_percentage REAL NOT NULL CHECK(exposure_percentage >= 0 AND exposure_percentage <= 100),
    
    FOREIGN KEY (portfolio_id) REFERENCES lineup_portfolios(portfolio_id) ON DELETE CASCADE,
    UNIQUE(portfolio_id, player_name)
);

-- Index for exposure queries
CREATE INDEX IF NOT EXISTS idx_player_exposure_portfolio 
ON player_exposure(portfolio_id);

-- Index for player-based queries
CREATE INDEX IF NOT EXISTS idx_player_exposure_player 
ON player_exposure(player_name);


-- Table: correlation_matrices
-- Stores correlation matrices for portfolios
CREATE TABLE IF NOT EXISTS correlation_matrices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id TEXT NOT NULL,
    lineup_i INTEGER NOT NULL,
    lineup_j INTEGER NOT NULL,
    correlation_value REAL NOT NULL CHECK(correlation_value >= 0 AND correlation_value <= 1),
    
    FOREIGN KEY (portfolio_id) REFERENCES lineup_portfolios(portfolio_id) ON DELETE CASCADE
);

-- Index for correlation matrix queries
CREATE INDEX IF NOT EXISTS idx_correlation_matrices_portfolio 
ON correlation_matrices(portfolio_id);


-- Trigger: Update updated_at timestamp on player_projections
CREATE TRIGGER IF NOT EXISTS update_player_projections_timestamp 
AFTER UPDATE ON player_projections
BEGIN
    UPDATE player_projections 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;


-- Trigger: Update updated_at timestamp on game_scenarios
CREATE TRIGGER IF NOT EXISTS update_game_scenarios_timestamp 
AFTER UPDATE ON game_scenarios
BEGIN
    UPDATE game_scenarios 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;


-- Trigger: Update updated_at timestamp on lineup_portfolios
CREATE TRIGGER IF NOT EXISTS update_lineup_portfolios_timestamp 
AFTER UPDATE ON lineup_portfolios
BEGIN
    UPDATE lineup_portfolios 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;

