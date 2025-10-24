"""
DFS Lineup Optimizer - Configuration

Single source of truth for app-wide configuration settings.
"""

# ============================================================================
# CURRENT NFL WEEK - UPDATE THIS WEEKLY
# ============================================================================
DEFAULT_NFL_WEEK = 8  # Current NFL week - update this each week

# ============================================================================
# Season Configuration
# ============================================================================
CURRENT_SEASON = 2025
SEASON_LABEL = "2025-2026-regular"

# ============================================================================
# DFS Site Configuration
# ============================================================================
DEFAULT_SITE = "DraftKings"

# ============================================================================
# Week Range
# ============================================================================
MIN_WEEK = 1
MAX_WEEK = 18

# ============================================================================
# Database Configuration
# ============================================================================
import os
from pathlib import Path

# Detect Streamlit Cloud environment and use appropriate persistent storage
# Aggressive detection with multiple fallback methods
def _get_db_path():
    """
    Determine the correct database path for current environment.
    
    Uses aggressive detection to ensure Streamlit Cloud is always recognized.
    Tries persistent storage first, falls back to ephemeral only if it fails.
    """
    # Method 1: Check HOME directory (most reliable for Streamlit Cloud)
    home_dir = os.getenv("HOME", "")
    if home_dir == "/home/appuser" or "/home/appuser" in home_dir:
        persistent_dir = Path.home() / ".streamlit" / "data"
        persistent_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(persistent_dir / "dfs_optimizer.db")
        print(f"🌐 Streamlit Cloud detected (HOME={home_dir}) - Using: {db_path}")
        return db_path
    
    # Method 2: Check for /mount/src/ directory
    if os.path.exists("/mount/src"):
        persistent_dir = Path.home() / ".streamlit" / "data"
        persistent_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(persistent_dir / "dfs_optimizer.db")
        print(f"🌐 Streamlit Cloud detected (/mount/src) - Using: {db_path}")
        return db_path
    
    # Method 3: Check environment variable
    if os.getenv("STREAMLIT_SHARING_MODE") == "true":
        persistent_dir = Path.home() / ".streamlit" / "data"
        persistent_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(persistent_dir / "dfs_optimizer.db")
        print(f"🌐 Streamlit Cloud detected (env var) - Using: {db_path}")
        return db_path
    
    # Method 4: Try persistent path anyway (works if home directory is writable)
    try:
        persistent_dir = Path.home() / ".streamlit" / "data"
        persistent_dir.mkdir(parents=True, exist_ok=True)
        # Test if writable
        test_file = persistent_dir / ".test_write"
        test_file.touch()
        test_file.unlink()
        db_path = str(persistent_dir / "dfs_optimizer.db")
        print(f"📁 Using persistent home directory: {db_path}")
        return db_path
    except Exception as e:
        print(f"⚠️  Persistent storage not available ({e}), using ephemeral")
    
    # Method 5: Local development fallback
    db_path = "dfs_optimizer.db"
    print(f"💻 Local development - Using: {db_path}")
    return db_path

DEFAULT_DB_PATH = _get_db_path()

# ============================================================================
# API Configuration
# ============================================================================
API_TIMEOUT = 30  # seconds
API_RETRY_ATTEMPTS = 3

# ============================================================================
# Optimization Configuration
# ============================================================================
DEFAULT_LINEUP_COUNT = 20
MAX_LINEUP_COUNT = 150
DEFAULT_SALARY_CAP = 50000

# ============================================================================
# File Upload Configuration
# ============================================================================
MAX_FILE_SIZE_MB = 200
ALLOWED_FILE_TYPES = ['csv', 'xlsx', 'xls']

# ============================================================================
# Advanced Stats Configuration
# ============================================================================
SEASON_STATS_DIR = "seasonStats"
ADVANCED_STATS_MIN_RECORDS = 10  # Minimum records to consider file "loaded"

