"""
Import Season Stats from Excel into Database

This script reads the "2025 Stats thru week X.xlsx" file and updates the database
with season-level statistics for all players. Run this whenever you receive
updated weekly data.

Usage:
    python scripts/import_season_data.py "2025 Stats thru week 5.xlsx"
    python scripts/import_season_data.py "2025 Stats thru week 6.xlsx"
"""

import sys
import pandas as pd
import sqlite3
from pathlib import Path
from datetime import datetime


def import_season_data(excel_file: str, db_path: str = "dfs_optimizer.db"):
    """
    Import season statistics from Excel file into database.
    
    Args:
        excel_file: Path to Excel file (e.g., "2025 Stats thru week 5.xlsx")
        db_path: Path to SQLite database
    """
    excel_path = Path(excel_file)
    if not excel_path.exists():
        print(f"❌ ERROR: File not found: {excel_file}")
        return False
    
    print("=" * 80)
    print(f"📊 IMPORTING SEASON DATA FROM: {excel_file}")
    print("=" * 80)
    print()
    
    try:
        # Read the Excel file (Snaps sheet)
        xls = pd.ExcelFile(excel_file)
        df = pd.read_excel(xls, sheet_name='Snaps')
        
        print(f"✅ Loaded {len(df)} player records from Excel")
        print()
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create season_stats table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS season_stats (
                player_name TEXT PRIMARY KEY,
                position TEXT,
                team TEXT,
                games_played INTEGER,
                snap_percentage_avg REAL,
                snap_percentage_std REAL,
                snap_percentage_trend REAL,
                fantasy_points_avg REAL,
                fantasy_points_std REAL,
                fantasy_points_trend REAL,
                season_ceiling REAL,
                last_updated TIMESTAMP,
                data_source TEXT
            )
        """)
        
        # Import data
        imported_count = 0
        updated_count = 0
        current_time = datetime.now().isoformat()
        
        for _, row in df.iterrows():
            player_name = row.get('Name')
            if pd.isna(player_name):
                continue
            
            # Extract relevant fields from Excel
            position = row.get('Position', '')
            team = row.get('Team', '')
            
            # Snap data
            snap_avg = row.get('Snap %', 0) or 0
            snap_std = row.get('Snap % Std', 0) or 0
            snap_trend = row.get('Snap Trend', 0) or 0
            
            # Fantasy points data
            fp_avg = row.get('FP/G', 0) or 0
            fp_std = row.get('FP Std', 0) or 0
            fp_trend = row.get('FP Trend', 0) or 0
            
            # Ceiling (max weekly score)
            ceiling = row.get('Season Ceiling', 0) or 0
            
            # Games played
            games = row.get('Games', 0) or 0
            
            # Check if player exists
            cursor.execute("SELECT player_name FROM season_stats WHERE player_name = ?", (player_name,))
            exists = cursor.fetchone()
            
            if exists:
                # Update existing record
                cursor.execute("""
                    UPDATE season_stats SET
                        position = ?,
                        team = ?,
                        games_played = ?,
                        snap_percentage_avg = ?,
                        snap_percentage_std = ?,
                        snap_percentage_trend = ?,
                        fantasy_points_avg = ?,
                        fantasy_points_std = ?,
                        fantasy_points_trend = ?,
                        season_ceiling = ?,
                        last_updated = ?,
                        data_source = ?
                    WHERE player_name = ?
                """, (position, team, games, snap_avg, snap_std, snap_trend,
                      fp_avg, fp_std, fp_trend, ceiling, current_time,
                      excel_file, player_name))
                updated_count += 1
            else:
                # Insert new record
                cursor.execute("""
                    INSERT INTO season_stats (
                        player_name, position, team, games_played,
                        snap_percentage_avg, snap_percentage_std, snap_percentage_trend,
                        fantasy_points_avg, fantasy_points_std, fantasy_points_trend,
                        season_ceiling, last_updated, data_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (player_name, position, team, games, snap_avg, snap_std, snap_trend,
                      fp_avg, fp_std, fp_trend, ceiling, current_time, excel_file))
                imported_count += 1
        
        conn.commit()
        conn.close()
        
        print(f"✅ Import complete!")
        print(f"   - New records: {imported_count}")
        print(f"   - Updated records: {updated_count}")
        print(f"   - Total: {imported_count + updated_count}")
        print()
        print(f"💾 Database updated: {db_path}")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR during import: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_season_data.py <excel_file>")
        print()
        print("Example:")
        print('  python scripts/import_season_data.py "2025 Stats thru week 5.xlsx"')
        sys.exit(1)
    
    excel_file = sys.argv[1]
    success = import_season_data(excel_file)
    
    if success:
        print("=" * 80)
        print("✅ NEXT STEPS:")
        print("=" * 80)
        print("1. Test the app locally to verify the data")
        print("2. Commit the updated database:")
        print("     git add dfs_optimizer.db")
        print('     git commit -m "Update season stats through week X"')
        print("3. Push to deploy:")
        print("     git push origin main")
        print("=" * 80)
        sys.exit(0)
    else:
        sys.exit(1)

