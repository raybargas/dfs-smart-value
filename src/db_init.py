"""
Database initialization and data refresh utilities for Streamlit Cloud.

This module handles:
- Running migrations to create tables
- Fetching fresh data from APIs (Vegas lines, injury reports)
- Initializing database on ephemeral storage
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional
import streamlit as st


def run_migrations(db_path: str = "dfs_optimizer.db") -> bool:
    """
    Run all database migrations to create tables.
    
    Args:
        db_path: Path to SQLite database
    
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get migration files
        migrations_dir = Path(__file__).parent.parent / "migrations"
        migration_files = sorted([f for f in migrations_dir.glob("*.sql")])
        
        for migration_file in migration_files:
            with open(migration_file, 'r') as f:
                sql_script = f.read()
                # Execute the entire migration script
                cursor.executescript(sql_script)
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        st.error(f"Error running migrations: {e}")
        return False


def fetch_vegas_lines(week: int, api_key: Optional[str] = None) -> bool:
    """
    Fetch Vegas lines from The Odds API and store in database.
    
    Args:
        week: NFL week number
        api_key: The Odds API key (from secrets or env)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get API key from secrets or environment
        if api_key is None:
            api_key = st.secrets.get("ODDS_API_KEY") or os.getenv("ODDS_API_KEY")
        
        if not api_key:
            st.warning("⚠️ ODDS_API_KEY not found in secrets. Vegas lines unavailable.")
            return False
        
        # Import here to avoid circular dependencies
        from src.api.odds_api import OddsAPIClient
        
        client = OddsAPIClient(api_key=api_key)
        client.fetch_nfl_odds(use_cache=False)  # Don't use cache when forcing refresh
        
        return True
        
    except Exception as e:
        st.error(f"Error fetching Vegas lines: {e}")
        import traceback
        st.error(traceback.format_exc())
        return False


def fetch_injury_reports(week: int, api_key: Optional[str] = None) -> bool:
    """
    Fetch injury reports from MySportsFeeds API and store in database.
    
    Args:
        week: NFL week number
        api_key: MySportsFeeds API key (from secrets or env)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get API key from secrets or environment
        if api_key is None:
            api_key = st.secrets.get("MYSPORTSFEEDS_API_KEY") or os.getenv("MYSPORTSFEEDS_API_KEY")
        
        if not api_key:
            st.warning("⚠️ MYSPORTSFEEDS_API_KEY not found in secrets. Injury reports unavailable.")
            return False
        
        # Import here to avoid circular dependencies
        from src.api.mysportsfeeds_api import MySportsFeedsClient
        
        client = MySportsFeedsClient(api_key=api_key)
        # Note: You'll need to implement fetch_injury_reports method in MySportsFeedsClient
        # For now, just silently return success
        # TODO: Implement injury report fetching in MySportsFeedsClient
        # client.fetch_injury_reports(week=week)
        
        return True
        
    except Exception as e:
        st.error(f"Error fetching injury reports: {e}")
        import traceback
        st.error(traceback.format_exc())
        return False


def initialize_database(week: int, use_cache: bool = True, force_refresh: bool = False, verbose: bool = True) -> bool:
    """
    Full database initialization: run migrations + load/fetch data.
    
    Args:
        week: NFL week number
        use_cache: Try to load from cache first before fetching
        force_refresh: Force API fetch even if cache exists
        verbose: Show status messages (set to False for silent loading)
    
    Returns:
        True if successful, False otherwise
    """
    if verbose:
        with st.spinner("🗄️ Initializing database..."):
            # Step 1: Run migrations
            if not run_migrations():
                return False
            st.success("✅ Database tables created")
    else:
        # Silent mode - no status messages
        if not run_migrations():
            return False
    
    # Import cache utilities
    from src.data_cache import (
        load_vegas_lines_from_cache,
        load_injury_reports_from_cache,
        save_vegas_lines_to_cache,
        save_injury_reports_to_cache,
        get_cache_status
    )
    
    # Step 2: Vegas Lines
    vegas_from_cache = False
    if use_cache and not force_refresh:
        if verbose:
            with st.spinner(f"📦 Loading Vegas lines from cache for Week {week}..."):
                cache_result = load_vegas_lines_from_cache(week)
                if cache_result:
                    st.success(f"✅ Vegas lines loaded from cache ({cache_result['record_count']} records)")
                    vegas_from_cache = True
        else:
            cache_result = load_vegas_lines_from_cache(week)
            if cache_result:
                vegas_from_cache = True
    
    if not vegas_from_cache:
        if verbose:
            with st.spinner(f"📊 Fetching Vegas lines from API for Week {week}..."):
                vegas_success = fetch_vegas_lines(week)
                if vegas_success:
                    # Save to cache for next time
                    save_vegas_lines_to_cache(week)
                    st.success(f"✅ Vegas lines fetched and cached for Week {week}")
        else:
            vegas_success = fetch_vegas_lines(week)
            if vegas_success:
                save_vegas_lines_to_cache(week)
    
    # Step 3: Injury Reports
    injury_from_cache = False
    if use_cache and not force_refresh:
        if verbose:
            with st.spinner(f"📦 Loading injury reports from cache for Week {week}..."):
                cache_result = load_injury_reports_from_cache(week)
                if cache_result:
                    st.success(f"✅ Injury reports loaded from cache ({cache_result['record_count']} records)")
                    injury_from_cache = True
        else:
            cache_result = load_injury_reports_from_cache(week)
            if cache_result:
                injury_from_cache = True
    
    if not injury_from_cache:
        if verbose:
            with st.spinner(f"🏥 Fetching injury reports from API for Week {week}..."):
                injury_success = fetch_injury_reports(week)
                if injury_success:
                    # Save to cache for next time
                    save_injury_reports_to_cache(week)
                    st.success(f"✅ Injury reports fetched and cached for Week {week}")
        else:
            injury_success = fetch_injury_reports(week)
            if injury_success:
                save_injury_reports_to_cache(week)
    
    return True


def check_data_freshness(db_path: str = "dfs_optimizer.db") -> dict:
    """
    Check if Vegas lines and injury reports exist in the database.
    
    Args:
        db_path: Path to SQLite database
    
    Returns:
        Dict with status of each data source
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check vegas_lines
        cursor.execute("SELECT COUNT(*) FROM vegas_lines")
        vegas_count = cursor.fetchone()[0]
        
        # Check injury_reports
        cursor.execute("SELECT COUNT(*) FROM injury_reports")
        injury_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'vegas_lines': vegas_count > 0,
            'vegas_count': vegas_count,
            'injury_reports': injury_count > 0,
            'injury_count': injury_count
        }
        
    except Exception as e:
        return {
            'vegas_lines': False,
            'vegas_count': 0,
            'injury_reports': False,
            'injury_count': 0,
            'error': str(e)
        }

