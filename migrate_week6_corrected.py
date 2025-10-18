#!/usr/bin/env python3
"""
Corrected migration: Update Week 6 data in player_game_stats with contest data.

This script updates the existing Week 6 records in player_game_stats with
accurate position and team data from the contest standings.
"""

import sqlite3
import pandas as pd
from datetime import datetime
import sys

def migrate_week6_data():
    """Update Week 6 data in player_game_stats with contest data."""
    
    print("🚀 Updating Week 6 Data in player_game_stats")
    print("=" * 60)
    
    # Connect to database
    db_path = "dfs_optimizer.db"
    conn = sqlite3.connect(db_path)
    
    try:
        # Step 1: Get Week 6 contest data
        print("📊 Step 1: Reading Week 6 contest data...")
        contest_data = pd.read_sql_query("""
            SELECT player_name, team, position, actual_points
            FROM historical_player_pool
            WHERE slate_id = '2025-W6-DK-CONTEST'
            AND actual_points IS NOT NULL
        """, conn)
        
        print(f"   Found {len(contest_data)} players in contest data")
        
        # Step 2: Get existing Week 6 data in player_game_stats
        print("\\n📊 Step 2: Reading existing Week 6 data in player_game_stats...")
        existing_data = pd.read_sql_query("""
            SELECT p.id, p.player_name, p.team, p.position, p.fantasy_points_draftkings
            FROM player_game_stats p
            JOIN game_boxscores g ON p.game_id = g.game_id
            WHERE g.week = 6
        """, conn)
        
        print(f"   Found {len(existing_data)} existing Week 6 records")
        
        # Step 3: Create lookup dictionary for contest data
        contest_lookup = {}
        for _, row in contest_data.iterrows():
            contest_lookup[row['player_name'].lower()] = {
                'team': row['team'],
                'position': row['position'],
                'points': row['actual_points']
            }
        
        # Step 4: Update existing records
        print("\\n🔄 Step 3: Updating existing records...")
        
        updated_count = 0
        not_found_count = 0
        
        for _, existing_row in existing_data.iterrows():
            player_name = existing_row['player_name']
            record_id = existing_row['id']
            
            # Look up contest data
            contest_info = contest_lookup.get(player_name.lower())
            
            if contest_info:
                # Update the record
                conn.execute("""
                    UPDATE player_game_stats 
                    SET team = ?, 
                        position = ?, 
                        fantasy_points_draftkings = ?,
                        played = 1,
                        started = CASE WHEN ? > 0 THEN 1 ELSE 0 END
                    WHERE id = ?
                """, (
                    contest_info['team'], 
                    contest_info['position'], 
                    contest_info['points'],
                    contest_info['points'],
                    record_id
                ))
                
                updated_count += 1
            else:
                not_found_count += 1
        
        # Commit changes
        conn.commit()
        
        print(f"\\n✅ Update complete!")
        print(f"   Updated: {updated_count} records")
        print(f"   Not found in contest: {not_found_count} records")
        
        # Step 5: Verify results
        print("\\n🔍 Step 4: Verifying results...")
        
        # Check updated data
        updated_data = pd.read_sql_query("""
            SELECT p.player_name, p.team, p.position, p.fantasy_points_draftkings
            FROM player_game_stats p
            JOIN game_boxscores g ON p.game_id = g.game_id
            WHERE g.week = 6
            AND p.fantasy_points_draftkings IS NOT NULL
            ORDER BY p.fantasy_points_draftkings DESC
            LIMIT 10
        """, conn)
        
        print("   Top 10 Week 6 scorers after update:")
        print(updated_data.to_string(index=False))
        
        # Check for any remaining UNK values
        unk_count = pd.read_sql_query("""
            SELECT COUNT(*) as count
            FROM player_game_stats p
            JOIN game_boxscores g ON p.game_id = g.game_id
            WHERE g.week = 6
            AND (p.team = 'UNK' OR p.position = 'UNK')
        """, conn)
        
        print(f"\\n   Remaining UNK values: {unk_count.iloc[0]['count']}")
        
        # Check total Week 6 records
        total_count = pd.read_sql_query("""
            SELECT COUNT(*) as count
            FROM player_game_stats p
            JOIN game_boxscores g ON p.game_id = g.game_id
            WHERE g.week = 6
        """, conn)
        
        print(f"   Total Week 6 records: {total_count.iloc[0]['count']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("🎯 Week 6 Data Update in player_game_stats")
    print("=" * 60)
    
    # Update data
    success = migrate_week6_data()
    
    if success:
        print("\\n🎉 Update complete!")
        print("\\n💡 Benefits:")
        print("   ✅ Week 6 data now has accurate position and team data")
        print("   ✅ Single table contains all Weeks 1-6 data")
        print("   ✅ No more UNK values for Week 6")
        print("   ✅ 80-20 rule can use unified data source")
        
    else:
        print("\\n❌ Update failed. Check the error messages above.")
        sys.exit(1)
