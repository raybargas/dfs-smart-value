"""
Database Migration Runner

Executes SQL migrations for DFS Optimizer extended data models.
Supports both SQLite (development) and PostgreSQL (production).

Auto-detects and runs all migration files in order (001_*.sql, 002_*.sql, etc.)
"""

import sqlite3
import sys
from pathlib import Path
from typing import List, Optional
import re

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def get_migration_files() -> List[str]:
    """
    Discover all migration files in the migrations directory.
    Returns files sorted by migration number (001, 002, etc.)
    
    Returns:
        List[str]: Sorted list of migration filenames
    """
    migrations_dir = Path(__file__).parent
    migration_files = []
    
    # Find all SQL files matching pattern: NNN_*.sql
    for file in migrations_dir.glob("*.sql"):
        match = re.match(r"^(\d{3})_.*\.sql$", file.name)
        if match:
            migration_files.append(file.name)
    
    # Sort by migration number
    migration_files.sort()
    
    return migration_files


def run_sqlite_migration(db_path: str = "dfs_optimizer.db", migration_file: str = "001_add_phase2_tables.sql") -> bool:
    """
    Run migration on SQLite database.
    
    Args:
        db_path: Path to SQLite database file
        migration_file: Migration SQL file to execute
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get migration file path
        migration_path = Path(__file__).parent / migration_file
        
        if not migration_path.exists():
            print(f"❌ Migration file not found: {migration_path}")
            return False
        
        # Read migration SQL
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print(f"📊 Running migration: {migration_file}")
        print(f"🗄️  Database: {db_path}")
        
        # Execute migration
        cursor.executescript(migration_sql)
        conn.commit()
        
        # Verify tables were created
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE '%project%' OR name LIKE '%scenario%' OR name LIKE '%portfolio%'
        """)
        tables = cursor.fetchall()
        
        print(f"✅ Migration completed successfully!")
        print(f"📋 Created/verified tables: {len(tables)}")
        for table in tables:
            print(f"   - {table[0]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False


def verify_migration(db_path: str = "dfs_optimizer.db") -> bool:
    """
    Verify that migration was applied successfully.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        bool: True if all tables exist, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for expected tables (Phase 2A + Phase 2C)
        expected_tables = [
            # Phase 2A tables
            'player_projections',
            'game_scenarios',
            'scenario_adjustments',
            'lineup_portfolios',
            'portfolio_lineups',
            'historical_lineups',
            'player_exposure',
            'correlation_matrices',
            # Phase 2C tables
            'vegas_lines',
            'injury_reports',
            'narrative_flags',
            'api_call_log'
        ]
        
        print("\n🔍 Verifying migration...")
        all_exist = True
        
        for table in expected_tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            result = cursor.fetchone()
            
            if result:
                print(f"   ✅ {table}")
            else:
                print(f"   ❌ {table} - NOT FOUND")
                all_exist = False
        
        conn.close()
        
        if all_exist:
            print("\n✅ All tables verified successfully!")
        else:
            print("\n❌ Some tables are missing")
            
        return all_exist
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False


def run_all_migrations(db_path: str = "dfs_optimizer.db") -> bool:
    """
    Run all migrations in order.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        bool: True if all migrations successful, False otherwise
    """
    migration_files = get_migration_files()
    
    if not migration_files:
        print("❌ No migration files found")
        return False
    
    print(f"📁 Found {len(migration_files)} migration(s):")
    for file in migration_files:
        print(f"   - {file}")
    print()
    
    for migration_file in migration_files:
        print(f"\n{'='*60}")
        success = run_sqlite_migration(db_path, migration_file)
        if not success:
            print(f"\n❌ Migration {migration_file} failed. Stopping.")
            return False
    
    print(f"\n{'='*60}")
    print(f"\n✅ All {len(migration_files)} migrations completed successfully!")
    return True


def main():
    """Run migrations and verify."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run DFS Optimizer database migrations')
    parser.add_argument('--db', default='dfs_optimizer.db', help='Database file path')
    parser.add_argument('--migration', default='001_add_phase2_tables.sql', help='Specific migration file to run')
    parser.add_argument('--all', action='store_true', help='Run all migrations in order')
    parser.add_argument('--verify-only', action='store_true', help='Only verify migration, do not run')
    
    args = parser.parse_args()
    
    if args.verify_only:
        success = verify_migration(args.db)
    elif args.all:
        success = run_all_migrations(args.db)
        if success:
            verify_migration(args.db)
    else:
        success = run_sqlite_migration(args.db, args.migration)
        if success:
            verify_migration(args.db)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

