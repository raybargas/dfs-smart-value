"""
Advanced Stats Database Operations

Lightweight module for saving/loading advanced stats to/from database.
Separated from advanced_stats_loader.py to avoid heavy import dependencies.
"""

import sqlite3
import pandas as pd
from typing import Dict, Optional
from pathlib import Path


def save_advanced_stats_to_database(
    season_files: Dict[str, Optional[pd.DataFrame]],
    week: int,
    db_path: str = "dfs_optimizer.db"
) -> bool:
    """
    Save advanced stats from loaded files to database.
    
    Args:
        season_files: Dictionary of loaded DataFrames from FileLoader
        week: Week number
        db_path: Path to SQLite database
    
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Ensure table exists (migration should handle this, but safe check)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS advanced_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                team TEXT NOT NULL,
                position TEXT NOT NULL,
                week INTEGER NOT NULL,
                adv_tprr REAL,
                adv_yprr REAL,
                adv_rte_pct REAL,
                adv_yaco_att REAL,
                adv_success_rate REAL,
                adv_cpoe REAL,
                adv_adot REAL,
                adv_deep_throw_pct REAL,
                adv_1read_pct REAL,
                adv_mtf_att REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(player_name, team, position, week)
            )
        """)
        
        # Import from each file type
        # For each file type, clear ONLY that stat type's columns for this week
        # This allows uploading files one at a time without wiping other data
        records_saved = 0
        
        # Receiving stats (TPRR, YPRR, RTE%, 1READ%)
        if season_files.get('receiving') is not None:
            # Clear only receiving-specific columns for this week
            cursor.execute("""
                UPDATE advanced_stats 
                SET adv_tprr = NULL, adv_yprr = NULL, adv_rte_pct = NULL
                WHERE week = ?
            """, (week,))
            
            rec_df = season_files['receiving']
            for _, row in rec_df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO advanced_stats 
                    (player_name, team, position, week, adv_tprr, adv_yprr, adv_rte_pct, adv_1read_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get('Name'),
                    row.get('Team'),
                    row.get('POS'),
                    week,
                    row.get('TPRR'),
                    row.get('YPRR'),
                    row.get('RTE %'),
                    row.get('1READ %')
                ))
                records_saved += 1
        
        # Rush stats (YACO/ATT, Success Rate, MTF/ATT)
        if season_files.get('rush') is not None:
            # Clear only rush-specific columns for this week
            cursor.execute("""
                UPDATE advanced_stats 
                SET adv_yaco_att = NULL, adv_success_rate = NULL, adv_mtf_att = NULL
                WHERE week = ?
            """, (week,))
            
            rush_df = season_files['rush']
            for _, row in rush_df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO advanced_stats 
                    (player_name, team, position, week, adv_yaco_att, adv_success_rate, adv_mtf_att)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get('Name'),
                    row.get('Team'),
                    row.get('POS'),
                    week,
                    row.get('YACO/ATT'),
                    row.get('Success Rate'),
                    row.get('MTF/ATT')
                ))
                records_saved += 1
        
        # Pass stats (CPOE, aDOT, Deep Throw%)
        if season_files.get('pass') is not None:
            # Clear only pass-specific columns for this week
            cursor.execute("""
                UPDATE advanced_stats 
                SET adv_cpoe = NULL, adv_adot = NULL, adv_deep_throw_pct = NULL
                WHERE week = ?
            """, (week,))
            
            pass_df = season_files['pass']
            for _, row in pass_df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO advanced_stats 
                    (player_name, team, position, week, adv_cpoe, adv_adot, adv_deep_throw_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row.get('Name'),
                    row.get('Team'),
                    row.get('POS'),
                    week,
                    row.get('CPOE'),
                    row.get('aDOT'),
                    row.get('Deep Throw %')
                ))
                records_saved += 1
        
        # Snap stats (1READ%)
        if season_files.get('snaps') is not None:
            # Clear only snap-specific columns for this week
            cursor.execute("""
                UPDATE advanced_stats 
                SET adv_1read_pct = NULL
                WHERE week = ?
            """, (week,))
            
            snaps_df = season_files['snaps']
            for _, row in snaps_df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO advanced_stats 
                    (player_name, team, position, week, adv_1read_pct)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    row.get('Name'),
                    row.get('Team'),
                    row.get('POS'),
                    week,
                    row.get('1READ %')
                ))
                records_saved += 1
        
        conn.commit()
        conn.close()
        
        return records_saved > 0
        
    except Exception as e:
        print(f"Error saving advanced stats to database: {e}")
        return False


def load_advanced_stats_from_database(
    week: int,
    db_path: str = "dfs_optimizer.db"
) -> Optional[pd.DataFrame]:
    """
    Load advanced stats for a specific week from database.
    
    Args:
        week: Week number
        db_path: Path to SQLite database
    
    Returns:
        DataFrame with advanced stats or None if error
    """
    try:
        conn = sqlite3.connect(db_path)
        
        query = """
            SELECT 
                player_name,
                team,
                position,
                week,
                adv_tprr,
                adv_yprr,
                adv_rte_pct,
                adv_yaco_att,
                adv_success_rate,
                adv_cpoe,
                adv_adot,
                adv_deep_throw_pct,
                adv_1read_pct,
                adv_mtf_att
            FROM advanced_stats
            WHERE week = ?
        """
        
        df = pd.read_sql_query(query, conn, params=(week,))
        conn.close()
        
        return df if len(df) > 0 else None
        
    except Exception as e:
        print(f"Error loading advanced stats from database: {e}")
        return None

