"""
80/20 Regression Rule Analyzer

Identifies players at high risk of regression based on the 80/20 rule:
"80% of players who scored 20+ fantasy points the previous week will regress"

This module:
1. Calculates DraftKings fantasy points from raw stats
2. Queries prior week performance from database
3. Flags players who scored 20+ points as regression candidates
"""

from typing import Dict, List, Optional, Tuple
import sqlite3
from pathlib import Path
import pandas as pd


def calculate_dk_fantasy_points(stats: Dict) -> float:
    """
    Calculate DraftKings fantasy points from raw player stats.
    
    DraftKings Scoring (standard):
    - Passing: 0.04 pts per yard, 4 pts per TD, -1 per INT
    - Rushing: 0.1 pts per yard, 6 pts per TD
    - Receiving: 1 pt per reception, 0.1 pts per yard, 6 pts per TD
    - Fumbles: -1 per fumble (pass + rush + receiving)
    - 2-pt conversions: 2 pts (not tracked in our data yet)
    
    Args:
        stats: Dict with keys like pass_yards, pass_touchdowns, etc.
    
    Returns:
        float: Total DraftKings fantasy points
    """
    points = 0.0
    
    # Passing
    points += stats.get('pass_yards', 0) * 0.04
    points += stats.get('pass_touchdowns', 0) * 4
    points -= stats.get('pass_interceptions', 0) * 1
    
    # Rushing
    points += stats.get('rush_yards', 0) * 0.1
    points += stats.get('rush_touchdowns', 0) * 6
    
    # Receiving
    points += stats.get('receptions', 0) * 1.0
    points += stats.get('receiving_yards', 0) * 0.1
    points += stats.get('receiving_touchdowns', 0) * 6
    
    # Note: Fumbles columns don't exist in our database schema yet
    # When available, add: points -= stats.get('fumbles_lost', 0) * 1
    
    return round(points, 2)


def get_prior_week_performance(
    player_name: str,
    week: int = 6,
    db_path: str = "dfs_optimizer.db"
) -> Optional[Dict]:
    """
    Get a player's prior week fantasy performance from the database.
    
    Args:
        player_name: Player's full name (e.g., "Lamar Jackson")
        week: Week to query (default: 5 for Week 5 data)
        db_path: Path to SQLite database
    
    Returns:
        Dict with keys: player_name, team, position, dk_points, raw_stats
        None if player not found
    """
    db_file = Path(db_path)
    if not db_file.exists():
        return None
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = """
        SELECT 
            p.player_name,
            p.team,
            p.position,
            p.pass_yards,
            p.pass_touchdowns,
            p.pass_interceptions,
            p.rush_yards,
            p.rush_touchdowns,
            p.receptions,
            p.receiving_yards,
            p.receiving_touchdowns
        FROM player_game_stats p
        JOIN game_boxscores g ON p.game_id = g.game_id
        WHERE g.week = ?
        AND LOWER(p.player_name) = LOWER(?)
        """
        
        cursor.execute(query, (week, player_name))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        stats = dict(row)
        dk_points = calculate_dk_fantasy_points(stats)
        
        return {
            'player_name': stats['player_name'],
            'team': stats['team'],
            'position': stats['position'],
            'dk_points': dk_points,
            'raw_stats': stats
        }
    
    except Exception as e:
        print(f"Error querying prior week data for {player_name}: {e}")
        return None


def get_high_scorers_from_prior_week(
    threshold: float = 20.0,
    week: int = 6,
    db_path: str = "dfs_optimizer.db"
) -> List[Dict]:
    """
    Get all players who scored above threshold in the prior week.
    
    These are regression candidates per the 80/20 rule.
    
    Args:
        threshold: Fantasy points threshold (default: 20.0)
        week: Week to query (default: 5)
        db_path: Path to SQLite database
    
    Returns:
        List of dicts with player_name, team, position, dk_points
    """
    db_file = Path(db_path)
    if not db_file.exists():
        return []
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = """
        SELECT 
            p.player_name,
            p.team,
            p.position,
            p.pass_yards,
            p.pass_touchdowns,
            p.pass_interceptions,
            p.rush_yards,
            p.rush_touchdowns,
            p.receptions,
            p.receiving_yards,
            p.receiving_touchdowns
        FROM player_game_stats p
        JOIN game_boxscores g ON p.game_id = g.game_id
        WHERE g.week = ?
        AND p.position = 'WR'
        """
        
        cursor.execute(query, (week,))
        rows = cursor.fetchall()
        conn.close()
        
        high_scorers = []
        for row in rows:
            stats = dict(row)
            dk_points = calculate_dk_fantasy_points(stats)
            
            if dk_points >= threshold:
                high_scorers.append({
                    'player_name': stats['player_name'],
                    'team': stats['team'],
                    'position': stats['position'],
                    'dk_points': dk_points
                })
        
        # Sort by points descending
        high_scorers.sort(key=lambda x: x['dk_points'], reverse=True)
        return high_scorers
    
    except Exception as e:
        print(f"Error querying high scorers: {e}")
        return []


