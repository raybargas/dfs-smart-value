"""
DFS Lineup Optimizer - Data Ingestion Component

This package provides data ingestion, parsing, validation, and modeling
for DFS lineup optimization.
"""

from .parser import parse_file, load_and_validate_player_data, detect_columns
from .validator import (
    validate_required_columns,
    validate_data_types,
    validate_data_ranges,
    get_data_quality_score
)
from .models import Player

# Advanced stats loader imports - only import when needed to avoid circular dependencies
try:
    from .advanced_stats_loader import FileLoader, save_advanced_stats_to_database, load_advanced_stats_from_database
    _ADVANCED_STATS_AVAILABLE = True
except ImportError:
    # Fallback if advanced_stats_loader has import issues
    _ADVANCED_STATS_AVAILABLE = False
    FileLoader = None
    save_advanced_stats_to_database = None
    load_advanced_stats_from_database = None

__all__ = [
    'parse_file',
    'load_and_validate_player_data',
    'detect_columns',
    'validate_required_columns',
    'validate_data_types',
    'validate_data_ranges',
    'get_data_quality_score',
    'Player',
]

# Only add advanced stats exports if successfully imported
if _ADVANCED_STATS_AVAILABLE:
    __all__.extend(['FileLoader', 'save_advanced_stats_to_database', 'load_advanced_stats_from_database'])

__version__ = '1.0.0'

