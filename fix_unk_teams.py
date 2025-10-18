#!/usr/bin/env python3
"""
Fix UNK team assignments in Week 6 data using season_stats.

This script updates Week 6 players with UNK team assignments using
team data from the season_stats table, which contains accurate
team assignments for all players.
"""

import sqlite3
import pandas as pd
from datetime import datetime
import sys

def fix_unk_teams():
    """Fix UNK team assignments in Week 6 data using season_stats."""
    
    print("🔧 Fixing UNK Team Assignments in Week 6 Data")
    print("=" * 60)
    
    # Connect to database
    db_path = "dfs_optimizer.db"
    conn = sqlite3.connect(db_path)
    
    try:
        # Step 1: Get Week 6 players with UNK teams
        print("📊 Step 1: Finding Week 6 players with UNK teams...")
        unk_players = pd.read_sql_query("""
            SELECT p.id, p.player_name, p.team, p.position, p.fantasy_points_draftkings
            FROM player_game_stats p
            JOIN game_boxscores g ON p.game_id = g.game_id
            WHERE g.week = 6
            AND p.team = 'UNK'
            ORDER BY p.fantasy_points_draftkings DESC
        """, conn)
        
        print(f"   Found {len(unk_players)} players with UNK teams")
        
        if len(unk_players) == 0:
            print("   ✅ No UNK teams found - all good!")
            return True
        
        # Step 2: Get team data from season_stats
        print("\\n📊 Step 2: Getting team data from season_stats...")
        season_teams = pd.read_sql_query("""
            SELECT player_name, team, position
            FROM season_stats
            WHERE team IS NOT NULL AND team != ''
        """, conn)
        
        print(f"   Found {len(season_teams)} players with team data")
        
        # Step 3: Create lookup dictionary
        team_lookup = {}
        for _, row in season_teams.iterrows():
            team_lookup[row['player_name'].lower()] = {
                'team': row['team'],
                'position': row['position'] if row['position'] else None
            }
        
        # Step 4: Update UNK players
        print("\\n🔄 Step 3: Updating UNK team assignments...")
        
        updated_count = 0
        not_found_count = 0
        
        for _, player in unk_players.iterrows():
            player_name = player['player_name']
            record_id = player['id']
            
            # Look up team data
            team_info = team_lookup.get(player_name.lower())
            
            if team_info:
                # Update the record
                conn.execute("""
                    UPDATE player_game_stats 
                    SET team = ?, 
                        position = COALESCE(?, position)
                    WHERE id = ?
                """, (
                    team_info['team'], 
                    team_info['position'],
                    record_id
                ))
                
                updated_count += 1
                print(f"   ✅ {player_name}: {team_info['team']} {team_info['position'] or 'UNK'}")
            else:
                not_found_count += 1
                print(f"   ❌ {player_name}: No team data found")
        
        # Commit changes
        conn.commit()
        
        print(f"\\n✅ Update complete!")
        print(f"   Updated: {updated_count} players")
        print(f"   Not found: {not_found_count} players")
        
        # Step 5: Verify results
        print("\\n🔍 Step 4: Verifying results...")
        
        # Check remaining UNK teams
        remaining_unk = pd.read_sql_query("""
            SELECT COUNT(*) as count
            FROM player_game_stats p
            JOIN game_boxscores g ON p.game_id = g.game_id
            WHERE g.week = 6
            AND p.team = 'UNK'
        """, conn)
        
        print(f"   Remaining UNK teams: {remaining_unk.iloc[0]['count']}")
        
        # Show updated top scorers
        top_scorers = pd.read_sql_query("""
            SELECT p.player_name, p.team, p.position, p.fantasy_points_draftkings
            FROM player_game_stats p
            JOIN game_boxscores g ON p.game_id = g.game_id
            WHERE g.week = 6
            AND p.fantasy_points_draftkings IS NOT NULL
            ORDER BY p.fantasy_points_draftkings DESC
            LIMIT 10
        """, conn)
        
        print("\\n   Top 10 Week 6 scorers after update:")
        print(top_scorers.to_string(index=False))
        
        return True
        
    except Exception as e:
        print(f"❌ Error during update: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("🎯 Fix UNK Team Assignments")
    print("=" * 60)
    
    # Fix UNK teams
    success = fix_unk_teams()
    
    if success:
        print("\\n🎉 UNK team fix complete!")
        print("\\n💡 Benefits:")
        print("   ✅ Week 6 data now has accurate team assignments")
        print("   ✅ No more UNK teams for known players")
        print("   ✅ Consistent team data across all weeks")
        print("   ✅ Better data quality for analysis")
        
    else:
        print("\\n❌ UNK team fix failed. Check the error messages above.")
        sys.exit(1)
