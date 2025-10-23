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
from .advanced_stats_loader import FileLoader, save_advanced_stats_to_database, load_advanced_stats_from_database

__all__ = [
    'parse_file',
    'load_and_validate_player_data',
    'detect_columns',
    'validate_required_columns',
    'validate_data_types',
    'validate_data_ranges',
    'get_data_quality_score',
    'Player',
    'FileLoader',
    'save_advanced_stats_to_database',
    'load_advanced_stats_from_database'
]

__version__ = '1.0.0'

