"""
Unit Tests for Parser Module

Tests file parsing, column detection, and data type conversion.
"""

import pytest
import pandas as pd
from io import StringIO
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from parser import (
    parse_file,
    detect_columns,
    convert_data_types,
    get_file_extension,
    load_and_validate_player_data
)


class TestGetFileExtension:
    """Test file extension extraction."""
    
    def test_csv_extension(self):
        """Test CSV file extension detection."""
        assert get_file_extension("data.csv") == ".csv"
    
    def test_xlsx_extension(self):
        """Test Excel file extension detection."""
        assert get_file_extension("data.xlsx") == ".xlsx"
    
    def test_xls_extension(self):
        """Test legacy Excel extension detection."""
        assert get_file_extension("data.xls") == ".xls"
    
    def test_case_insensitive(self):
        """Test extension detection is case-insensitive."""
        assert get_file_extension("DATA.CSV") == ".csv"
    
    def test_multiple_dots(self):
        """Test filename with multiple dots."""
        assert get_file_extension("my.data.file.csv") == ".csv"


class TestDetectColumns:
    """Test column name detection and mapping."""
    
    def test_standard_columns(self):
        """Test detection of standard column names."""
        df = pd.DataFrame(columns=['Name', 'Position', 'Salary', 'Projection'])
        mapping = detect_columns(df)
        
        assert mapping['Name'] == 'name'
        assert mapping['Position'] == 'position'
        assert mapping['Salary'] == 'salary'
        assert mapping['Projection'] == 'projection'
    
    def test_column_variations(self):
        """Test detection handles name variations."""
        df = pd.DataFrame(columns=['Player Name', 'Pos', 'Cost', 'Proj'])
        mapping = detect_columns(df)
        
        assert mapping['Player Name'] == 'name'
        assert mapping['Pos'] == 'position'
        assert mapping['Cost'] == 'salary'
        assert mapping['Proj'] == 'projection'
    
    def test_case_insensitive(self):
        """Test detection is case-insensitive."""
        df = pd.DataFrame(columns=['NAME', 'POSITION', 'SALARY', 'PROJECTION'])
        mapping = detect_columns(df)
        
        assert mapping['NAME'] == 'name'
        assert mapping['POSITION'] == 'position'
        assert mapping['SALARY'] == 'salary'
        assert mapping['PROJECTION'] == 'projection'
    
    def test_optional_columns(self):
        """Test detection of optional columns."""
        df = pd.DataFrame(columns=['Team', 'Opponent', 'Ownership', 'Player ID'])
        mapping = detect_columns(df)
        
        assert mapping['Team'] == 'team'
        assert mapping['Opponent'] == 'opponent'
        assert mapping['Ownership'] == 'ownership'
        assert mapping['Player ID'] == 'player_id'
    
    def test_unrecognized_columns_ignored(self):
        """Test unrecognized columns are not mapped."""
        df = pd.DataFrame(columns=['Name', 'Unknown Column', 'Projection'])
        mapping = detect_columns(df)
        
        assert 'Name' in mapping
        assert 'Projection' in mapping
        assert 'Unknown Column' not in mapping


class TestConvertDataTypes:
    """Test data type conversion."""
    
    def test_salary_to_int(self):
        """Test salary converted to integer."""
        df = pd.DataFrame({'salary': ['8500', '9200']})
        result = convert_data_types(df)
        
        assert result['salary'].dtype == 'int64'
        assert result['salary'].iloc[0] == 8500
    
    def test_salary_with_dollar_sign(self):
        """Test salary handles dollar signs."""
        df = pd.DataFrame({'salary': ['$8,500', '$9,200']})
        result = convert_data_types(df)
        
        assert result['salary'].dtype == 'int64'
        assert result['salary'].iloc[0] == 8500
    
    def test_projection_to_float(self):
        """Test projection converted to float."""
        df = pd.DataFrame({'projection': ['24.2', '22.1']})
        result = convert_data_types(df)
        
        assert result['projection'].dtype == 'float64'
        assert result['projection'].iloc[0] == 24.2
    
    def test_ownership_to_float(self):
        """Test ownership converted to float."""
        df = pd.DataFrame({'ownership': ['28.5', '32.0']})
        result = convert_data_types(df)
        
        assert result['ownership'].dtype == 'float64'
        assert result['ownership'].iloc[0] == 28.5
    
    def test_string_columns_trimmed(self):
        """Test string columns have whitespace trimmed."""
        df = pd.DataFrame({
            'name': ['  Patrick Mahomes  ', ' Christian McCaffrey'],
            'position': ['QB ', ' RB']
        })
        result = convert_data_types(df)
        
        assert result['name'].iloc[0] == 'Patrick Mahomes'
        assert result['position'].iloc[1] == 'RB'
    
    def test_invalid_salary_raises_error(self):
        """Test invalid salary values raise ValueError."""
        df = pd.DataFrame({'salary': ['invalid', '8500']})
        
        with pytest.raises(ValueError) as excinfo:
            convert_data_types(df)
        
        assert 'salary' in str(excinfo.value).lower()


