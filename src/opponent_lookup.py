"""
Opponent Lookup from Vegas Lines

Uses Vegas odds data to determine which team each NFL team is playing against
for a given week. This provides clean opponent data without parsing messy CSV columns.

The lookup is built once when data is loaded and cached for the session.
"""

import sqlite3
from typing import Dict, Optional
from pathlib import Path


# NFL team abbreviation to full name mapping
TEAM_NAME_TO_ABBR = {
    'Arizona Cardinals': 'ARI',
    'Atlanta Falcons': 'ATL',
    'Baltimore Ravens': 'BAL',
    'Buffalo Bills': 'BUF',
    'Carolina Panthers': 'CAR',
    'Chicago Bears': 'CHI',
    'Cincinnati Bengals': 'CIN',
    'Cleveland Browns': 'CLE',
    'Dallas Cowboys': 'DAL',
    'Denver Broncos': 'DEN',
    'Detroit Lions': 'DET',
    'Green Bay Packers': 'GB',
    'Houston Texans': 'HOU',
    'Indianapolis Colts': 'IND',
    'Jacksonville Jaguars': 'JAX',
    'Kansas City Chiefs': 'KC',
    'Las Vegas Raiders': 'LV',
    'Los Angeles Chargers': 'LAC',
    'Los Angeles Rams': 'LA',
    'Miami Dolphins': 'MIA',
    'Minnesota Vikings': 'MIN',
    'New England Patriots': 'NE',
    'New Orleans Saints': 'NO',
    'New York Giants': 'NYG',
    'New York Jets': 'NYJ',
    'Philadelphia Eagles': 'PHI',
    'Pittsburgh Steelers': 'PIT',
    'San Francisco 49ers': 'SF',
    'Seattle Seahawks': 'SEA',
    'Tampa Bay Buccaneers': 'TB',
    'Tennessee Titans': 'TEN',
    'Washington Commanders': 'WAS',
}

# Abbreviation variations (maps non-standard abbreviations to standard ones)
ABBR_VARIATIONS = {
    'LAR': 'LA',  # Rams
    'LV': 'LV',   # Raiders (already standard)
    'OAK': 'LV',  # Old Raiders abbreviation
    'WSH': 'WAS', # Old Washington abbreviation
    'WAS': 'WAS', # Washington (standard)
}


def build_opponent_lookup(
    week: int = 5,
    db_path: str = "dfs_optimizer.db"
) -> Dict[str, str]:
    """
    Build a team -> opponent lookup from Vegas lines data.
    
    For each game in the Vegas lines, we create bidirectional mappings:
    - home_team -> away_team
    - away_team -> home_team
    
    Args:
        week: NFL week number to get matchups for
        db_path: Path to SQLite database
    
    Returns:
        Dict mapping team abbreviation to opponent abbreviation
        Example: {'KC': 'SF', 'SF': 'KC', 'BAL': 'CIN', 'CIN': 'BAL', ...}
    """
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"⚠️ Database not found: {db_path}")
        return {}
    
    opponent_map = {}
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query Vegas lines for the specified week
        query = """
        SELECT home_team, away_team
        FROM vegas_lines
        WHERE week = ?
        ORDER BY game_id
        """
        
        cursor.execute(query, (week,))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            print(f"⚠️ No Vegas lines found for Week {week}")
            return {}
        
        # Build bidirectional mapping (convert full names to abbreviations)
        for home_team_full, away_team_full in rows:
            # Convert full team names to abbreviations
            home_abbr = TEAM_NAME_TO_ABBR.get(home_team_full, home_team_full)
            away_abbr = TEAM_NAME_TO_ABBR.get(away_team_full, away_team_full)
            
            # Away team plays @ Home team
            opponent_map[away_abbr] = home_abbr
            # Home team plays vs Away team
            opponent_map[home_abbr] = away_abbr
        
        print(f"✅ Built opponent lookup for Week {week}: {len(opponent_map)} teams mapped")
        return opponent_map
    
    except Exception as e:
        print(f"❌ Error building opponent lookup: {e}")
        return {}


def get_opponent(
    team: str,
    opponent_map: Dict[str, str]
) -> str:
    """
    Get the opponent for a given team.
    
    Args:
        team: Team abbreviation (e.g., 'KC', 'SF', 'LAR')
        opponent_map: Pre-built opponent lookup dictionary
    
    Returns:
        Opponent abbreviation with @ prefix if away game, or vs if home
        Returns "-" if opponent not found
    """
    if not opponent_map:
        return "-"
    
    # Normalize the team abbreviation (handle variations like LAR -> LA)
    normalized_team = ABBR_VARIATIONS.get(team, team)
    
    opponent = opponent_map.get(normalized_team)
    if not opponent:
        # Try original team name as fallback
        opponent = opponent_map.get(team)
        if not opponent:
            return "-"
    
    # Note: We could add @ or vs prefix here if we track home/away
    # For now, just return the opponent abbreviation
    return opponent


def add_opponents_to_dataframe(df, opponent_map: Dict[str, str]):
    """
    Add opponent column to player DataFrame using the lookup map.
    
    Args:
        df: DataFrame with player data (must have 'team' column)
        opponent_map: Pre-built opponent lookup dictionary
    
    Returns:
        DataFrame with 'opponent' column added/updated
    """
    if 'team' not in df.columns:
        print("⚠️ No 'team' column found in DataFrame")
        return df
    
    # Add opponent column by mapping each team
    df['opponent'] = df['team'].apply(lambda team: get_opponent(team, opponent_map))
    
    matched = (df['opponent'] != '-').sum()
    total = len(df)
    print(f"✅ Matched opponents for {matched}/{total} players")
    
    return df

