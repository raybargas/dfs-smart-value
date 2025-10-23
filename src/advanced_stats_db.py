"""
Advanced Stats Database Operations - 4 Separate Tables

Lightweight module for saving/loading advanced stats to/from database.
Uses 4 separate tables to avoid INSERT OR REPLACE conflicts.
"""

import sqlite3
import pandas as pd
from typing import Dict, Optional
from pathlib import Path
import sys

# Add parent directory to path for config import
parent_path = Path(__file__).parent.parent
sys.path.insert(0, str(parent_path))

from config import DEFAULT_DB_PATH


def _normalize_column_name(col: str) -> str:
    """Normalize column names to handle variations between file versions."""
    # Convert to lowercase and replace spaces with underscores
    normalized = col.lower().replace(' ', '_').replace('%', 'pct').replace('/', '_')
    # Remove special characters
    normalized = ''.join(c for c in normalized if c.isalnum() or c == '_')
    return normalized


def _get_player_name(row: pd.Series) -> str:
    """Extract player name from row, handling different column names."""
    for col in ['Name', 'name', 'Player', 'player']:
        if col in row.index:
            return row[col]
    return None


def _get_team(row: pd.Series) -> str:
    """Extract team from row, handling different column names."""
    for col in ['Team', 'team']:
        if col in row.index:
            return row[col]
    return None


def _get_position(row: pd.Series) -> str:
    """Extract position from row, handling different column names."""
    for col in ['POS', 'pos', 'Position', 'position']:
        if col in row.index:
            return row[col]
    return None


