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
# Multiple detection methods for robustness
def _get_db_path():
    """
    Determine the correct database path for current environment.
    
    Streamlit Cloud detection (in priority order):
    1. Check for /mount/src/ directory (always exists in Streamlit Cloud)
    2. Check STREAMLIT_SHARING_MODE environment variable
    3. Fall back to local development path
    """
    # Method 1: Check if we're in Streamlit Cloud (more reliable)
    if os.path.exists("/mount/src"):
        # Use home directory for persistent storage (writable)
        persistent_dir = Path.home() / ".streamlit" / "data"
        persistent_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(persistent_dir / "dfs_optimizer.db")
        print(f"🌐 Streamlit Cloud detected - Using persistent storage: {db_path}")
        return db_path
    
    # Method 2: Check environment variable
    if os.getenv("STREAMLIT_SHARING_MODE") == "true":
        persistent_dir = Path.home() / ".streamlit" / "data"
        persistent_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(persistent_dir / "dfs_optimizer.db")
        print(f"🌐 Streamlit Cloud (env var) - Using persistent storage: {db_path}")
        return db_path
    
    # Method 3: Local development
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

