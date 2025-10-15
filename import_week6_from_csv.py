"""
Import Week 6 historical data from contest standings CSV into database.
"""

import pandas as pd
import sqlite3
from datetime import datetime

def import_week6_from_csv():
    """Import Week 6 player scores from contest standings CSV."""
    
    # Read the CSV file
    df = pd.read_csv('contest-standings-183090259.csv', low_memory=False)
    
    # Clean up the data
    df = df.dropna(subset=['Player', 'FPTS'])
    df['FPTS'] = pd.to_numeric(df['FPTS'], errors='coerce')
    df = df.dropna(subset=['FPTS'])
    
    # Get unique player scores (take the first occurrence of each player)
    player_scores = df.groupby('Player')['FPTS'].first().to_dict()
    
    print(f"Found {len(player_scores)} unique players in CSV")
    print("Sample players:", list(player_scores.items())[:10])
    
    # Connect to database
    db_path = "dfs_optimizer.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Clear existing Week 6 data
        cursor.execute("DELETE FROM player_game_stats WHERE game_id LIKE '20241013-%'")
        cursor.execute("DELETE FROM game_boxscores WHERE week = 6")
        
        # Create Week 6 games (simplified - one game per team)
        week6_games = [
            ('20241013-NO-NE', '2024-2025-regular', 6, '2024-10-13', 'NO', 'NE'),
            ('20241013-SF-CLE', '2024-2025-regular', 6, '2024-10-13', 'SF', 'CLE'),
            ('20241013-TB-DET', '2024-2025-regular', 6, '2024-10-13', 'TB', 'DET'),
            ('20241013-SEA-JAX', '2024-2025-regular', 6, '2024-10-13', 'SEA', 'JAX'),
            ('20241013-LAR-LV', '2024-2025-regular', 6, '2024-10-13', 'LAR', 'LV'),
            ('20241013-ARI-LAC', '2024-2025-regular', 6, '2024-10-13', 'ARI', 'LAC'),
            ('20241013-DAL-PHI', '2024-2025-regular', 6, '2024-10-13', 'DAL', 'PHI'),
            ('20241013-MIA-BUF', '2024-2025-regular', 6, '2024-10-13', 'MIA', 'BUF'),
            ('20241013-GB-CIN', '2024-2025-regular', 6, '2024-10-13', 'GB', 'CIN'),
            ('20241013-CAR-DAL', '2024-2025-regular', 6, '2024-10-13', 'CAR', 'DAL')
        ]
        
        # Insert games
        for game_id, season, week, game_date, home_team, away_team in week6_games:
            cursor.execute("""
                INSERT INTO game_boxscores 
                (game_id, season, week, game_date, home_team, away_team, game_status)
                VALUES (?, ?, ?, ?, ?, ?, 'final')
            """, (game_id, season, week, game_date, home_team, away_team))
        
        # Insert player scores
        inserted_count = 0
        for player_name, dk_points in player_scores.items():
            # Determine team and game_id based on player name patterns
            # This is a simplified mapping - in reality you'd need more sophisticated matching
            team_map = {
                'Sam Darnold': ('SEA', '20241013-SEA-JAX'),
                'Javonte Williams': ('DAL', '20241013-DAL-PHI'),
                'Rachaad White': ('TB', '20241013-TB-DET'),
                'Jaxon Smith-Njigba': ('SEA', '20241013-SEA-JAX'),
                'Chris Olave': ('NO', '20241013-NO-NE'),
                'Cooper Kupp': ('SEA', '20241013-SEA-JAX'),  # From your lineup
                'Jake Ferguson': ('DAL', '20241013-DAL-PHI'),
                'Rico Dowdle': ('CAR', '20241013-CAR-DAL'),
                'Packers': ('GB', '20241013-GB-CIN'),
                'Dolphins': ('MIA', '20241013-MIA-BUF')
            }
            
            # Try to find team mapping, fallback to generic
            team, game_id = team_map.get(player_name, ('UNK', '20241013-UNK-UNK'))
            
            # Determine position based on common patterns
            if any(pos in player_name.lower() for pos in ['qb', 'quarterback']):
                position = 'QB'
            elif any(pos in player_name.lower() for pos in ['rb', 'running back']):
                position = 'RB'
            elif any(pos in player_name.lower() for pos in ['wr', 'wide receiver']):
                position = 'WR'
            elif any(pos in player_name.lower() for pos in ['te', 'tight end']):
                position = 'TE'
            elif any(pos in player_name.lower() for pos in ['dst', 'defense', 'packers', 'dolphins', 'raiders', 'seahawks', 'rams', 'titans', 'bengals', 'browns', 'colts', 'steelers']):
                position = 'DST'
            else:
                position = 'UNK'
            
            cursor.execute("""
                INSERT INTO player_game_stats 
                (game_id, player_name, team, position, fantasy_points_draftkings, played)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (game_id, player_name, team, position, dk_points))
            inserted_count += 1
        
        conn.commit()
        conn.close()
        
        print(f"✅ Successfully imported Week 6 data from CSV:")
        print(f"   - {len(week6_games)} games")
        print(f"   - {inserted_count} player scores")
        print(f"   - Database: {db_path}")
        
    except Exception as e:
        print(f"❌ Error importing Week 6 data: {e}")
        conn.rollback()
        conn.close()

if __name__ == "__main__":
    import_week6_from_csv()