def save_advanced_stats_to_database(
    season_files: Dict[str, Optional[pd.DataFrame]],
    week: int,
    db_path: str = None
) -> bool:
    """
    Save advanced stats from loaded files to 4 separate database tables.
    
    Args:
        season_files: Dictionary of loaded DataFrames from file uploads
        week: Week number
        db_path: Path to SQLite database (defaults to config.DEFAULT_DB_PATH)
    
    Returns:
        True if successful, False otherwise
    """
    # Use config default if not specified
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create tables inline (simpler and more reliable than migration file)
        print("📝 Creating tables...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pass_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    team TEXT NOT NULL,
                    position TEXT NOT NULL,
                    week INTEGER NOT NULL,
                    cpoe REAL, adot REAL, deep_throw_pct REAL,
                    att INTEGER, cmp INTEGER, cmp_pct REAL, yds INTEGER,
                    ypa REAL, td INTEGER, int INTEGER, rate REAL,
                    sack INTEGER, sack_pct REAL, any_a REAL,
                    read1_pct REAL, acc_pct REAL, press_pct REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(player_name, team, position, week)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rush_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    team TEXT NOT NULL,
                    position TEXT NOT NULL,
                    week INTEGER NOT NULL,
                    yaco_att REAL, success_rate REAL, mtf_att REAL,
                    att INTEGER, yds INTEGER, ypc REAL, td INTEGER,
                    fum INTEGER, first_downs INTEGER, stuff_pct REAL,
                    mtf INTEGER, yaco INTEGER, yaco_pct REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(player_name, team, position, week)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS receiving_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    team TEXT NOT NULL,
                    position TEXT NOT NULL,
                    week INTEGER NOT NULL,
                    tprr REAL, yprr REAL, rte_pct REAL,
                    rte INTEGER, tgt INTEGER, tgt_pct REAL, rec INTEGER,
                    cr_pct REAL, yds INTEGER, ypr REAL, yac INTEGER,
                    yac_rec REAL, td INTEGER, read1_pct REAL, mtf INTEGER,
                    mtf_rec REAL, first_downs INTEGER, drops INTEGER,
                    drop_pct REAL, adot REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(player_name, team, position, week)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS snap_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    team TEXT NOT NULL,
                    position TEXT NOT NULL,
                    week INTEGER NOT NULL,
                    snaps INTEGER, snap_pct REAL, tm_snaps INTEGER,
                    snaps_per_gp REAL, rush_per_snap REAL, rush_share REAL,
                    tgt_per_snap REAL, tgt_share REAL, touch_per_snap REAL,
                    util_per_snap REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(player_name, team, position, week)
                )
        """)
        print("✅ Tables created")
        
        records_saved = 0
        
        # ====================================================================
        # PASS STATS
        # ====================================================================
        if season_files.get('pass') is not None:
            pass_df = season_files['pass']
            
            for _, row in pass_df.iterrows():
                player_name = _get_player_name(row)
                team = _get_team(row)
                position = _get_position(row)
                
                if not player_name or not team or not position:
                    continue
                
                cursor.execute("""
                    INSERT OR REPLACE INTO pass_stats 
                    (player_name, team, position, week, cpoe, adot, deep_throw_pct,
                     att, cmp, cmp_pct, yds, ypa, td, int, rate, sack, sack_pct,
                     any_a, read1_pct, acc_pct, press_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_name, team, position, week,
                    row.get('CPOE'), row.get('aDOT'), row.get('Deep Throw %'),
                    row.get('ATT'), row.get('CMP'), row.get('CMP %'),
                    row.get('YDS'), row.get('YPA'), row.get('TD'), row.get('INT'),
                    row.get('RATE'), row.get('SACK'), row.get('SACK %'),
                    row.get('ANY/A'), row.get('1Read %'), row.get('ACC %'), row.get('PRESS %')
                ))
                records_saved += 1
        
        # ====================================================================
        # RUSH STATS
        # ====================================================================
        if season_files.get('rush') is not None:
            rush_df = season_files['rush']
            
            for _, row in rush_df.iterrows():
                player_name = _get_player_name(row)
                team = _get_team(row)
                position = _get_position(row)
                
                if not player_name or not team or not position:
                    continue
                
                cursor.execute("""
                    INSERT OR REPLACE INTO rush_stats 
                    (player_name, team, position, week, yaco_att, success_rate, mtf_att,
                     att, yds, ypc, td, fum, first_downs, stuff_pct, mtf, yaco, yaco_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_name, team, position, week,
                    row.get('YACO/ATT'), row.get('Success Rate'), row.get('MTF/ATT'),
                    row.get('ATT'), row.get('YDS'), row.get('YPC'), row.get('TD'),
                    row.get('FUM'), row.get('1D'), row.get('STUFF %'),
                    row.get('MTF'), row.get('YACO'), row.get('YACO %')
                ))
                records_saved += 1
        
        # ====================================================================
        # RECEIVING STATS
        # ====================================================================
        if season_files.get('receiving') is not None:
            rec_df = season_files['receiving']
            
            for _, row in rec_df.iterrows():
                player_name = _get_player_name(row)
                team = _get_team(row)
                position = _get_position(row)
                
                if not player_name or not team or not position:
                    continue
                
                cursor.execute("""
                    INSERT OR REPLACE INTO receiving_stats 
                    (player_name, team, position, week, tprr, yprr, rte_pct,
                     rte, tgt, tgt_pct, rec, cr_pct, yds, ypr, yac, yac_rec,
                     td, read1_pct, mtf, mtf_rec, first_downs, drops, drop_pct, adot)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_name, team, position, week,
                    row.get('TPRR'), row.get('YPRR'), row.get('RTE %'),
                    row.get('RTE'), row.get('TGT'), row.get('TGT %'),
                    row.get('REC'), row.get('CR %'), row.get('YDS'), row.get('YPR'),
                    row.get('YAC'), row.get('YAC/REC'), row.get('TD'), row.get('1READ %'),
                    row.get('MTF'), row.get('MTF/REC'), row.get('1D'),
                    row.get('DRP'), row.get('DRP %'), row.get('aDOT')
                ))
                records_saved += 1
        
        # ====================================================================
        # SNAP STATS (Handle both Week 7 and Week 8 formats)
        # ====================================================================
        if season_files.get('snaps') is not None:
            snaps_df = season_files['snaps']
            
            for _, row in snaps_df.iterrows():
                player_name = _get_player_name(row)
                team = _get_team(row)
                position = _get_position(row)
                
                if not player_name or not team or not position:
                    continue
                
                # Handle different column formats
                snaps = row.get('Snaps') or row.get('snaps')
                snap_pct = row.get('Snap %') or row.get('snap_pct')
                
                cursor.execute("""
                    INSERT OR REPLACE INTO snap_stats 
                    (player_name, team, position, week, snaps, snap_pct,
                     tm_snaps, snaps_per_gp, rush_per_snap, rush_share,
                     tgt_per_snap, tgt_share, touch_per_snap, util_per_snap)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_name, team, position, week,
                    snaps, snap_pct,
                    row.get('TM Snaps'), row.get('snaps_per_gp'),
                    row.get('rush_per_snap'), row.get('rush_share'),
                    row.get('tgt_per_snap'), row.get('tgt_share'),
                    row.get('touch_per_snap'), row.get('util_per_snap')
                ))
                records_saved += 1
        
        conn.commit()
        conn.close()
        
        return records_saved > 0
        
    except Exception as e:
        print(f"Error saving advanced stats to database: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_advanced_stats_from_database(
    week: int,
    db_path: str = None
) -> Dict[str, Optional[pd.DataFrame]]:
    """
    Load advanced stats for a specific week from all 4 tables.
    
    Args:
        week: Week number
        db_path: Path to SQLite database (defaults to config.DEFAULT_DB_PATH)
    
    Returns:
        Dictionary with DataFrames for each stat type or None if error
    """
    # Use config default if not specified
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    try:
        conn = sqlite3.connect(db_path)
        
        result = {}
        
        # Load from each table
        tables = {
            'pass': 'pass_stats',
            'rush': 'rush_stats',
            'receiving': 'receiving_stats',
            'snaps': 'snap_stats'
        }
        
        for key, table_name in tables.items():
            try:
                query = f"SELECT * FROM {table_name} WHERE week = ?"
                df = pd.read_sql_query(query, conn, params=(week,))
                result[key] = df if len(df) > 0 else None
            except Exception as e:
                print(f"Error loading {table_name}: {e}")
                result[key] = None
        
        conn.close()
        return result
        
    except Exception as e:
        print(f"Error loading advanced stats from database: {e}")
        return {'pass': None, 'rush': None, 'receiving': None, 'snaps': None}
