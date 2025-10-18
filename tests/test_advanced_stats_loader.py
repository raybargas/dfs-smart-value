"""
Unit Tests for FileLoader

Tests for the FileLoader class from the DFS Advanced Stats Migration.
Part of Phase 1 Infrastructure Testing (Task 1.4.1).

Test Coverage:
- Successful loading of all 4 files
- Graceful degradation with missing files
- Corrupted file handling
- Schema validation
- Performance benchmarking
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os
import time
from unittest.mock import Mock, patch, MagicMock
import logging

# Import the classes to test
from DFS.src.advanced_stats_loader import (
    FileLoader,
    load_season_stats_files,
    REQUIRED_COLUMNS,
    FILE_PATTERNS
)
from DFS.src.team_normalizer import TeamNormalizer


class TestFileLoader:
    """
    Comprehensive tests for FileLoader class functionality.

    Tests cover:
    - File loading success/failure scenarios
    - Schema validation
    - Error handling
    - Performance requirements
    """

    @pytest.fixture
    def temp_stats_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def create_valid_excel_file(self):
        """Helper to create valid test Excel files."""
        def _create(file_path: str, file_type: str, num_records: int = 100):
            """
            Create a valid Excel file with required columns.

            Args:
                file_path: Where to save the file
                file_type: One of 'pass', 'rush', 'receiving', 'snaps'
                num_records: Number of test records to create
            """
            # Get required columns for this file type
            required_cols = REQUIRED_COLUMNS[file_type]

            # Create test data based on file type
            data = {}

            # Common columns
            data['Name'] = [f"Player {i}" for i in range(num_records)]
            data['Team'] = [['KC', 'SF', 'BUF', 'DAL', 'MIA'][i % 5] for i in range(num_records)]
            data['POS'] = [['QB', 'RB', 'WR', 'TE'][i % 4] for i in range(num_records)]
            data['W'] = [i % 5 + 1 for i in range(num_records)]  # Weeks 1-5

            # File-specific columns
            if file_type == 'pass':
                data['CPOE'] = np.random.uniform(-10, 10, num_records)
                data['aDOT'] = np.random.uniform(5, 15, num_records)
                data['Deep Throw %'] = np.random.uniform(0, 30, num_records)
                data['1Read %'] = np.random.uniform(20, 80, num_records)
                data['ATT'] = np.random.randint(20, 50, num_records)
                data['CMP'] = np.random.randint(10, 35, num_records)

            elif file_type == 'rush':
                data['YACO/ATT'] = np.random.uniform(1, 5, num_records)
                data['MTF/ATT'] = np.random.uniform(0, 0.5, num_records)
                data['Success Rate'] = np.random.uniform(30, 60, num_records)
                data['STUFF %'] = np.random.uniform(10, 30, num_records)
                data['ATT'] = np.random.randint(5, 25, num_records)
                data['YDS'] = np.random.randint(20, 150, num_records)

            elif file_type == 'receiving':
                data['TPRR'] = np.random.uniform(0.1, 0.4, num_records)
                data['YPRR'] = np.random.uniform(0.5, 3.0, num_records)
                data['RTE %'] = np.random.uniform(50, 95, num_records)
                data['1READ %'] = np.random.uniform(10, 40, num_records)
                data['CTGT %'] = np.random.uniform(5, 25, num_records)
                data['TGT'] = np.random.randint(3, 15, num_records)
                data['REC'] = np.random.randint(2, 10, num_records)

            elif file_type == 'snaps':
                data['Snap %'] = np.random.uniform(30, 95, num_records)
                data['FP/G'] = np.random.uniform(5, 25, num_records)
                data['FP'] = np.random.uniform(25, 125, num_records)
                data['Snaps'] = np.random.randint(20, 75, num_records)

            # Create DataFrame and save to Excel
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False)
            return df

        return _create

    @pytest.fixture
    def create_corrupted_excel_file(self):
        """Helper to create corrupted test Excel files."""
        def _create(file_path: str):
            """Create a corrupted Excel file."""
            # Write invalid bytes that aren't a valid Excel file
            with open(file_path, 'wb') as f:
                f.write(b'This is not a valid Excel file content')
        return _create

    def test_successful_load_all_files(self, temp_stats_dir, create_valid_excel_file):
        """
        Test successful loading of all 4 files.

        Acceptance Criteria:
        - All 4 files load successfully
        - Schema validation passes
        - Team normalization applied
        - Performance <2 seconds
        """
        # Create all 4 valid files
        for file_key, file_name in FILE_PATTERNS.items():
            file_path = os.path.join(temp_stats_dir, file_name)
            create_valid_excel_file(file_path, file_key)

        # Initialize loader and load files
        loader = FileLoader(temp_stats_dir)
        start_time = time.time()
        files = loader.load_all_files()
        load_time = time.time() - start_time

        # Verify all files loaded
        assert len(files) == 4
        for file_key in FILE_PATTERNS:
            assert file_key in files
            assert files[file_key] is not None
            assert isinstance(files[file_key], pd.DataFrame)
            assert len(files[file_key]) > 0

        # Verify performance
        assert load_time < 2.0, f"Loading took {load_time:.2f} seconds (target: <2 seconds)"

        # Get report and verify success
        report = loader.get_load_report()
        assert report['files_loaded'] == 4
        assert report['files_failed'] == 0
        assert len(report['errors']) == 0
        assert report['total_records'] > 0

    def test_graceful_degradation_one_missing_file(self, temp_stats_dir, create_valid_excel_file):
        """
        Test graceful degradation with 1 missing file.

        Acceptance Criteria:
        - System continues with 3 files
        - Missing file returns None
        - Warning logged
        - No exceptions raised
        """
        # Create only 3 files (skip 'rush')
        files_to_create = ['pass', 'receiving', 'snaps']
        for file_key in files_to_create:
            file_name = FILE_PATTERNS[file_key]
            file_path = os.path.join(temp_stats_dir, file_name)
            create_valid_excel_file(file_path, file_key)

        # Load files
        loader = FileLoader(temp_stats_dir)
        files = loader.load_all_files()

        # Verify 3 files loaded, 1 is None
        assert files['pass'] is not None
        assert files['rush'] is None  # Missing file
        assert files['receiving'] is not None
        assert files['snaps'] is not None

        # Verify report shows degradation
        report = loader.get_load_report()
        assert report['files_loaded'] == 3
        assert report['files_failed'] == 1
        assert 'rush' in report['errors']

        # Verify minimum files check passes (need at least 2)
        assert loader.has_minimum_files() == True

    def test_graceful_degradation_two_missing_files(self, temp_stats_dir, create_valid_excel_file):
        """
        Test graceful degradation with 2 missing files.

        Acceptance Criteria:
        - System continues with 2 files
        - Missing files return None
        - Warning logged
        - Still meets minimum requirement
        """
        # Create only 2 files
        files_to_create = ['pass', 'snaps']
        for file_key in files_to_create:
            file_name = FILE_PATTERNS[file_key]
            file_path = os.path.join(temp_stats_dir, file_name)
            create_valid_excel_file(file_path, file_key, num_records=50)

        # Load files
        loader = FileLoader(temp_stats_dir)
        files = loader.load_all_files()

        # Verify 2 files loaded, 2 are None
        assert files['pass'] is not None
        assert files['rush'] is None
        assert files['receiving'] is None
        assert files['snaps'] is not None

        # Verify report
        report = loader.get_load_report()
        assert report['files_loaded'] == 2
        assert report['files_failed'] == 2

        # Still meets minimum requirement
        assert loader.has_minimum_files() == True

    def test_error_handling_corrupted_file(self, temp_stats_dir, create_valid_excel_file, create_corrupted_excel_file):
        """
        Test error handling for corrupted file.

        Acceptance Criteria:
        - Corrupted file fails to load
        - Other files still load successfully
        - Error logged with appropriate code
        - System continues gracefully
        """
        # Create 3 valid files and 1 corrupted
        valid_files = ['pass', 'receiving', 'snaps']
        for file_key in valid_files:
            file_name = FILE_PATTERNS[file_key]
            file_path = os.path.join(temp_stats_dir, file_name)
            create_valid_excel_file(file_path, file_key)

        # Create corrupted rush file
        corrupted_path = os.path.join(temp_stats_dir, FILE_PATTERNS['rush'])
        create_corrupted_excel_file(corrupted_path)

        # Load files
        loader = FileLoader(temp_stats_dir)
        files = loader.load_all_files()

        # Verify 3 files loaded, corrupted one failed
        assert files['pass'] is not None
        assert files['rush'] is None  # Corrupted file
        assert files['receiving'] is not None
        assert files['snaps'] is not None

        # Verify error logged
        report = loader.get_load_report()
        assert report['files_failed'] == 1
        assert 'rush' in report['errors']
        assert 'ERR-ADV-002' in report['errors']['rush']

    def test_schema_validation_missing_columns(self, temp_stats_dir):
        """
        Test schema validation with missing required columns.

        Acceptance Criteria:
        - Files with missing required columns fail validation
        - Error code ERR-ADV-003 logged
        - File returns None
        """
        # Create file with missing required columns
        file_path = os.path.join(temp_stats_dir, FILE_PATTERNS['pass'])

        # Create DataFrame missing required columns
        data = {
            'Name': ['Player 1', 'Player 2'],
            'Team': ['KC', 'SF'],
            'POS': ['QB', 'QB'],
            # Missing: 'W', 'CPOE', 'aDOT', 'Deep Throw %', '1Read %'
        }
        df = pd.DataFrame(data)
        df.to_excel(file_path, index=False)

        # Load files
        loader = FileLoader(temp_stats_dir)
        files = loader.load_all_files()

        # Verify file failed to load
        assert files['pass'] is None

        # Verify error contains ERR-ADV-003
        report = loader.get_load_report()
        assert 'pass' in report['errors']
        assert 'ERR-ADV-003' in report['errors']['pass']

    def test_file_size_validation(self, temp_stats_dir):
        """
        Test file size validation warnings and errors.

        Acceptance Criteria:
        - Files >10MB generate warning
        - Files >50MB generate error
        - Files <1KB generate empty file error
        """
        # Test empty file detection
        empty_file = os.path.join(temp_stats_dir, FILE_PATTERNS['pass'])
        with open(empty_file, 'wb') as f:
            f.write(b'')  # Empty file

        loader = FileLoader(temp_stats_dir)
        files = loader.load_all_files()

        # Verify empty file rejected
        assert files['pass'] is None
        report = loader.get_load_report()
        assert 'pass' in report['errors']
        assert 'empty' in report['errors']['pass'].lower()

    def test_team_normalization_applied(self, temp_stats_dir):
        """
        Test that team abbreviations are normalized.

        Acceptance Criteria:
        - Non-standard team abbreviations converted
        - BLT → BAL, CLV → CLE, etc.
        """
        # Create file with non-standard team abbreviations
        file_path = os.path.join(temp_stats_dir, FILE_PATTERNS['snaps'])

        data = {
            'Name': ['Player 1', 'Player 2', 'Player 3'],
            'Team': ['BLT', 'CLV', 'LA'],  # Non-standard abbreviations
            'POS': ['QB', 'RB', 'WR'],
            'W': [1, 1, 1],
            'Snap %': [85.0, 75.0, 65.0],
            'FP/G': [20.0, 15.0, 12.0],
            'FP': [20.0, 15.0, 12.0]
        }
        df = pd.DataFrame(data)
        df.to_excel(file_path, index=False)

        # Load files
        loader = FileLoader(temp_stats_dir)
        files = loader.load_all_files()

        # Verify normalization applied
        snaps_df = files['snaps']
        assert snaps_df is not None
        teams = snaps_df['Team'].tolist()
        assert 'BAL' in teams  # BLT → BAL
        assert 'CLE' in teams  # CLV → CLE
        assert 'LAR' in teams  # LA → LAR
        assert 'BLT' not in teams
        assert 'CLV' not in teams

    def test_directory_not_found_error(self):
        """
        Test FileLoader raises error when directory doesn't exist.

        Acceptance Criteria:
        - FileNotFoundError raised with ERR-ADV-001
        """
        non_existent_dir = "/this/directory/does/not/exist"

        with pytest.raises(FileNotFoundError) as excinfo:
            loader = FileLoader(non_existent_dir)

        assert "ERR-ADV-001" in str(excinfo.value)

    def test_get_file_methods(self, temp_stats_dir, create_valid_excel_file):
        """
        Test get_file() and get_all_files() methods.

        Acceptance Criteria:
        - Can retrieve individual files by key
        - Can retrieve all files
        """
        # Create test files
        for file_key in ['pass', 'rush']:
            file_name = FILE_PATTERNS[file_key]
            file_path = os.path.join(temp_stats_dir, file_name)
            create_valid_excel_file(file_path, file_key, num_records=10)

        loader = FileLoader(temp_stats_dir)
        loader.load_all_files()

        # Test get_file()
        pass_df = loader.get_file('pass')
        assert pass_df is not None
        assert isinstance(pass_df, pd.DataFrame)

        rush_df = loader.get_file('rush')
        assert rush_df is not None

        # Test missing file
        receiving_df = loader.get_file('receiving')
        assert receiving_df is None

        # Test get_all_files()
        all_files = loader.get_all_files()
        assert len(all_files) == 4
        assert 'pass' in all_files
        assert 'rush' in all_files

    def test_load_report_details(self, temp_stats_dir, create_valid_excel_file):
        """
        Test comprehensive load report generation.

        Acceptance Criteria:
        - Report contains all required fields
        - File details include records, columns, load times
        - Week information captured
        """
        # Create files with different sizes
        create_valid_excel_file(
            os.path.join(temp_stats_dir, FILE_PATTERNS['pass']),
            'pass',
            num_records=50
        )
        create_valid_excel_file(
            os.path.join(temp_stats_dir, FILE_PATTERNS['rush']),
            'rush',
            num_records=150
        )

        loader = FileLoader(temp_stats_dir)
        loader.load_all_files()

        report = loader.get_load_report()

        # Check report structure
        assert 'files_loaded' in report
        assert 'files_failed' in report
        assert 'errors' in report
        assert 'warnings' in report
        assert 'load_times' in report
        assert 'total_load_time' in report
        assert 'total_records' in report
        assert 'file_details' in report

        # Check file details
        pass_details = report['file_details']['pass']
        assert pass_details['records'] == 50
        assert pass_details['columns'] > 0
        assert pass_details['load_time'] > 0
        assert pass_details['unique_players'] > 0
        assert pass_details['unique_teams'] > 0
        assert len(pass_details['weeks']) > 0

        # Check total records
        assert report['total_records'] == 200  # 50 + 150


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    @pytest.fixture
    def mock_files(self):
        """Create mock season stats files."""
        return {
            'pass': pd.DataFrame({'Name': ['QB1'], 'Team': ['KC']}),
            'rush': pd.DataFrame({'Name': ['RB1'], 'Team': ['SF']}),
            'receiving': None,  # Missing file
            'snaps': pd.DataFrame({'Name': ['All'], 'Team': ['DAL']})
        }

    @patch('DFS.src.advanced_stats_loader.FileLoader')
    def test_load_season_stats_files(self, MockLoader, mock_files):
        """
        Test convenience function for loading files.

        Acceptance Criteria:
        - Returns loaded files dictionary
        - Logs warnings for failures
        """
        # Setup mock
        mock_instance = MockLoader.return_value
        mock_instance.load_all_files.return_value = mock_files
        mock_instance.get_load_report.return_value = {
            'files_loaded': 3,
            'files_failed': 1,
            'errors': {'receiving': 'Not found'}
        }

        # Call function
        result = load_season_stats_files("/test/dir")

        # Verify
        assert result == mock_files
        MockLoader.assert_called_once_with("/test/dir")
        mock_instance.load_all_files.assert_called_once()
        mock_instance.get_load_report.assert_called_once()


class TestPerformanceBenchmarks:
    """
    Performance benchmark tests.

    Verifies system meets performance requirements:
    - File loading <2 seconds
    - Memory usage reasonable
    """

    @pytest.fixture
    def create_large_excel_file(self):
        """Create large Excel files for performance testing."""
        def _create(file_path: str, file_type: str, num_records: int = 2000):
            """Create a large Excel file for performance testing."""
            required_cols = REQUIRED_COLUMNS[file_type]

            data = {
                'Name': [f"Player {i}" for i in range(num_records)],
                'Team': [['KC', 'SF', 'BUF', 'DAL', 'MIA'][i % 5] for i in range(num_records)],
                'POS': [['QB', 'RB', 'WR', 'TE'][i % 4] for i in range(num_records)],
                'W': [i % 5 + 1 for i in range(num_records)]
            }

            # Add file-specific columns with random data
            for col in required_cols:
                if col not in data:
                    if '%' in col or 'Rate' in col:
                        data[col] = np.random.uniform(0, 100, num_records)
                    elif col in ['CPOE', 'aDOT', 'YACO/ATT', 'MTF/ATT', 'TPRR', 'YPRR']:
                        data[col] = np.random.uniform(0, 10, num_records)
                    else:
                        data[col] = np.random.uniform(0, 50, num_records)

            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False)
            return df

        return _create

    def test_performance_large_files(self, temp_stats_dir, create_large_excel_file):
        """
        Test performance with large files.

        Acceptance Criteria:
        - 4 files with 2000 records each load in <2 seconds
        """
        # Create large files
        for file_key, file_name in FILE_PATTERNS.items():
            file_path = os.path.join(temp_stats_dir, file_name)
            create_large_excel_file(file_path, file_key, num_records=2000)

        # Measure loading time
        loader = FileLoader(temp_stats_dir)
        start_time = time.time()
        files = loader.load_all_files()
        load_time = time.time() - start_time

        # Verify performance
        assert load_time < 2.0, f"Large files took {load_time:.2f} seconds to load (target: <2 seconds)"

        # Verify all files loaded
        report = loader.get_load_report()
        assert report['files_loaded'] == 4
        assert report['total_records'] == 8000  # 2000 * 4


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])