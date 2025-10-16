"""
Data Ingestion Parser Module

This module handles file upload, column detection, and DataFrame creation
for the DFS Lineup Optimizer.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
from pathlib import Path


def detect_and_standardize_data_source(df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    """
    Detect data source format and standardize to internal format.
    
    Supports:
    - Linestar: Professional projections with ceiling/floor, ownership, consistency
    - DraftKings: Standard CSV format
    
    Args:
        df: Raw DataFrame from file
        
    Returns:
        Tuple of (standardized_df, source_type)
        source_type: 'linestar' or 'draftkings'
    """
    # Detect Linestar format
    linestar_signature_cols = ['LineStarId', 'Ceiling', 'Floor', 'ProjOwn', 'Consistency']
    if all(col in df.columns for col in linestar_signature_cols):
        return standardize_linestar(df), 'linestar'
    
    # Detect DraftKings or generic format
    elif 'Name' in df.columns and 'Salary' in df.columns:
        return standardize_draftkings(df), 'draftkings'
    
    # Unknown format - treat as DraftKings and let column detection handle it
    else:
        return standardize_draftkings(df), 'draftkings'


def standardize_linestar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Map Linestar columns to internal format and preserve rich data.
    
    Linestar provides professional-grade data:
    - Projected: Pro projection
    - ProjOwn: Real ownership projections
    - Ceiling/Floor: Accurate GPP ranges
    - Consistency: 0-100 reliability score
    - OppRank: Position-specific matchup quality
    
    Args:
        df: Raw Linestar DataFrame
        
    Returns:
        pd.DataFrame: Standardized format with Linestar enhancements
    """
    standardized = pd.DataFrame()
    
    # Core columns (required by app)
    standardized['player_name'] = df['Name']
    standardized['name'] = df['Name']  # Alias for compatibility
    standardized['position'] = df['Position']
    standardized['team'] = df['Team']
    standardized['salary'] = df['Salary']
    standardized['projection'] = df['Projected']  # Professional projection!
    standardized['ownership'] = df['ProjOwn']     # Real ownership data!
    
    # Enhanced columns (Linestar-specific advantages)
    standardized['ceiling'] = df['Ceiling']           # Pro ceiling estimate
    standardized['floor'] = df['Floor']               # Floor for safety calc
    standardized['consistency'] = df['Consistency']   # 0-100 reliability score
    standardized['opp_rank'] = df['OppRank']         # Opponent rank vs position
    standardized['opponent'] = df['VersusStr']        # Matchup detail string
    standardized['ppg'] = df['PPG']                   # Points per game avg
    
    # Vegas data (may already have via API, but good to preserve)
    if 'VegasImplied' in df.columns:
        standardized['implied_total'] = df['VegasImplied']
    if 'Vegas' in df.columns:
        standardized['vegas_spread'] = df['Vegas']
    if 'VegasML' in df.columns:
        standardized['vegas_ml'] = df['VegasML']
    if 'VegasTotals' in df.columns:
        standardized['vegas_total'] = df['VegasTotals']
    
    # Linestar-specific metrics (for advanced analysis)
    if 'Leverage' in df.columns:
        standardized['linestar_leverage'] = df['Leverage']
    if 'Safety' in df.columns:
        standardized['linestar_safety'] = df['Safety']
    if 'StartingStatus' in df.columns:
        standardized['starting_status'] = df['StartingStatus']
    if 'LineStarId' in df.columns:
        standardized['linestar_id'] = df['LineStarId']
    
    return standardized


