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

__all__ = [
    'parse_file',
    'load_and_validate_player_data',
    'detect_columns',
    'validate_required_columns',
    'validate_data_types',
    'validate_data_ranges',
    'get_data_quality_score',
    'Player'
]

__version__ = '1.0.0'