def check_regression_risk(
    player_name: str,
    week: int = 6,
    threshold: float = 20.0,
    db_path: str = "dfs_optimizer.db"
) -> Tuple[bool, Optional[float], Optional[Dict]]:
    """
    Check if a player is at regression risk per the 80/20 rule.
    
    Args:
        player_name: Player's full name
        week: Prior week to check (default: 5)
        threshold: Points threshold for regression risk (default: 20.0)
        db_path: Path to database
    
    Returns:
        Tuple of (is_at_risk: bool, prior_week_points: Optional[float], stats: Optional[Dict])
        stats dict contains: pass_yards, pass_td, rush_yards, rush_td, receptions, rec_yards, rec_td
    """
    performance = get_prior_week_performance(player_name, week, db_path)
    
    if not performance:
        return (False, None, None)
    
    dk_points = performance['dk_points']
    is_at_risk = dk_points >= threshold
    
    # Extract key stats for tooltip
    raw_stats = performance['raw_stats']
    stats_summary = {
        'pass_yards': raw_stats.get('pass_yards', 0),
        'pass_td': raw_stats.get('pass_touchdowns', 0),
        'pass_int': raw_stats.get('pass_interceptions', 0),
        'rush_yards': raw_stats.get('rush_yards', 0),
        'rush_td': raw_stats.get('rush_touchdowns', 0),
        'receptions': raw_stats.get('receptions', 0),
        'rec_yards': raw_stats.get('receiving_yards', 0),
        'rec_td': raw_stats.get('receiving_touchdowns', 0)
    }
    
    return (is_at_risk, dk_points, stats_summary)


def check_regression_risk_batch(
    player_names: List[str],
    week: int = 6,
    threshold: float = 20.0,
    db_path: str = "dfs_optimizer.db"
) -> Dict[str, Tuple[bool, Optional[float], Optional[Dict]]]:
    """
    Batch version of check_regression_risk - queries all players in ONE database call.
    
    PERFORMANCE OPTIMIZATION: Eliminates N+1 query problem by fetching all player
    data in a single query, then processing results in memory.
    
    Args:
        player_names: List of player names to check
        week: Prior week to check (default: 5)
        threshold: Points threshold for regression risk (default: 20.0)
        db_path: Path to database
    
    Returns:
        Dict mapping player_name -> (is_at_risk, prior_week_points, stats_summary)
        Players not found in database will have (False, None, None)
    
    Example:
        results = check_regression_risk_batch(['Lamar Jackson', 'Justin Jefferson'], week=5)
        is_at_risk, points, stats = results['Lamar Jackson']
    """
    db_file = Path(db_path)
    if not db_file.exists():
        # Return empty results for all players
        return {name: (False, None, None) for name in player_names}
    
    if not player_names:
        return {}
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Create placeholders for IN clause (?, ?, ?, ...)
        placeholders = ','.join('?' * len(player_names))
        
        # Query all players at once
        query = f"""
        SELECT 
            p.player_name,
            p.team,
            p.position,
            p.pass_yards,
            p.pass_touchdowns,
            p.pass_interceptions,
            p.rush_yards,
            p.rush_touchdowns,
            p.receptions,
            p.receiving_yards,
            p.receiving_touchdowns
        FROM player_game_stats p
        JOIN game_boxscores g ON p.game_id = g.game_id
        WHERE g.week = ?
        AND LOWER(p.player_name) IN ({placeholders})
        """
        
        # Lowercase all player names for case-insensitive matching
        lowercase_names = [name.lower() for name in player_names]
        
        cursor.execute(query, [week] + lowercase_names)
        rows = cursor.fetchall()
        conn.close()
        
        # Build results dictionary
        results = {}
        
        # First, initialize all players with no data found
        for name in player_names:
            results[name] = (False, None, None)
        
        # Then, process found players
        for row in rows:
            raw_stats = {
                'pass_yards': row['pass_yards'] or 0,
                'pass_touchdowns': row['pass_touchdowns'] or 0,
                'pass_interceptions': row['pass_interceptions'] or 0,
                'rush_yards': row['rush_yards'] or 0,
                'rush_touchdowns': row['rush_touchdowns'] or 0,
                'receptions': row['receptions'] or 0,
                'receiving_yards': row['receiving_yards'] or 0,
                'receiving_touchdowns': row['receiving_touchdowns'] or 0
            }
            
            dk_points = calculate_dk_fantasy_points(raw_stats)
            is_at_risk = dk_points >= threshold
            
            stats_summary = {
                'pass_yards': raw_stats['pass_yards'],
                'pass_td': raw_stats['pass_touchdowns'],
                'pass_int': raw_stats['pass_interceptions'],
                'rush_yards': raw_stats['rush_yards'],
                'rush_td': raw_stats['rush_touchdowns'],
                'receptions': raw_stats['receptions'],
                'rec_yards': raw_stats['receiving_yards'],
                'rec_td': raw_stats['receiving_touchdowns']
            }
            
            # Find original name with matching case
            player_name = row['player_name']
            original_name = None
            for name in player_names:
                if name.lower() == player_name.lower():
                    original_name = name
                    break
            
            if original_name:
                results[original_name] = (is_at_risk, dk_points, stats_summary)
        
        return results
        
    except Exception as e:
        # On error, return empty results for all players
        return {name: (False, None, None) for name in player_names}