def standardize_draftkings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize DraftKings/generic CSV format.
    
    Adds defaults for Linestar-specific columns to maintain
    compatibility across both data sources.
    
    Args:
        df: Raw DraftKings DataFrame
        
    Returns:
        pd.DataFrame: Standardized format with estimated values
    """
    standardized = df.copy()
    
    # Add Linestar-specific columns with estimated defaults
    # (These will be overridden if they exist in the source data)
    
    if 'ceiling' not in standardized.columns:
        # Estimate ceiling as 1.5x projection (rough GPP upside estimate)
        if 'projection' in standardized.columns:
            standardized['ceiling'] = standardized['projection'] * 1.5
        elif 'Projection' in standardized.columns:
            standardized['ceiling'] = standardized['Projection'] * 1.5
    
    if 'floor' not in standardized.columns:
        # Estimate floor as 0.5x projection (rough downside estimate)
        if 'projection' in standardized.columns:
            standardized['floor'] = standardized['projection'] * 0.5
        elif 'Projection' in standardized.columns:
            standardized['floor'] = standardized['Projection'] * 0.5
    
    if 'consistency' not in standardized.columns:
        # Default to 70 (neutral consistency score)
        standardized['consistency'] = 70.0
    
    if 'ownership' not in standardized.columns:
        # Default to 10% ownership (current behavior)
        standardized['ownership'] = 10.0
    
    # Mark as non-Linestar source
    standardized['linestar_id'] = None
    
    return standardized


def parse_file(uploaded_file: Any) -> pd.DataFrame:
    """
    Main entry point for file parsing.
    
    Accepts CSV and Excel files, detects column names, and returns
    a standardized DataFrame with validated structure.
    
    Supports multiple data sources:
    - Linestar (professional projections, ownership, ceiling/floor)
    - DraftKings (standard CSV format)
    
    Args:
        uploaded_file: Streamlit UploadedFile object or file-like object
        
    Returns:
        pd.DataFrame: Parsed player data with standardized column names
        
    Raises:
        ValueError: If file format unsupported
        pd.errors.ParserError: If file malformed
        KeyError: If required columns missing
    """
    from validator import validate_required_columns
    
    # 1. Detect file type from extension
    file_extension = get_file_extension(uploaded_file.name)
    
    # 2. Read file based on type
    if file_extension == '.csv':
        df = pd.read_csv(uploaded_file)
    elif file_extension in ['.xlsx', '.xls']:
        # Try reading with default header first
        df = pd.read_excel(uploaded_file)
        
        # If columns are mostly "Unnamed", try reading with header in row 1
        unnamed_count = sum(1 for col in df.columns if str(col).startswith('Unnamed'))
        if unnamed_count > len(df.columns) * 0.5:  # More than 50% unnamed
            # Seek back to beginning before re-reading
            if hasattr(uploaded_file, 'seek'):
                uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file, header=1)
            # Reset index to avoid alignment issues
            df = df.reset_index(drop=True)
    else:
        raise ValueError(
            f"Unsupported file format: {file_extension}. "
            f"Supported formats: CSV (.csv), Excel (.xlsx, .xls)"
        )
    
    # 3. Detect data source (Linestar vs DraftKings) and standardize
    df, data_source = detect_and_standardize_data_source(df)
    
    # Store data source in DataFrame for UI display
    df.attrs['data_source'] = data_source
    
    # 4. Detect and normalize column names (for non-Linestar sources)
    if data_source != 'linestar':
        column_mapping = detect_columns(df)
        df = df.rename(columns=column_mapping)
    
    # 5. Validate required columns present
    validate_required_columns(df)
    
    # 6. Convert data types
    df = convert_data_types(df)
    
    return df


def get_file_extension(filename: str) -> str:
    """
    Extract file extension from filename.
    
    Args:
        filename: Name of the uploaded file
        
    Returns:
        str: File extension (e.g., '.csv', '.xlsx')
    """
    return Path(filename).suffix.lower()


def detect_columns(df: pd.DataFrame) -> Dict[str, str]:
    """
    Auto-detect column names despite variations.
    
    Uses fuzzy matching to map common column name variations to
    standardized names expected by downstream components.
    
    Args:
        df: Raw DataFrame with original column names
        
    Returns:
        dict: Mapping of {original_column_name: standardized_name}
        
    Example:
        Input columns: ['Player Name', 'Pos', 'Salary', 'Proj']
        Output: {'Player Name': 'name', 'Pos': 'position', 'Salary': 'salary', 'Proj': 'projection'}
    """
    # Define patterns for each standard column name
    column_patterns = {
        'name': ['name', 'player', 'player name', 'player_name', 'playername'],
        'position': ['position', 'pos', 'position_abbr', 'roster position'],
        'salary': ['salary', 'cost', 'price', 'sal', 's'],
        'projection': ['projection', 'proj', 'fppg', 'points', 'projected_points', 
                       'projectedpoints', 'avgpointspergame', 'avg points per game'],
        'team': ['team', 'tm', 'teamabbrev', 'team_abbr', 'team abbrev', 't'],
        'opponent': ['opponent', 'opp', 'vs', 'matchup', 'oppo'],
        'ownership': ['ownership', 'own', 'own%', 'own_pct', 'projected_ownership',
                      'projectedownership', 'own pct'],
        'player_id': ['id', 'player_id', 'playerid', 'dk_id', 'draftkings_id', 
                      'draftkingsid', 'player id']
    }
    
    mapping = {}
    
    # Iterate through each column in the DataFrame
    for col in df.columns:
        # Convert to string in case column name is numeric
        col_str = str(col) if not isinstance(col, str) else col
        col_lower = col_str.lower().strip()
        
        # Try to match against standard patterns
        for standard_name, patterns in column_patterns.items():
            if col_lower in patterns:
                mapping[col] = standard_name
                break
    
    return mapping


def convert_data_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert columns to correct data types.
    
    Ensures numeric columns are properly typed and string columns
    are cleaned of leading/trailing whitespace.
    
    Args:
        df: DataFrame with standardized column names
        
    Returns:
        pd.DataFrame: DataFrame with converted types
        
    Raises:
        ValueError: If column cannot be converted to expected type
    """
    # Define type conversions for numeric columns
    type_conversions = {
        'salary': 'int64',
        'projection': 'float64',
        'ownership': 'float64'
    }
    
    # Convert numeric columns
    for col, dtype in type_conversions.items():
        if col in df.columns:
            try:
                # Handle potential dollar signs or commas in salary
                if col == 'salary':
                    df[col] = df[col].astype(str).str.replace('$', '').str.replace(',', '')
                df[col] = df[col].astype(dtype)
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Cannot convert column '{col}' to {dtype}. "
                    f"Please ensure all values are valid numbers. Error: {e}"
                )
    
    # Clean string columns
    string_columns = ['name', 'position', 'team', 'opponent', 'player_id']
    for col in string_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    
    return df


def load_and_validate_player_data(uploaded_file: Any) -> tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Main entry point for data ingestion component.
    
    Parses file, validates data, and generates summary statistics.
    
    Args:
        uploaded_file: Streamlit UploadedFile object
    
    Returns:
        tuple: (DataFrame, summary_dict)
            - DataFrame: Validated player data
            - summary_dict: {
                'total_players': 250,
                'position_breakdown': {'QB': 32, 'RB': 64, ...},
                'salary_range': (3000, 10000),
                'quality_score': 98.0,
                'issues': [...]
              }
    
    Raises:
        ValueError: If file format unsupported
        KeyError: If required columns missing
        pd.errors.ParserError: If file malformed
    """
    from validator import get_data_quality_score
    
    # Parse file
    df = parse_file(uploaded_file)
    
    # Validate and get quality info
    quality_info = get_data_quality_score(df)
    
    # Generate summary statistics
    summary = {
        'total_players': len(df),
        'position_breakdown': df['position'].value_counts().to_dict() if 'position' in df.columns else {},
        'salary_range': (int(df['salary'].min()), int(df['salary'].max())) if 'salary' in df.columns else (0, 0),
        'quality_score': quality_info['quality_percentage'],
        'issues': quality_info['issues']
    }
    
    return df, summary