class TestParseFile:
    """Test complete file parsing."""
    
    def test_parse_valid_csv(self, valid_csv_data, mock_uploaded_file):
        """Test parsing a valid CSV file."""
        mock_file = mock_uploaded_file(valid_csv_data, "test.csv")
        df = parse_file(mock_file)
        
        assert len(df) == 5
        assert list(df.columns) == ['name', 'position', 'salary', 'team', 'opponent', 
                                     'projection', 'ownership']
        assert df.iloc[0]['name'] == 'Patrick Mahomes'
        assert df.iloc[0]['salary'] == 8500
        assert df.iloc[0]['projection'] == 24.2
    
    def test_parse_csv_with_variations(self, valid_csv_with_variations, mock_uploaded_file):
        """Test parsing CSV with column name variations."""
        mock_file = mock_uploaded_file(valid_csv_with_variations, "test.csv")
        df = parse_file(mock_file)
        
        assert 'name' in df.columns
        assert 'position' in df.columns
        assert 'salary' in df.columns
        assert 'projection' in df.columns
    
    def test_parse_unsupported_format(self, mock_uploaded_file):
        """Test parsing unsupported file format raises error."""
        mock_file = mock_uploaded_file("some data", "test.pdf")
        
        with pytest.raises(ValueError) as excinfo:
            parse_file(mock_file)
        
        assert ".pdf" in str(excinfo.value)
        assert "Unsupported" in str(excinfo.value)
    
    def test_parse_missing_required_column(self, csv_missing_required_column, mock_uploaded_file):
        """Test parsing file missing required column raises KeyError."""
        mock_file = mock_uploaded_file(csv_missing_required_column, "test.csv")
        
        with pytest.raises(KeyError) as excinfo:
            parse_file(mock_file)
        
        assert "projection" in str(excinfo.value).lower()


class TestLoadAndValidatePlayerData:
    """Test complete data loading and validation pipeline."""
    
    def test_load_valid_data(self, valid_csv_data, mock_uploaded_file):
        """Test loading and validating valid data."""
        mock_file = mock_uploaded_file(valid_csv_data, "test.csv")
        df, summary = load_and_validate_player_data(mock_file)
        
        assert len(df) == 5
        assert summary['total_players'] == 5
        assert summary['quality_score'] == 100.0
        assert len(summary['issues']) == 0
    
    def test_summary_position_breakdown(self, valid_csv_data, mock_uploaded_file):
        """Test position breakdown in summary."""
        mock_file = mock_uploaded_file(valid_csv_data, "test.csv")
        df, summary = load_and_validate_player_data(mock_file)
        
        assert 'QB' in summary['position_breakdown']
        assert 'RB' in summary['position_breakdown']
        assert 'WR' in summary['position_breakdown']
        assert 'TE' in summary['position_breakdown']
        assert 'DST' in summary['position_breakdown']
    
    def test_summary_salary_range(self, valid_csv_data, mock_uploaded_file):
        """Test salary range in summary."""
        mock_file = mock_uploaded_file(valid_csv_data, "test.csv")
        df, summary = load_and_validate_player_data(mock_file)
        
        min_sal, max_sal = summary['salary_range']
        assert min_sal == 3500
        assert max_sal == 9200
    
    def test_quality_score_with_issues(self, csv_invalid_position, mock_uploaded_file):
        """Test quality score reflects data issues."""
        mock_file = mock_uploaded_file(csv_invalid_position, "test.csv")
        df, summary = load_and_validate_player_data(mock_file)
        
        assert summary['quality_score'] < 100.0
        assert len(summary['issues']) > 0

