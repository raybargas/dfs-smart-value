"""
Data Validation Module

This module validates data quality and completeness for the DFS Lineup Optimizer.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any


def validate_required_columns(df: pd.DataFrame) -> None:
    """
    Validate that all required columns are present.
    
    Args:
        df: DataFrame with standardized column names
        
    Raises:
        KeyError: If required column missing with helpful error message
    """
    required_columns = ['name', 'position', 'salary', 'projection']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        # Convert column names to strings for display
        column_names = [str(col) for col in df.columns.tolist()]
        raise KeyError(
            f"Missing required columns: {', '.join(missing_columns)}.\n"
            f"Expected columns: {', '.join(required_columns)}\n"
            f"Your file has: {', '.join(column_names)}"
        )


def validate_data_types(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Validate data types for each column.
    
    Checks that numeric columns contain valid numeric values.
    
    Args:
        df: DataFrame with standardized column names
        
    Returns:
        list[dict]: List of validation issues, each containing:
            - row: Row number (1-indexed)
            - column: Column name
            - issue: Description of the issue
    """
    issues = []
    
    # Check salary is integer
    if 'salary' in df.columns:
        non_int_rows = df[~df['salary'].apply(lambda x: isinstance(x, (int, np.integer)))].index
        for row in non_int_rows:
            issues.append({
                'row': int(row + 1),
                'column': 'salary',
                'issue': f"Invalid salary: {df.loc[row, 'salary']} (must be an integer)"
            })
    
    # Check projection is numeric
    if 'projection' in df.columns:
        non_numeric_rows = df[~df['projection'].apply(
            lambda x: isinstance(x, (int, float, np.number)) and not pd.isna(x)
        )].index
        for row in non_numeric_rows:
            issues.append({
                'row': int(row + 1),
                'column': 'projection',
                'issue': f"Invalid projection: {df.loc[row, 'projection']} (must be a number)"
            })
    
    # Check ownership is numeric (if present)
    if 'ownership' in df.columns:
        non_numeric_rows = df[
            ~df['ownership'].apply(lambda x: isinstance(x, (int, float, np.number)) or pd.isna(x))
        ].index
        for row in non_numeric_rows:
            issues.append({
                'row': int(row + 1),
                'column': 'ownership',
                'issue': f"Invalid ownership: {df.loc[row, 'ownership']} (must be a number)"
            })
    
    return issues


def validate_data_ranges(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Validate data values are within expected ranges.
    
    Checks business logic constraints like valid positions, salary ranges,
    and projection values.
    
    Args:
        df: DataFrame with standardized column names
        
    Returns:
        list[dict]: List of validation issues
    """
    issues = []
    
    # Validate position values
    valid_positions = ['QB', 'RB', 'WR', 'TE', 'DST', 'D/ST', 'DEF']
    if 'position' in df.columns:
        invalid_positions = df[~df['position'].isin(valid_positions)]
        for idx, row in invalid_positions.iterrows():
            issues.append({
                'row': int(idx + 1),
                'column': 'position',
                'issue': (
                    f"Invalid position: '{row['position']}'. "
                    f"Must be one of: {', '.join(valid_positions)}"
                )
            })
    
    # Validate salary range (DraftKings typical range)
    if 'salary' in df.columns:
        invalid_salaries = df[(df['salary'] < 2000) | (df['salary'] > 10000)]
        for idx, row in invalid_salaries.iterrows():
            issues.append({
                'row': int(idx + 1),
                'column': 'salary',
                'issue': f"Salary ${row['salary']:,} out of range ($2,000 - $10,000)"
            })
    
    # Validate projection is positive
    if 'projection' in df.columns:
        invalid_projections = df[df['projection'] <= 0]
        for idx, row in invalid_projections.iterrows():
            issues.append({
                'row': int(idx + 1),
                'column': 'projection',
                'issue': f"Projection {row['projection']} must be positive"
            })
    
    # Validate ownership percentage (if present)
    if 'ownership' in df.columns:
        # Filter out NaN values for ownership (it's optional)
        ownership_data = df[df['ownership'].notna()]
        invalid_ownership = ownership_data[
            (ownership_data['ownership'] < 0) | (ownership_data['ownership'] > 100)
        ]
        for idx, row in invalid_ownership.iterrows():
            issues.append({
                'row': int(idx + 1),
                'column': 'ownership',
                'issue': f"Ownership {row['ownership']}% must be between 0-100"
            })
    
    return issues


def get_data_quality_score(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate overall data quality metrics.
    
    Aggregates all validation issues and computes a quality score
    as percentage of valid rows.
    
    Args:
        df: DataFrame with standardized column names
        
    Returns:
        dict: Quality metrics containing:
            - total_rows: Total number of rows
            - valid_rows: Number of rows without issues
            - quality_percentage: Percentage of valid rows (0-100)
            - issues: List of all validation issues found
    """
    # Collect all validation issues
    type_issues = validate_data_types(df)
    range_issues = validate_data_ranges(df)
    all_issues = type_issues + range_issues
    
    # Calculate quality metrics
    total_rows = len(df)
    rows_with_issues = len(set(issue['row'] for issue in all_issues))
    valid_rows = total_rows - rows_with_issues
    quality_percentage = (valid_rows / total_rows * 100) if total_rows > 0 else 0
    
    return {
        'total_rows': total_rows,
        'valid_rows': valid_rows,
        'quality_percentage': round(quality_percentage, 1),
        'issues': all_issues
    }

