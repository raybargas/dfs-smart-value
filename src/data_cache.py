"""
Server-side data caching for API responses.

This module provides persistent caching for Vegas lines and injury reports,
storing data as JSON files that survive app restarts and can be shared across users.
"""

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import streamlit as st


# Cache directory for persistent data storage
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_file_path(data_type: str, week: int) -> Path:
    """Get the path to a cache file."""
    return CACHE_DIR / f"{data_type}_week{week}.json"


def save_vegas_lines_to_cache(week: int, db_path: str = "dfs_optimizer.db") -> bool:
    """
    Export Vegas lines from database to JSON cache file.
    
    Args:
        week: NFL week number
        db_path: Path to SQLite database
    
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Fetch all Vegas lines for this week
        cursor.execute("""
            SELECT game_id, home_team, away_team, home_spread, away_spread, 
                   total, home_itt, away_itt, fetched_at
            FROM vegas_lines
            WHERE week = ?
            ORDER BY game_id
        """, (week,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return False
        
        # Convert to list of dicts
        data = []
        for row in rows:
            data.append({
                'game_id': row[0],
                'home_team': row[1],
                'away_team': row[2],
                'home_spread': row[3],
                'away_spread': row[4],
                'total': row[5],
                'home_itt': row[6],
                'away_itt': row[7],
                'fetched_at': row[8]
            })
        
        # Save to cache file
        cache_file = get_cache_file_path('vegas_lines', week)
        with open(cache_file, 'w') as f:
            json.dump({
                'week': week,
                'cached_at': datetime.now().isoformat(),
                'record_count': len(data),
                'data': data
            }, f, indent=2)
        
        return True
        
    except Exception as e:
        st.error(f"Error saving Vegas lines to cache: {e}")
        return False


def save_injury_reports_to_cache(week: int, db_path: str = "dfs_optimizer.db") -> bool:
    """
    Export injury reports from database to JSON cache file.
    
    Args:
        week: NFL week number
        db_path: Path to SQLite database
    
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Fetch all injury reports for this week
        cursor.execute("""
            SELECT player_name, team, position, injury_status, practice_status,
                   body_part, description, updated_at
            FROM injury_reports
            WHERE week = ?
            ORDER BY team, player_name
        """, (week,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return False
        
        # Convert to list of dicts
        data = []
        for row in rows:
            data.append({
                'player_name': row[0],
                'team': row[1],
                'position': row[2],
                'injury_status': row[3],
                'practice_status': row[4],
                'body_part': row[5],
                'description': row[6],
                'updated_at': row[7]
            })
        
        # Save to cache file
        cache_file = get_cache_file_path('injury_reports', week)
        with open(cache_file, 'w') as f:
            json.dump({
                'week': week,
                'cached_at': datetime.now().isoformat(),
                'record_count': len(data),
                'data': data
            }, f, indent=2)
        
        return True
        
    except Exception as e:
        st.error(f"Error saving injury reports to cache: {e}")
        return False


def load_vegas_lines_from_cache(week: int, db_path: str = "dfs_optimizer.db") -> Optional[Dict]:
    """
    Load Vegas lines from JSON cache file into database.
    
    Args:
        week: NFL week number
        db_path: Path to SQLite database
    
    Returns:
        Dict with cache metadata if successful, None otherwise
    """
    try:
        cache_file = get_cache_file_path('vegas_lines', week)
        
        if not cache_file.exists():
            return None
        
        # Load from cache file
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        
        # Insert into database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Clear existing data for this week
        cursor.execute("DELETE FROM vegas_lines WHERE week = ?", (week,))
        
        # Insert cached data
        for row in cache_data['data']:
            cursor.execute("""
                INSERT INTO vegas_lines 
                (week, game_id, home_team, away_team, home_spread, away_spread, 
                 total, home_itt, away_itt, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                week, row['game_id'], row['home_team'], row['away_team'],
                row['home_spread'], row['away_spread'], row['total'],
                row['home_itt'], row['away_itt'], row['fetched_at']
            ))
        
        conn.commit()
        conn.close()
        
        return {
            'week': cache_data['week'],
            'cached_at': cache_data['cached_at'],
            'record_count': cache_data['record_count']
        }
        
    except Exception as e:
        st.error(f"Error loading Vegas lines from cache: {e}")
        return None


def load_injury_reports_from_cache(week: int, db_path: str = "dfs_optimizer.db") -> Optional[Dict]:
    """
    Load injury reports from JSON cache file into database.
    
    Args:
        week: NFL week number
        db_path: Path to SQLite database
    
    Returns:
        Dict with cache metadata if successful, None otherwise
    """
    try:
        cache_file = get_cache_file_path('injury_reports', week)
        
        if not cache_file.exists():
            return None
        
        # Load from cache file
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        
        # Insert into database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Clear existing data for this week
        cursor.execute("DELETE FROM injury_reports WHERE week = ?", (week,))
        
        # Insert cached data
        for row in cache_data['data']:
            cursor.execute("""
                INSERT INTO injury_reports 
                (week, player_name, team, position, injury_status, practice_status,
                 body_part, description, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                week, row['player_name'], row['team'], row['position'],
                row['injury_status'], row['practice_status'],
                row['body_part'], row['description'], row['updated_at']
            ))
        
        conn.commit()
        conn.close()
        
        return {
            'week': cache_data['week'],
            'cached_at': cache_data['cached_at'],
            'record_count': cache_data['record_count']
        }
        
    except Exception as e:
        st.error(f"Error loading injury reports from cache: {e}")
        return None


def get_cache_status(week: int) -> Dict:
    """
    Check if cache files exist for a given week.
    
    Args:
        week: NFL week number
    
    Returns:
        Dict with cache status for each data type
    """
    vegas_file = get_cache_file_path('vegas_lines', week)
    injury_file = get_cache_file_path('injury_reports', week)
    
    status = {
        'vegas_lines': {
            'exists': vegas_file.exists(),
            'path': str(vegas_file)
        },
        'injury_reports': {
            'exists': injury_file.exists(),
            'path': str(injury_file)
        }
    }
    
    # Get file metadata if exists
    if vegas_file.exists():
        try:
            with open(vegas_file, 'r') as f:
                data = json.load(f)
                status['vegas_lines']['cached_at'] = data.get('cached_at')
                status['vegas_lines']['record_count'] = data.get('record_count', 0)
        except:
            pass
    
    if injury_file.exists():
        try:
            with open(injury_file, 'r') as f:
                data = json.load(f)
                status['injury_reports']['cached_at'] = data.get('cached_at')
                status['injury_reports']['record_count'] = data.get('record_count', 0)
        except:
            pass
    
    return status


def list_cached_weeks() -> List[int]:
    """
    Get list of weeks that have cached data.
    
    Returns:
        Sorted list of week numbers with cache files
    """
    weeks = set()
    
    for file in CACHE_DIR.glob("*.json"):
        # Extract week number from filename (e.g., "vegas_lines_week6.json" -> 6)
        if "_week" in file.stem:
            try:
                week_str = file.stem.split("_week")[1]
                weeks.add(int(week_str))
            except:
                pass
    
    return sorted(list(weeks))

