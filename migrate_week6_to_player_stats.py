#!/usr/bin/env python3
"""
Migrate Week 6 contest data to player_game_stats table.

This script updates the existing Week 6 records in player_game_stats with
accurate position and team data from the contest standings, and ensures
fantasy points match the contest results.
"""

import sqlite3
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

def migrate_week6_data():
    """Migrate Week 6 contest data to player_game_stats table."""
    
    print("🚀 Migrating Week 6 Contest Data to player_game_stats")
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
            SELECT p.id, p.player_name, p.team, p.position, p.fantasy_points_draftkings, g.game_id
            FROM player_game_stats p
            JOIN game_boxscores g ON p.game_id = g.game_id
            WHERE g.week = 6
        """, conn)
        
        print(f"   Found {len(existing_data)} existing Week 6 records")
        
        # Step 3: Match and update records
        print("\\n🔄 Step 3: Matching and updating records...")
        
        updated_count = 0
        added_count = 0
        
        for _, contest_row in contest_data.iterrows():
            player_name = contest_row['player_name']
            contest_team = contest_row['team']
            contest_position = contest_row['position']
            contest_points = contest_row['actual_points']
            
            # Find matching record in existing data
            existing_match = existing_data[
                existing_data['player_name'].str.lower() == player_name.lower()
            ]
            
            if not existing_match.empty:
                # Update existing record
                record_id = existing_match.iloc[0]['id']
                game_id = existing_match.iloc[0]['game_id']
                
                # Update the record
                conn.execute("""
                    UPDATE player_game_stats 
                    SET team = ?, 
                        position = ?, 
                        fantasy_points_draftkings = ?,
                        played = 1,
                        started = CASE WHEN ? > 0 THEN 1 ELSE 0 END
                    WHERE id = ?
                """, (contest_team, contest_position, contest_points, contest_points, record_id))
                
                updated_count += 1
                
            else:
                # Need to add new record - find a game_id for Week 6
                week6_games = pd.read_sql_query("""
                    SELECT game_id FROM game_boxscores WHERE week = 6 LIMIT 1
                """, conn)
                
                if not week6_games.empty:
                    game_id = week6_games.iloc[0]['game_id']
                    
                    # Insert new record
                    conn.execute("""
                        INSERT INTO player_game_stats (
                            game_id, player_name, team, position, 
                            fantasy_points_draftkings, played, started, fetched_at
                        ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """, (
                        game_id, player_name, contest_team, contest_position,
                        contest_points, 1 if contest_points > 0 else 0,
                        datetime.utcnow().isoformat()
                    ))
                    
                    added_count += 1
        
        # Commit changes
        conn.commit()
        
        print(f"\\n✅ Migration complete!")
        print(f"   Updated: {updated_count} existing records")
        print(f"   Added: {added_count} new records")
        print(f"   Total processed: {updated_count + added_count}")
        
        # Step 4: Verify results
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
        
        print("   Top 10 Week 6 scorers after migration:")
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
        
        return True
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def cleanup_historical_pool():
    """Remove Week 6 data from historical_player_pool since it's now in player_game_stats."""
    
    print("\\n🧹 Cleaning up historical_player_pool...")
    
    conn = sqlite3.connect("dfs_optimizer.db")
    
    try:
        # Count records to be deleted
        count_query = pd.read_sql_query("""
            SELECT COUNT(*) as count
            FROM historical_player_pool
            WHERE slate_id = '2025-W6-DK-CONTEST'
        """, conn)
        
        count = count_query.iloc[0]['count']
        
        if count > 0:
            # Delete Week 6 records
            conn.execute("""
                DELETE FROM historical_player_pool
                WHERE slate_id = '2025-W6-DK-CONTEST'
            """)
            
            # Delete the slate entry
            conn.execute("""
                DELETE FROM slates
                WHERE slate_id = '2025-W6-DK-CONTEST'
            """)
            
            conn.commit()
            print(f"   ✅ Removed {count} records from historical_player_pool")
            print("   ✅ Removed slate entry")
        else:
            print("   ℹ️ No Week 6 records found in historical_player_pool")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error during cleanup: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("🎯 Week 6 Data Migration to player_game_stats")
    print("=" * 60)
    
    # Migrate data
    success = migrate_week6_data()
    
    if success:
        # Clean up historical pool
        cleanup_historical_pool()
        
        print("\\n🎉 Migration complete!")
        print("\\n💡 Benefits:")
        print("   ✅ Week 6 data now in single table with Weeks 1-5")
        print("   ✅ Accurate position and team data")
        print("   ✅ Single query for all historical data")
        print("   ✅ 80-20 rule can use unified data source")
        
    else:
        print("\\n❌ Migration failed. Check the error messages above.")
        sys.exit(1)
