"""
Initialize historical Week 6 data for Streamlit Cloud deployment.
This script creates the database tables and inserts Week 6 data.
"""

import sqlite3
import pandas as pd
import os

def init_historical_data():
    """Initialize Week 6 historical data in the database."""
    
    # Database path (works for both local and cloud)
    db_path = "dfs_optimizer.db"
    
    # Read the CSV file
    csv_path = "contest-standings-183090259.csv"
    if not os.path.exists(csv_path):
        print(f"❌ CSV file not found: {csv_path}")
        return False
    
    df = pd.read_csv(csv_path, low_memory=False)
    
    # Clean up the data
    df = df.dropna(subset=['Player', 'FPTS'])
    df['FPTS'] = pd.to_numeric(df['FPTS'], errors='coerce')
    df = df.dropna(subset=['FPTS'])
    
    # Get unique player scores (take the first occurrence of each player)
    player_scores = df.groupby('Player')['FPTS'].first().to_dict()
    
    print(f"Found {len(player_scores)} unique players in CSV")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Clear existing Week 6 data
        cursor.execute("DELETE FROM player_game_stats WHERE game_id LIKE '20241013-%'")
        cursor.execute("DELETE FROM game_boxscores WHERE week = 6")
        
        # Create Week 6 games
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
        
        # Insert player scores with improved team mapping
        team_map = {
            'Sam Darnold': ('SEA', '20241013-SEA-JAX'),
            'Javonte Williams': ('DAL', '20241013-DAL-PHI'),
            'Rachaad White': ('TB', '20241013-TB-DET'),
            'Jaxon Smith-Njigba': ('SEA', '20241013-SEA-JAX'),
            'Chris Olave': ('NO', '20241013-NO-NE'),
            'Cooper Kupp': ('SEA', '20241013-SEA-JAX'),
            'Jake Ferguson': ('DAL', '20241013-DAL-PHI'),
            'Rico Dowdle': ('CAR', '20241013-CAR-DAL'),
            'Packers': ('GB', '20241013-GB-CIN'),
            'Dolphins': ('MIA', '20241013-MIA-BUF'),
            '49ers': ('SF', '20241013-SF-CLE'),
            'Rams': ('LAR', '20241013-LAR-LV'),
            'Cardinals': ('ARI', '20241013-ARI-LAC'),
            'Bengals': ('CIN', '20241013-GB-CIN'),
            'Browns': ('CLE', '20241013-SF-CLE'),
            'Lions': ('DET', '20241013-TB-DET'),
            'Jaguars': ('JAX', '20241013-SEA-JAX'),
            'Raiders': ('LV', '20241013-LAR-LV'),
            'Chargers': ('LAC', '20241013-ARI-LAC'),
            'Eagles': ('PHI', '20241013-DAL-PHI'),
            'Bills': ('BUF', '20241013-MIA-BUF'),
            'Patriots': ('NE', '20241013-NO-NE'),
            'Cowboys': ('DAL', '20241013-DAL-PHI')
        }
        
        # Default game assignment for unmapped players
        default_games = [
            '20241013-NO-NE', '20241013-SF-CLE', '20241013-TB-DET', 
            '20241013-SEA-JAX', '20241013-LAR-LV', '20241013-ARI-LAC',
            '20241013-DAL-PHI', '20241013-MIA-BUF', '20241013-GB-CIN', 
            '20241013-CAR-DAL'
        ]
        
        inserted_count = 0
        for i, (player_name, dk_points) in enumerate(player_scores.items()):
            # Clean player name (remove trailing spaces)
            player_name = player_name.strip()
            
            # Try to find team mapping, fallback to default game assignment
            if player_name in team_map:
                team, game_id = team_map[player_name]
            else:
                # Assign to a default game to ensure all players are included
                game_id = default_games[i % len(default_games)]
                team = 'UNK'
            
            # Determine position based on common patterns
            if any(pos in player_name.lower() for pos in ['qb', 'quarterback']):
                position = 'QB'
            elif any(pos in player_name.lower() for pos in ['rb', 'running back']):
                position = 'RB'
            elif any(pos in player_name.lower() for pos in ['wr', 'wide receiver']):
                position = 'WR'
            elif any(pos in player_name.lower() for pos in ['te', 'tight end']):
                position = 'TE'
            elif any(pos in player_name.lower() for pos in ['dst', 'defense', 'packers', 'dolphins', 'raiders', 'seahawks', 'rams', 'titans', 'bengals', 'browns', 'colts', 'steelers', '49ers', 'cardinals', 'lions', 'jaguars', 'chargers', 'eagles', 'bills', 'patriots', 'cowboys']):
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
        
        print(f"✅ Successfully initialized Week 6 historical data:")
        print(f"   - {len(week6_games)} games")
        print(f"   - {inserted_count} player scores")
        print(f"   - Database: {db_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error initializing historical data: {e}")
        conn.rollback()
        conn.close()
        return False

if __name__ == "__main__":
    init_historical_data()
