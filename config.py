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

# Use Streamlit Cloud persistent storage if available, otherwise local
# Streamlit Cloud provides /mount/src/.streamlit/ for persistent data
if os.path.exists("/mount/src/.streamlit"):
    # Production: Use persistent storage directory
    PERSISTENT_DIR = Path("/mount/src/.streamlit/data")
    PERSISTENT_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_DB_PATH = str(PERSISTENT_DIR / "dfs_optimizer.db")
else:
    # Local development: Use current directory
    DEFAULT_DB_PATH = "dfs_optimizer.db"

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

