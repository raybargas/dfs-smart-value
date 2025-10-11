"""
Unit Tests for Validator Module

Tests data validation logic and quality scoring.
"""

import pytest
import pandas as pd
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from validator import (
    validate_required_columns,
    validate_data_types,
    validate_data_ranges,
    get_data_quality_score
)


class TestValidateRequiredColumns:
    """Test required column validation."""
    
    def test_all_required_columns_present(self, valid_dataframe):
        """Test validation passes when all required columns present."""
        # Should not raise an exception
        validate_required_columns(valid_dataframe)
    
    def test_missing_name_column(self):
        """Test validation fails when name column missing."""
        df = pd.DataFrame({
            'position': ['QB'],
            'salary': [8500],
            'projection': [24.2]
        })
        
        with pytest.raises(KeyError) as excinfo:
            validate_required_columns(df)
        
        assert 'name' in str(excinfo.value).lower()
    
    def test_missing_position_column(self):
        """Test validation fails when position column missing."""
        df = pd.DataFrame({
            'name': ['Patrick Mahomes'],
            'salary': [8500],
            'projection': [24.2]
        })
        
        with pytest.raises(KeyError) as excinfo:
            validate_required_columns(df)
        
        assert 'position' in str(excinfo.value).lower()
    
    def test_missing_multiple_columns(self):
        """Test validation reports all missing columns."""
        df = pd.DataFrame({
            'name': ['Patrick Mahomes'],
            'salary': [8500]
        })
        
        with pytest.raises(KeyError) as excinfo:
            validate_required_columns(df)
        
        error_msg = str(excinfo.value).lower()
        assert 'position' in error_msg
        assert 'projection' in error_msg


class TestValidateDataTypes:
    """Test data type validation."""
    
    def test_valid_data_types(self, valid_dataframe):
        """Test no issues with valid data types."""
        issues = validate_data_types(valid_dataframe)
        assert len(issues) == 0
    
    def test_invalid_salary_type(self):
        """Test detection of invalid salary data type."""
        df = pd.DataFrame({
            'name': ['Player 1'],
            'position': ['QB'],
            'salary': ['not a number'],
            'projection': [20.0]
        })
        
        issues = validate_data_types(df)
        assert len(issues) > 0
        assert any('salary' in issue['column'] for issue in issues)
    
    def test_invalid_projection_type(self):
        """Test detection of invalid projection data type."""
        df = pd.DataFrame({
            'name': ['Player 1'],
            'position': ['QB'],
            'salary': [8500],
            'projection': ['invalid']
        })
        
        issues = validate_data_types(df)
        assert len(issues) > 0
        assert any('projection' in issue['column'] for issue in issues)
    
    def test_invalid_ownership_type(self):
        """Test detection of invalid ownership data type."""
        df = pd.DataFrame({
            'name': ['Player 1'],
            'position': ['QB'],
            'salary': [8500],
            'projection': [20.0],
            'ownership': ['invalid']
        })
        
        issues = validate_data_types(df)
        assert len(issues) > 0
        assert any('ownership' in issue['column'] for issue in issues)
    
    def test_issue_includes_row_number(self, valid_dataframe):
        """Test issues include 1-indexed row numbers."""
        df = valid_dataframe.copy()
        df.loc[1, 'salary'] = 'invalid'
        
        issues = validate_data_types(df)
        assert len(issues) > 0
        assert issues[0]['row'] == 2  # Row 2 (1-indexed)


