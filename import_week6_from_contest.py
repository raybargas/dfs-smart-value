#!/usr/bin/env python3
"""
Import Week 6 player data from contest standings CSV into historical database.

This script extracts player fantasy point scores from the contest standings CSV
and imports them into the historical_player_pool table for Week 6, enabling
the 80-20 rule and other historical analysis features.
"""

import pandas as pd
import sqlite3
from datetime import datetime
import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def import_week6_data():
    """Import Week 6 player data from contest standings CSV."""
    
    # Read contest standings CSV
    csv_path = "contest-standings-183090259.csv"
    if not Path(csv_path).exists():
        print(f"❌ Contest standings CSV not found: {csv_path}")
        return False
    
    print(f"📊 Reading contest standings from {csv_path}...")
    df = pd.read_csv(csv_path, low_memory=False)
    
    # Extract unique player scores
    print("🔍 Extracting player scores...")
    player_scores = df[['Player', 'FPTS']].dropna()
    player_scores = player_scores.groupby('Player')['FPTS'].first().reset_index()
    
    print(f"✅ Found {len(player_scores)} unique players with Week 6 scores")
    
    # Connect to database
    db_path = "dfs_optimizer.db"
    conn = sqlite3.connect(db_path)
    
    try:
        # Create Week 6 slate entry
        slate_id = "2025-W6-DK-CONTEST"
        week = 6
        season = 2025
        
        print(f"📅 Creating slate entry: {slate_id}")
        
        # Insert slate if not exists
        slate_check = pd.read_sql_query(
            "SELECT slate_id FROM slates WHERE slate_id = ?", 
            conn, params=(slate_id,)
        )
        
        if slate_check.empty:
            slate_data = {
                'slate_id': slate_id,
                'week': week,
                'season': season,
                'site': 'DraftKings',
                'contest_type': 'Contest',
                'slate_date': '2025-10-05',
                'games_in_slate': '["Week6-2025"]',
                'created_at': datetime.utcnow().isoformat()
            }
            
            slate_df = pd.DataFrame([slate_data])
            slate_df.to_sql('slates', conn, if_exists='append', index=False)
            print(f"✅ Created slate: {slate_id}")
        else:
            print(f"ℹ️ Slate already exists: {slate_id}")
        
        # Prepare historical player pool data
        print("📝 Preparing historical player pool data...")
        
        historical_data = []
        for _, row in player_scores.iterrows():
            player_name = row['Player']
            actual_points = row['FPTS']
            
            # Create historical player pool entry
            player_data = {
                'slate_id': slate_id,
                'player_id': f"W6-{player_name.replace(' ', '_')}",  # Simple ID
                'player_name': player_name,
                'position': 'UNKNOWN',  # Will need to be updated
                'team': 'UNKNOWN',     # Will need to be updated
                'opponent': 'UNKNOWN',
                'salary': 0,           # Not available in contest data
                'projection': 0,       # Not available in contest data
                'ceiling': None,
                'ownership': None,
                'actual_points': actual_points,
                'smart_value': None,
                'smart_value_profile': None,
                'projection_source': 'Contest Import',
                'ownership_source': None,
                'data_source': 'contest-standings-183090259.csv',
                'fetched_at': datetime.utcnow().isoformat()
            }
            
            historical_data.append(player_data)
        
        # Insert into historical_player_pool
        print(f"💾 Inserting {len(historical_data)} player records...")
        
        historical_df = pd.DataFrame(historical_data)
        historical_df.to_sql('historical_player_pool', conn, if_exists='append', index=False)
        
        print("✅ Week 6 data imported successfully!")
        
        # Show summary
        print("\n📊 Import Summary:")
        print(f"   Slate ID: {slate_id}")
        print(f"   Players: {len(historical_data)}")
        print(f"   Top Scorers:")
        
        top_scorers = player_scores.nlargest(5, 'FPTS')
        for _, row in top_scorers.iterrows():
            print(f"     {row['Player']}: {row['FPTS']:.1f} points")
        
        return True
        
    except Exception as e:
        print(f"❌ Error importing Week 6 data: {e}")
        return False
        
    finally:
        conn.close()

def update_player_positions():
    """Update player positions and teams using existing data."""
    
    print("\n🔧 Updating player positions and teams...")
    
    conn = sqlite3.connect("dfs_optimizer.db")
    
    try:
        # Get Week 6 players that need position/team updates
        week6_players = pd.read_sql_query("""
            SELECT player_name, position, team 
            FROM historical_player_pool 
            WHERE slate_id = '2025-W6-DK-CONTEST' 
            AND (position = 'UNKNOWN' OR team = 'UNKNOWN')
        """, conn)
        
        if week6_players.empty:
            print("ℹ️ No players need position/team updates")
            return True
        
        print(f"📝 Found {len(week6_players)} players needing updates")
        
        # Try to match with existing player data
        updated_count = 0
        for _, player in week6_players.iterrows():
            player_name = player['player_name']
            
            # Look for this player in other tables
            matches = pd.read_sql_query("""
                SELECT DISTINCT position, team 
                FROM player_game_stats 
                WHERE player_name = ? 
                AND position IS NOT NULL 
                AND team IS NOT NULL
                LIMIT 1
            """, conn, params=(player_name,))
            
            if not matches.empty:
                position = matches.iloc[0]['position']
                team = matches.iloc[0]['team']
                
                # Update the historical player pool
                conn.execute("""
                    UPDATE historical_player_pool 
                    SET position = ?, team = ?
                    WHERE slate_id = '2025-W6-DK-CONTEST' 
                    AND player_name = ?
                """, (position, team, player_name))
                
                updated_count += 1
        
        conn.commit()
        print(f"✅ Updated {updated_count} players with position/team data")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating player positions: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("🚀 Week 6 Data Import from Contest Standings")
    print("=" * 50)
    
    # Import Week 6 data
    success = import_week6_data()
    
    if success:
        # Update player positions
        update_player_positions()
        
        print("\n🎉 Week 6 import complete!")
        print("\n💡 Next steps:")
        print("   1. Week 6 data is now available for 80-20 rule calculations")
        print("   2. Historical analysis will include Week 6 performance")
        print("   3. Smart Value calculations can use Week 6 as 'prior week'")
        
    else:
        print("\n❌ Import failed. Check the error messages above.")
        sys.exit(1)
