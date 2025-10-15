"""
Import Week 6 historical data into database for historical scoring feature.
"""

import sqlite3
from datetime import datetime

# Week 6 actual scores from lineup2_actual_week6.py
week6_player_scores = {
    'Spencer Rattler': 11.08,
    'Christian McCaffrey': 24.1,
    'Rachaad White': 17.6,
    'Jaxon Smith-Njigba': 33.2,
    'Chris Olave': 15.8,
    'Cooper Kupp': 12.0,
    'Trey McBride': 21.2,
    'Rico Dowdle': 36.9,
    'Dolphins': 2.0
}

# Week 6 games (simplified - we'll create one game per team)
week6_games = [
    ('20241013-NO-NE', '2024-2025-regular', 6, '2024-10-13', 'NO', 'NE'),
    ('20241013-SF-CLE', '2024-2025-regular', 6, '2024-10-13', 'SF', 'CLE'),
    ('20241013-TB-DET', '2024-2025-regular', 6, '2024-10-13', 'TB', 'DET'),
    ('20241013-SEA-JAX', '2024-2025-regular', 6, '2024-10-13', 'SEA', 'JAX'),
    ('20241013-LAR-LV', '2024-2025-regular', 6, '2024-10-13', 'LAR', 'LV'),
    ('20241013-ARI-LAC', '2024-2025-regular', 6, '2024-10-13', 'ARI', 'LAC'),
    ('20241013-DAL-PHI', '2024-2025-regular', 6, '2024-10-13', 'DAL', 'PHI'),
    ('20241013-MIA-BUF', '2024-2025-regular', 6, '2024-10-13', 'MIA', 'BUF')
]

def import_week6_data():
    """Import Week 6 game and player data into database."""
    
    db_path = "dfs_optimizer.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Insert game boxscores
        print("Inserting Week 6 games...")
        for game_id, season, week, game_date, home_team, away_team in week6_games:
            cursor.execute("""
                INSERT OR REPLACE INTO game_boxscores 
                (game_id, season, week, game_date, home_team, away_team, game_status)
                VALUES (?, ?, ?, ?, ?, ?, 'final')
            """, (game_id, season, week, game_date, home_team, away_team))
        
        # Insert player game stats
        print("Inserting Week 6 player stats...")
        for player_name, dk_points in week6_player_scores.items():
            # Determine team and game_id based on player
            team_map = {
                'Spencer Rattler': ('NO', '20241013-NO-NE'),
                'Christian McCaffrey': ('SF', '20241013-SF-CLE'),
                'Rachaad White': ('TB', '20241013-TB-DET'),
                'Jaxon Smith-Njigba': ('SEA', '20241013-SEA-JAX'),
                'Chris Olave': ('NO', '20241013-NO-NE'),
                'Cooper Kupp': ('LAR', '20241013-LAR-LV'),
                'Trey McBride': ('ARI', '20241013-ARI-LAC'),
                'Rico Dowdle': ('DAL', '20241013-DAL-PHI'),
                'Dolphins': ('MIA', '20241013-MIA-BUF')
            }
            
            team, game_id = team_map.get(player_name, ('UNK', '20241013-UNK-UNK'))
            
            # Determine position
            position_map = {
                'Spencer Rattler': 'QB',
                'Christian McCaffrey': 'RB',
                'Rachaad White': 'RB',
                'Jaxon Smith-Njigba': 'WR',
                'Chris Olave': 'WR',
                'Cooper Kupp': 'WR',
                'Trey McBride': 'TE',
                'Rico Dowdle': 'RB',
                'Dolphins': 'DST'
            }
            
            position = position_map.get(player_name, 'UNK')
            
            cursor.execute("""
                INSERT OR REPLACE INTO player_game_stats 
                (game_id, player_name, team, position, fantasy_points_draftkings, played)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (game_id, player_name, team, position, dk_points))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Successfully imported Week 6 data:")
        print(f"   - {len(week6_games)} games")
        print(f"   - {len(week6_player_scores)} player scores")
        print(f"   - Database: {db_path}")
        
    except Exception as e:
        print(f"❌ Error importing Week 6 data: {e}")

if __name__ == "__main__":
    import_week6_data()