class TestValidateDataRanges:
    """Test data range validation."""
    
    def test_valid_data_ranges(self, valid_dataframe):
        """Test no issues with valid data ranges."""
        issues = validate_data_ranges(valid_dataframe)
        assert len(issues) == 0
    
    def test_invalid_position(self):
        """Test detection of invalid position values."""
        df = pd.DataFrame({
            'name': ['Player 1'],
            'position': ['WR1'],  # Invalid
            'salary': [8500],
            'projection': [20.0]
        })
        
        issues = validate_data_ranges(df)
        assert len(issues) > 0
        assert any('position' in issue['column'] for issue in issues)
        assert any('WR1' in issue['issue'] for issue in issues)
    
    def test_valid_position_variations(self):
        """Test D/ST and DEF are valid position values."""
        df1 = pd.DataFrame({
            'name': ['Defense 1'],
            'position': ['D/ST'],
            'salary': [3500],
            'projection': [12.0]
        })
        
        df2 = pd.DataFrame({
            'name': ['Defense 2'],
            'position': ['DEF'],
            'salary': [3500],
            'projection': [12.0]
        })
        
        assert len(validate_data_ranges(df1)) == 0
        assert len(validate_data_ranges(df2)) == 0
    
    def test_salary_too_low(self):
        """Test detection of salary below minimum."""
        df = pd.DataFrame({
            'name': ['Player 1'],
            'position': ['QB'],
            'salary': [1500],  # Too low (below $2,000 minimum)
            'projection': [20.0]
        })
        
        issues = validate_data_ranges(df)
        assert len(issues) > 0
        assert any('salary' in issue['column'] for issue in issues)
        assert any('1500' in issue['issue'] or '1,500' in issue['issue'] for issue in issues)
    
    def test_salary_too_high(self):
        """Test detection of salary above maximum."""
        df = pd.DataFrame({
            'name': ['Player 1'],
            'position': ['QB'],
            'salary': [15000],  # Too high
            'projection': [20.0]
        })
        
        issues = validate_data_ranges(df)
        assert len(issues) > 0
        assert any('salary' in issue['column'] for issue in issues)
    
    def test_negative_projection(self):
        """Test detection of negative projections."""
        df = pd.DataFrame({
            'name': ['Player 1'],
            'position': ['QB'],
            'salary': [8500],
            'projection': [-5.0]  # Invalid
        })
        
        issues = validate_data_ranges(df)
        assert len(issues) > 0
        assert any('projection' in issue['column'] for issue in issues)
    
    def test_zero_projection(self):
        """Test detection of zero projections."""
        df = pd.DataFrame({
            'name': ['Player 1'],
            'position': ['QB'],
            'salary': [8500],
            'projection': [0.0]  # Invalid
        })
        
        issues = validate_data_ranges(df)
        assert len(issues) > 0
        assert any('projection' in issue['column'] for issue in issues)
    
    def test_ownership_out_of_range_low(self):
        """Test detection of ownership below 0%."""
        df = pd.DataFrame({
            'name': ['Player 1'],
            'position': ['QB'],
            'salary': [8500],
            'projection': [20.0],
            'ownership': [-10.0]  # Invalid
        })
        
        issues = validate_data_ranges(df)
        assert len(issues) > 0
        assert any('ownership' in issue['column'] for issue in issues)
    
    def test_ownership_out_of_range_high(self):
        """Test detection of ownership above 100%."""
        df = pd.DataFrame({
            'name': ['Player 1'],
            'position': ['QB'],
            'salary': [8500],
            'projection': [20.0],
            'ownership': [150.0]  # Invalid
        })
        
        issues = validate_data_ranges(df)
        assert len(issues) > 0
        assert any('ownership' in issue['column'] for issue in issues)
    
    def test_ownership_nan_allowed(self):
        """Test NaN ownership values are allowed (optional field)."""
        df = pd.DataFrame({
            'name': ['Player 1'],
            'position': ['QB'],
            'salary': [8500],
            'projection': [20.0],
            'ownership': [pd.NA]
        })
        
        issues = validate_data_ranges(df)
        # Should have no ownership issues
        assert not any('ownership' in issue['column'] for issue in issues)


class TestGetDataQualityScore:
    """Test data quality scoring."""
    
    def test_perfect_quality_score(self, valid_dataframe):
        """Test quality score is 100% for valid data."""
        result = get_data_quality_score(valid_dataframe)
        
        assert result['total_rows'] == 3
        assert result['valid_rows'] == 3
        assert result['quality_percentage'] == 100.0
        assert len(result['issues']) == 0
    
    def test_quality_score_with_issues(self):
        """Test quality score reflects data issues."""
        df = pd.DataFrame({
            'name': ['Player 1', 'Player 2', 'Player 3'],
            'position': ['QB', 'INVALID', 'WR'],  # 1 invalid
            'salary': [8500, 9200, 8000],
            'projection': [20.0, 22.0, 21.0]
        })
        
        result = get_data_quality_score(df)
        
        assert result['total_rows'] == 3
        assert result['valid_rows'] == 2  # 1 row with issue
        assert result['quality_percentage'] == 66.7
        assert len(result['issues']) > 0
    
    def test_quality_score_multiple_issues_same_row(self):
        """Test row with multiple issues counted once."""
        df = pd.DataFrame({
            'name': ['Player 1'],
            'position': ['INVALID'],  # Issue 1
            'salary': [15000],  # Issue 2
            'projection': [-5.0]  # Issue 3
        })
        
        result = get_data_quality_score(df)
        
        assert result['total_rows'] == 1
        assert result['valid_rows'] == 0  # 1 row with multiple issues
        assert result['quality_percentage'] == 0.0
        assert len(result['issues']) == 3  # 3 separate issues
    
    def test_quality_score_empty_dataframe(self):
        """Test quality score for empty DataFrame."""
        df = pd.DataFrame({
            'name': [],
            'position': [],
            'salary': [],
            'projection': []
        })
        
        result = get_data_quality_score(df)
        
        assert result['total_rows'] == 0
        assert result['valid_rows'] == 0
        assert result['quality_percentage'] == 0.0
    
    def test_issues_list_format(self):
        """Test issues list has correct format."""
        df = pd.DataFrame({
            'name': ['Player 1'],
            'position': ['INVALID'],
            'salary': [8500],
            'projection': [20.0]
        })
        
        result = get_data_quality_score(df)
        issues = result['issues']
        
        assert len(issues) > 0
        issue = issues[0]
        assert 'row' in issue
        assert 'column' in issue
        assert 'issue' in issue
        assert isinstance(issue['row'], int)
        assert isinstance(issue['column'], str)
        assert isinstance(issue['issue'], str)

