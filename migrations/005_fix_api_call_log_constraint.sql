-- Migration 005: Fix api_call_log constraint to include mysportsfeeds_dfs
-- Date: 2025-10-16
-- Description: Add 'mysportsfeeds_dfs' to the allowed api_name values

-- SQLite doesn't support ALTER TABLE to modify CHECK constraints directly
-- We need to recreate the table

-- Step 1: Create new table with correct constraint
CREATE TABLE api_call_log_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_name TEXT NOT NULL CHECK(api_name IN ('the_odds_api', 'mysportsfeeds', 'mysportsfeeds_dfs', 'nfl_data_py', 'other')),
    endpoint TEXT NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    error_message TEXT,
    called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Step 2: Copy existing data
INSERT INTO api_call_log_new (id, api_name, endpoint, status_code, response_time_ms, error_message, called_at)
SELECT id, api_name, endpoint, status_code, response_time_ms, error_message, called_at
FROM api_call_log;

-- Step 3: Drop old table
DROP TABLE api_call_log;

-- Step 4: Rename new table
ALTER TABLE api_call_log_new RENAME TO api_call_log;

-- Step 5: Recreate indexes
CREATE INDEX idx_api_call_log_api_name ON api_call_log(api_name);
CREATE INDEX idx_api_call_log_called_at ON api_call_log(called_at);

