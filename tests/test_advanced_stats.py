"""
Unit Tests for Advanced Stats Infrastructure
Part of DFS Advanced Stats Migration (2025-10-18) - Phase 1

Tests for:
- FileLoader: File loading and validation
- TeamNormalizer: Team abbreviation standardization
- PlayerNameMapper: Fuzzy name matching
- Performance benchmarks

Enhanced with comprehensive Phase 1 testing requirements:
- Task 1.4.1: FileLoader unit tests
- Task 1.4.2: PlayerNameMapper unit tests
- Task 1.4.3: Performance benchmarking
"""

import unittest
import tempfile
import os
import sys
import pandas as pd
import time
import json
import shutil
from unittest.mock import patch, MagicMock, mock_open
from io import BytesIO

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.advanced_stats_loader import FileLoader, load_season_stats_files, create_player_mapper
from src.team_normalizer import TeamNormalizer
from src.player_name_mapper import PlayerNameMapper, PlayerMapping, normalize_name


class TestFileLoader(unittest.TestCase):
    """Tests for FileLoader class - Task 1.4.1"""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.loader = None

    def tearDown(self):
        """Clean up test fixtures."""
        # Remove test files
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def create_valid_test_files(self):
        """Create valid test Excel files with all required columns."""
        # Pass file with all required columns
        pass_data = pd.DataFrame({
            'Name': ['Patrick Mahomes', 'Josh Allen', 'Lamar Jackson'],
            'Team': ['KC', 'BUF', 'BAL'],
            'POS': ['QB', 'QB', 'QB'],
            'W': [1, 1, 1],
            'CPOE': [5.2, 3.1, 7.8],
            'aDOT': [8.5, 7.2, 9.1],
            'Deep Throw %': [25.0, 22.0, 28.0],
            '1Read %': [65.0, 62.0, 58.0],
            'ATT': [35, 32, 28],
            'CMP': [24, 22, 19]
        })
        pass_data.to_excel(os.path.join(self.test_dir, 'Pass 2025.xlsx'), index=False)

        # Rush file with all required columns
        rush_data = pd.DataFrame({
            'Name': ['Derrick Henry', 'Nick Chubb', 'Josh Jacobs'],
            'Team': ['BAL', 'CLE', 'LVR'],
            'POS': ['RB', 'RB', 'RB'],
            'W': [1, 1, 1],
            'YACO/ATT': [3.2, 3.8, 2.9],
            'MTF/ATT': [0.25, 0.31, 0.22],
            'Success Rate': [45.0, 52.0, 41.0],
            'STUFF %': [15.0, 12.0, 18.0],
            'ATT': [22, 18, 20],
            'YDS': [95, 88, 76]
        })
        rush_data.to_excel(os.path.join(self.test_dir, 'Rush 2025.xlsx'), index=False)

        # Receiving file with all required columns
        receiving_data = pd.DataFrame({
            'Name': ['CeeDee Lamb', 'Justin Jefferson', 'Tyreek Hill'],
            'Team': ['DAL', 'MIN', 'MIA'],
            'POS': ['WR', 'WR', 'WR'],
            'W': [1, 1, 1],
            'TPRR': [0.28, 0.32, 0.26],
            'YPRR': [2.8, 3.1, 2.5],
            'RTE %': [85.0, 92.0, 81.0],
            '1READ %': [28.0, 35.0, 25.0],
            'CTGT %': [15.0, 18.0, 12.0],
            'TGT': [11, 12, 10],
            'REC': [8, 9, 7]
        })
        receiving_data.to_excel(os.path.join(self.test_dir, 'Receiving 2025.xlsx'), index=False)

        # Snaps file with all required columns
        snaps_data = pd.DataFrame({
            'Name': ['Patrick Mahomes', 'Derrick Henry', 'CeeDee Lamb'],
            'Team': ['KC', 'BAL', 'DAL'],
            'POS': ['QB', 'RB', 'WR'],
            'W': [1, 1, 1],
            'Snap %': [100.0, 65.0, 82.0],
            'FP/G': [25.0, 18.0, 21.0],
            'FP': [25.0, 18.0, 21.0],
            'Snaps': [72, 45, 58]
        })
        snaps_data.to_excel(os.path.join(self.test_dir, 'Snaps 2025.xlsx'), index=False)

    def test_load_all_files_success(self):
        """Test successful loading of all 4 files - Task 1.4.1 Requirement 1"""
        self.create_valid_test_files()
        loader = FileLoader(self.test_dir)
        files = loader.load_all_files()

        # Check all files loaded successfully
        self.assertIsNotNone(files['pass'])
        self.assertIsNotNone(files['rush'])
        self.assertIsNotNone(files['receiving'])
        self.assertIsNotNone(files['snaps'])

        # Verify correct number of records
        self.assertEqual(len(files['pass']), 3)
        self.assertEqual(len(files['rush']), 3)
        self.assertEqual(len(files['receiving']), 3)
        self.assertEqual(len(files['snaps']), 3)

        # Verify all required columns present
        self.assertIn('CPOE', files['pass'].columns)
        self.assertIn('YACO/ATT', files['rush'].columns)
        self.assertIn('TPRR', files['receiving'].columns)
        self.assertIn('Snap %', files['snaps'].columns)

        # Check load report
        report = loader.get_load_report()
        self.assertEqual(report['files_loaded'], 4)
        self.assertEqual(report['files_failed'], 0)

    def test_graceful_degradation_one_missing_file(self):
        """Test graceful degradation with 1 missing file - Task 1.4.1 Requirement 2"""
        self.create_valid_test_files()
        # Remove rush file to test graceful degradation
        os.remove(os.path.join(self.test_dir, 'Rush 2025.xlsx'))

        loader = FileLoader(self.test_dir)
        files = loader.load_all_files()

        # Check 3 files loaded, 1 failed
        self.assertIsNotNone(files['pass'])
        self.assertIsNone(files['rush'])  # This should be None
        self.assertIsNotNone(files['receiving'])
        self.assertIsNotNone(files['snaps'])

        # Verify report shows correct counts
        report = loader.get_load_report()
        self.assertEqual(report['files_loaded'], 3)
        self.assertEqual(report['files_failed'], 1)
        self.assertIn('rush', report['errors'])

    def test_graceful_degradation_two_missing_files(self):
        """Test graceful degradation with 2 missing files - Task 1.4.1 Requirement 3"""
        self.create_valid_test_files()
        # Remove two files
        os.remove(os.path.join(self.test_dir, 'Rush 2025.xlsx'))
        os.remove(os.path.join(self.test_dir, 'Receiving 2025.xlsx'))

        loader = FileLoader(self.test_dir)
        files = loader.load_all_files()

        # Check 2 files loaded, 2 failed
        self.assertIsNotNone(files['pass'])
        self.assertIsNone(files['rush'])
        self.assertIsNone(files['receiving'])
        self.assertIsNotNone(files['snaps'])

        report = loader.get_load_report()
        self.assertEqual(report['files_loaded'], 2)
        self.assertEqual(report['files_failed'], 2)

    def test_corrupted_file_handling(self):
        """Test error handling for corrupted file - Task 1.4.1 Requirement 4"""
        self.create_valid_test_files()

        # Create a corrupted file (invalid Excel)
        corrupted_path = os.path.join(self.test_dir, 'Pass 2025.xlsx')
        with open(corrupted_path, 'w') as f:
            f.write("This is not a valid Excel file")

        loader = FileLoader(self.test_dir)
        files = loader.load_all_files()

        # Pass file should fail, others should load
        self.assertIsNone(files['pass'])
        self.assertIsNotNone(files['rush'])
        self.assertIsNotNone(files['receiving'])
        self.assertIsNotNone(files['snaps'])

        report = loader.get_load_report()
        self.assertEqual(report['files_failed'], 1)
        self.assertIn('pass', report['errors'])

    def test_schema_validation(self):
        """Test schema validation - Task 1.4.1 Requirement 5"""
        loader = FileLoader(self.test_dir)

        # Test valid schema
        valid_pass_df = pd.DataFrame({
            'Name': ['Test Player'],
            'Team': ['KC'],
            'POS': ['QB'],
            'W': [1],
            'CPOE': [5.0],
            'aDOT': [8.0],
            'Deep Throw %': [25.0],
            '1Read %': [60.0]
        })
        self.assertTrue(loader.validate_file_schema('pass', valid_pass_df))

        # Test missing required columns
        invalid_df = pd.DataFrame({
            'Name': ['Test Player'],
            'Team': ['KC']
            # Missing required columns
        })
        self.assertFalse(loader.validate_file_schema('pass', invalid_df))

        # Test validation for each file type
        valid_rush_df = pd.DataFrame({
            'Name': ['RB'],
            'Team': ['KC'],
            'POS': ['RB'],
            'W': [1],
            'YACO/ATT': [3.0],
            'MTF/ATT': [0.2],
            'Success Rate': [45.0],
            'STUFF %': [15.0]
        })
        self.assertTrue(loader.validate_file_schema('rush', valid_rush_df))

        valid_receiving_df = pd.DataFrame({
            'Name': ['WR'],
            'Team': ['KC'],
            'POS': ['WR'],
            'W': [1],
            'TPRR': [0.25],
            'YPRR': [2.0],
            'RTE %': [80.0],
            '1READ %': [25.0],
            'CTGT %': [15.0]
        })
        self.assertTrue(loader.validate_file_schema('receiving', valid_receiving_df))

        valid_snaps_df = pd.DataFrame({
            'Name': ['Player'],
            'Team': ['KC'],
            'POS': ['QB'],
            'W': [1],
            'Snap %': [95.0],
            'FP/G': [20.0],
            'FP': [20.0]
        })
        self.assertTrue(loader.validate_file_schema('snaps', valid_snaps_df))

    def test_empty_directory(self):
        """Test handling of empty directory."""
        empty_dir = os.path.join(self.test_dir, 'empty')
        os.makedirs(empty_dir)

        loader = FileLoader(empty_dir)
        files = loader.load_all_files()

        # All files should be None
        self.assertIsNone(files['pass'])
        self.assertIsNone(files['rush'])
        self.assertIsNone(files['receiving'])
        self.assertIsNone(files['snaps'])

        report = loader.get_load_report()
        self.assertEqual(report['files_loaded'], 0)
        self.assertEqual(report['files_failed'], 4)

    def test_file_size_warnings(self):
        """Test file size validation and warnings."""
        self.create_valid_test_files()
        loader = FileLoader(self.test_dir)

        # Test normal file size (should be fine)
        files = loader.load_all_files()
        report = loader.get_load_report()

        # Small test files should not trigger warnings
        self.assertEqual(len(report.get('warnings', [])), 0)


class TestPlayerNameMapper(unittest.TestCase):
    """Tests for PlayerNameMapper class - Task 1.4.2"""

    def setUp(self):
        """Set up test fixtures."""
        self.mapper = PlayerNameMapper(threshold=85)

    def test_exact_name_matches(self):
        """Test exact name matches return 100 score - Task 1.4.2 Requirement 1"""
        stats_df = pd.DataFrame({
            'Name': ['Patrick Mahomes', 'Josh Allen', 'Lamar Jackson'],
            'Team': ['KC', 'BUF', 'BAL'],
            'POS': ['QB', 'QB', 'QB']
        })

        # Exact match should give 100
        match_name, score = self.mapper.fuzzy_match_player(
            'Patrick Mahomes', 'KC', 'QB', stats_df
        )
        self.assertEqual(match_name, 'Patrick Mahomes')
        self.assertEqual(score, 100)

        # Another exact match
        match_name, score = self.mapper.fuzzy_match_player(
            'Josh Allen', 'BUF', 'QB', stats_df
        )
        self.assertEqual(match_name, 'Josh Allen')
        self.assertEqual(score, 100)

    def test_names_with_suffixes(self):
        """Test names with Jr/Sr/III suffixes - Task 1.4.2 Requirement 2"""
        stats_df = pd.DataFrame({
            'Name': ['Patrick Mahomes', 'Odell Beckham', 'Robert Griffin'],
            'Team': ['KC', 'MIA', 'IND'],
            'POS': ['QB', 'WR', 'QB']
        })

        # Test Jr. suffix
        match_name, score = self.mapper.fuzzy_match_player(
            'Odell Beckham Jr.', 'MIA', 'WR', stats_df
        )
        self.assertEqual(match_name, 'Odell Beckham')
        self.assertGreaterEqual(score, 90)

        # Test II suffix
        match_name, score = self.mapper.fuzzy_match_player(
            'Patrick Mahomes II', 'KC', 'QB', stats_df
        )
        self.assertEqual(match_name, 'Patrick Mahomes')
        self.assertGreaterEqual(score, 90)

        # Test III suffix
        match_name, score = self.mapper.fuzzy_match_player(
            'Robert Griffin III', 'IND', 'QB', stats_df
        )
        self.assertEqual(match_name, 'Robert Griffin')
        self.assertGreaterEqual(score, 90)

        # Test Sr. suffix
        test_df = pd.DataFrame({
            'Name': ['Steve Smith'],
            'Team': ['CAR'],
            'POS': ['WR']
        })
        match_name, score = self.mapper.fuzzy_match_player(
            'Steve Smith Sr.', 'CAR', 'WR', test_df
        )
        self.assertEqual(match_name, 'Steve Smith')
        self.assertGreaterEqual(score, 90)

    def test_names_with_apostrophes_hyphens(self):
        """Test names with apostrophes and hyphens - Task 1.4.2 Requirement 3"""
        stats_df = pd.DataFrame({
            'Name': ["De'Von Achane", "Ja'Marr Chase", "Clyde Edwards-Helaire", "JuJu Smith-Schuster"],
            'Team': ['MIA', 'CIN', 'KC', 'PIT'],
            'POS': ['RB', 'WR', 'RB', 'WR']
        })

        # Test apostrophe handling
        match_name, score = self.mapper.fuzzy_match_player(
            "Devon Achane", 'MIA', 'RB', stats_df  # Without apostrophe
        )
        self.assertEqual(match_name, "De'Von Achane")
        self.assertGreaterEqual(score, 85)

        # Test another apostrophe
        match_name, score = self.mapper.fuzzy_match_player(
            "Jamarr Chase", 'CIN', 'WR', stats_df  # Without apostrophe
        )
        self.assertEqual(match_name, "Ja'Marr Chase")
        self.assertGreaterEqual(score, 85)

        # Test hyphen handling
        match_name, score = self.mapper.fuzzy_match_player(
            "Clyde Edwards Helaire", 'KC', 'RB', stats_df  # Without hyphen
        )
        self.assertEqual(match_name, "Clyde Edwards-Helaire")
        self.assertGreaterEqual(score, 85)

        # Test another hyphen
        match_name, score = self.mapper.fuzzy_match_player(
            "JuJu Smith Schuster", 'PIT', 'WR', stats_df  # Without hyphen
        )
        self.assertEqual(match_name, "JuJu Smith-Schuster")
        self.assertGreaterEqual(score, 85)

    def test_match_rate_over_90_percent(self):
        """Test >90% match rate requirement - Task 1.4.2 Requirement 4"""
        # Create a realistic player DataFrame
        player_df = pd.DataFrame({
            'name': [
                'Patrick Mahomes', 'Josh Allen', 'Lamar Jackson',
                'Derrick Henry', 'Nick Chubb', 'Josh Jacobs',
                'Justin Jefferson', 'CeeDee Lamb', 'Tyreek Hill',
                'Travis Kelce'
            ],
            'position': ['QB', 'QB', 'QB', 'RB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE'],
            'team': ['KC', 'BUF', 'BAL', 'BAL', 'CLE', 'LVR', 'MIN', 'DAL', 'MIA', 'KC']
        })

        # Create season files with slight variations (but still matchable)
        season_files = {
            'pass': pd.DataFrame({
                'Name': ['Patrick Mahomes', 'Josh Allen', 'L. Jackson'],
                'Team': ['KC', 'BUF', 'BAL'],
                'POS': ['QB', 'QB', 'QB']
            }),
            'rush': pd.DataFrame({
                'Name': ['D. Henry', 'Nick Chubb', 'Josh Jacobs'],
                'Team': ['BAL', 'CLE', 'LVR'],
                'POS': ['RB', 'RB', 'RB']
            }),
            'receiving': pd.DataFrame({
                'Name': ['Justin Jefferson', 'CeeDee Lamb', 'T. Hill', 'T. Kelce'],
                'Team': ['MIN', 'DAL', 'MIA', 'KC'],
                'POS': ['WR', 'WR', 'WR', 'TE']
            }),
            'snaps': None
        }

        mappings = self.mapper.create_mappings(player_df, season_files)
        report = self.mapper.get_match_report()

        # Should achieve >90% match rate
        self.assertEqual(report['total_players'], 10)
        self.assertGreaterEqual(report['match_rate'], 90)

        # Most players should have high match scores
        avg_score = report.get('avg_match_score', 0)
        self.assertGreaterEqual(avg_score, 85)

    def test_performance_under_2_seconds_for_500_players(self):
        """Test <2 second performance for 500 players - Task 1.4.2 Requirement 5"""
        # Create 500 player dataset
        player_names = []
        positions = ['QB', 'RB', 'WR', 'TE']
        teams = ['KC', 'BUF', 'DAL', 'MIA', 'GB', 'SF', 'LAR', 'BAL']

        for i in range(500):
            player_names.append(f"Player {i:03d}")

        player_df = pd.DataFrame({
            'name': player_names,
            'position': [positions[i % 4] for i in range(500)],
            'team': [teams[i % 8] for i in range(500)]
        })

        # Create season files with subset of players
        season_files = {
            'pass': pd.DataFrame({
                'Name': player_names[:100],  # QBs
                'Team': [teams[i % 8] for i in range(100)],
                'POS': ['QB'] * 100
            }),
            'rush': pd.DataFrame({
                'Name': player_names[100:250],  # RBs
                'Team': [teams[i % 8] for i in range(150)],
                'POS': ['RB'] * 150
            }),
            'receiving': pd.DataFrame({
                'Name': player_names[250:450],  # WRs/TEs
                'Team': [teams[i % 8] for i in range(200)],
                'POS': ['WR'] * 150 + ['TE'] * 50
            }),
            'snaps': pd.DataFrame({
                'Name': player_names[:400],  # Most players
                'Team': [teams[i % 8] for i in range(400)],
                'POS': [positions[i % 4] for i in range(400)]
            })
        }

        # Measure performance
        start_time = time.time()
        mappings = self.mapper.create_mappings(player_df, season_files)
        elapsed_time = time.time() - start_time

        # Should complete in under 2 seconds
        self.assertLess(elapsed_time, 2.0)

        # Verify mappings were created
        self.assertEqual(len(mappings), 500)

        # Check report
        report = self.mapper.get_match_report()
        self.assertEqual(report['total_players'], 500)

    def test_normalize_name_edge_cases(self):
        """Test edge cases in name normalization."""
        # Empty string
        self.assertEqual(normalize_name(""), "")

        # Just spaces
        self.assertEqual(normalize_name("   "), "")

        # Multiple spaces
        self.assertEqual(normalize_name("  John   Doe  "), "john doe")

        # Mixed case
        self.assertEqual(normalize_name("JoHn DoE"), "john doe")

        # Multiple suffixes
        self.assertEqual(normalize_name("John Doe Jr. III"), "john doe")

        # Apostrophes and hyphens
        self.assertEqual(normalize_name("D'Andre Swift-Jones"), "dandre swift jones")

        # Numbers (should be preserved)
        self.assertEqual(normalize_name("Player 99"), "player 99")


class TestPerformanceBenchmarks(unittest.TestCase):
    """Performance benchmarking tests - Task 1.4.3"""

    def setUp(self):
        """Set up test fixtures for performance testing."""
        self.test_dir = tempfile.mkdtemp()
        self.create_performance_test_files()

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def create_performance_test_files(self):
        """Create realistic-sized test files for performance testing."""
        # Create larger datasets for performance testing

        # Pass file - ~200 QBs
        qb_names = [f"QB Player {i:03d}" for i in range(200)]
        pass_data = pd.DataFrame({
            'Name': qb_names,
            'Team': ['KC', 'BUF', 'DAL', 'MIA'] * 50,
            'POS': ['QB'] * 200,
            'W': [1] * 200,
            'CPOE': [5.0] * 200,
            'aDOT': [8.0] * 200,
            'Deep Throw %': [25.0] * 200,
            '1Read %': [60.0] * 200
        })
        pass_data.to_excel(os.path.join(self.test_dir, 'Pass 2025.xlsx'), index=False)

        # Rush file - ~300 RBs
        rb_names = [f"RB Player {i:03d}" for i in range(300)]
        rush_data = pd.DataFrame({
            'Name': rb_names,
            'Team': ['BAL', 'CLE', 'GB', 'SF'] * 75,
            'POS': ['RB'] * 300,
            'W': [1] * 300,
            'YACO/ATT': [3.0] * 300,
            'MTF/ATT': [0.25] * 300,
            'Success Rate': [45.0] * 300,
            'STUFF %': [15.0] * 300
        })
        rush_data.to_excel(os.path.join(self.test_dir, 'Rush 2025.xlsx'), index=False)

        # Receiving file - ~500 WRs/TEs
        wr_names = [f"WR Player {i:03d}" for i in range(400)]
        te_names = [f"TE Player {i:03d}" for i in range(100)]
        receiving_data = pd.DataFrame({
            'Name': wr_names + te_names,
            'Team': ['DAL', 'MIN', 'MIA', 'KC'] * 125,
            'POS': ['WR'] * 400 + ['TE'] * 100,
            'W': [1] * 500,
            'TPRR': [0.25] * 500,
            'YPRR': [2.5] * 500,
            'RTE %': [85.0] * 500,
            '1READ %': [25.0] * 500,
            'CTGT %': [15.0] * 500
        })
        receiving_data.to_excel(os.path.join(self.test_dir, 'Receiving 2025.xlsx'), index=False)

        # Snaps file - All players
        all_names = qb_names[:100] + rb_names[:200] + wr_names[:150] + te_names[:50]
        snaps_data = pd.DataFrame({
            'Name': all_names,
            'Team': ['KC', 'BUF', 'DAL', 'MIA'] * 125,
            'POS': ['QB'] * 100 + ['RB'] * 200 + ['WR'] * 150 + ['TE'] * 50,
            'W': [1] * 500,
            'Snap %': [95.0] * 500,
            'FP/G': [20.0] * 500,
            'FP': [20.0] * 500
        })
        snaps_data.to_excel(os.path.join(self.test_dir, 'Snaps 2025.xlsx'), index=False)

    def test_file_loading_under_2_seconds(self):
        """Benchmark file loading: verify <2 seconds - Task 1.4.3 Requirement 1"""
        loader = FileLoader(self.test_dir)

        # Measure file loading time
        start_time = time.time()
        files = loader.load_all_files()
        loading_time = time.time() - start_time

        # Should be under 2 seconds
        self.assertLess(loading_time, 2.0, f"File loading took {loading_time:.2f}s, exceeds 2s limit")

        # Verify all files loaded
        self.assertIsNotNone(files['pass'])
        self.assertIsNotNone(files['rush'])
        self.assertIsNotNone(files['receiving'])
        self.assertIsNotNone(files['snaps'])

        # Check record counts
        self.assertEqual(len(files['pass']), 200)
        self.assertEqual(len(files['rush']), 300)
        self.assertEqual(len(files['receiving']), 500)
        self.assertEqual(len(files['snaps']), 500)

    def test_player_mapping_under_2_seconds(self):
        """Benchmark player mapping: verify <2 seconds - Task 1.4.3 Requirement 2"""
        # Load files first
        loader = FileLoader(self.test_dir)
        season_files = loader.load_all_files()

        # Create player DataFrame (500 players)
        player_names = []
        positions = []
        teams = []

        for i in range(100):  # 100 QBs
            player_names.append(f"QB Player {i:03d}")
            positions.append('QB')
            teams.append(['KC', 'BUF', 'DAL', 'MIA'][i % 4])

        for i in range(200):  # 200 RBs
            player_names.append(f"RB Player {i:03d}")
            positions.append('RB')
            teams.append(['BAL', 'CLE', 'GB', 'SF'][i % 4])

        for i in range(150):  # 150 WRs
            player_names.append(f"WR Player {i:03d}")
            positions.append('WR')
            teams.append(['DAL', 'MIN', 'MIA', 'KC'][i % 4])

        for i in range(50):  # 50 TEs
            player_names.append(f"TE Player {i:03d}")
            positions.append('TE')
            teams.append(['KC', 'BUF', 'DAL', 'MIA'][i % 4])

        player_df = pd.DataFrame({
            'name': player_names,
            'position': positions,
            'team': teams
        })

        # Measure mapping time
        mapper = PlayerNameMapper(threshold=85)
        start_time = time.time()
        mappings = mapper.create_mappings(player_df, season_files)
        mapping_time = time.time() - start_time

        # Should be under 2 seconds for 500 players
        self.assertLess(mapping_time, 2.0, f"Player mapping took {mapping_time:.2f}s, exceeds 2s limit")

        # Verify mappings created
        self.assertEqual(len(mappings), 500)

        # Check match rate
        report = mapper.get_match_report()
        self.assertGreaterEqual(report['match_rate'], 90)

    def test_memory_overhead_under_50mb(self):
        """Benchmark memory overhead: verify <50MB - Task 1.4.3 Requirement 3"""
        import tracemalloc

        # Start memory tracking
        tracemalloc.start()
        snapshot_start = tracemalloc.take_snapshot()

        # Load files
        loader = FileLoader(self.test_dir)
        files = loader.load_all_files()

        # Create player mappings
        player_df = pd.DataFrame({
            'name': [f"Player {i:03d}" for i in range(500)],
            'position': ['QB'] * 125 + ['RB'] * 125 + ['WR'] * 200 + ['TE'] * 50,
            'team': ['KC', 'BUF', 'DAL', 'MIA'] * 125
        })

        mapper = PlayerNameMapper(threshold=85)
        mappings = mapper.create_mappings(player_df, files)

        # Take memory snapshot
        snapshot_end = tracemalloc.take_snapshot()

        # Calculate memory usage
        stats = snapshot_end.compare_to(snapshot_start, 'lineno')
        total_memory = sum(stat.size_diff for stat in stats) / (1024 * 1024)  # Convert to MB

        tracemalloc.stop()

        # Memory overhead should be under 50MB
        self.assertLess(abs(total_memory), 50.0, f"Memory overhead {abs(total_memory):.2f}MB exceeds 50MB limit")

    def test_end_to_end_performance(self):
        """Test complete pipeline performance."""
        import tracemalloc

        # Track overall performance
        tracemalloc.start()
        start_time = time.time()

        # Step 1: Load files
        loader = FileLoader(self.test_dir)
        load_start = time.time()
        files = loader.load_all_files()
        load_time = time.time() - load_start

        # Step 2: Create player DataFrame
        player_df = pd.DataFrame({
            'name': [f"Player {i:03d}" for i in range(500)],
            'position': ['QB'] * 125 + ['RB'] * 125 + ['WR'] * 200 + ['TE'] * 50,
            'team': ['KC', 'BUF', 'DAL', 'MIA'] * 125,
            'salary': [8000] * 500,
            'projection': [15.0] * 500
        })

        # Step 3: Create mappings
        mapper = PlayerNameMapper(threshold=85)
        map_start = time.time()
        mappings = mapper.create_mappings(player_df, files)
        map_time = time.time() - map_start

        # Total time
        total_time = time.time() - start_time

        # Memory usage
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Log performance results
        performance_report = {
            'file_loading_time': f"{load_time:.3f}s",
            'player_mapping_time': f"{map_time:.3f}s",
            'total_time': f"{total_time:.3f}s",
            'peak_memory_mb': f"{peak / (1024 * 1024):.2f}MB",
            'files_loaded': loader.get_load_report()['files_loaded'],
            'players_mapped': len(mappings),
            'match_rate': mapper.get_match_report()['match_rate']
        }

        # Assert performance requirements
        self.assertLess(load_time, 2.0, "File loading exceeds 2s")
        self.assertLess(map_time, 2.0, "Player mapping exceeds 2s")
        self.assertLess(total_time, 5.0, "Total pipeline exceeds 5s")
        self.assertLess(peak / (1024 * 1024), 100.0, "Memory usage exceeds 100MB")

        # Print performance report for documentation
        print("\nPerformance Benchmark Results:")
        print("-" * 50)
        for key, value in performance_report.items():
            print(f"{key}: {value}")


class TestTeamNormalizer(unittest.TestCase):
    """Tests for TeamNormalizer class."""

    def test_all_team_variations(self):
        """Test comprehensive team abbreviation normalization."""
        # Test all known variations
        test_cases = [
            ('BLT', 'BAL'),  # Baltimore variations
            ('CLV', 'CLE'),  # Cleveland variations
            ('LA', 'LAR'),   # LA Rams variations
            ('LV', 'LVR'),   # Las Vegas variations
            ('KC', 'KC'),    # Kansas City (no change)
            ('WAS', 'WAS'),  # Washington (no change)
            ('WSH', 'WAS'),  # Washington alternate
            ('ARZ', 'ARI'),  # Arizona variations
            ('JAX', 'JAC'),  # Jacksonville variations
            ('JAC', 'JAC'),  # Jacksonville canonical
        ]

        for input_team, expected in test_cases:
            normalized = TeamNormalizer.normalize_team(input_team)
            self.assertEqual(normalized, expected, f"Failed to normalize {input_team} to {expected}")

    def test_dataframe_normalization_performance(self):
        """Test bulk DataFrame normalization performance."""
        # Create large DataFrame
        teams = ['BLT', 'CLV', 'LA', 'LV', 'KC', 'WAS'] * 100  # 600 rows
        df = pd.DataFrame({
            'Name': [f"Player {i}" for i in range(600)],
            'Team': teams
        })

        # Measure normalization time
        start_time = time.time()
        normalized_df = TeamNormalizer.normalize_dataframe(df)
        elapsed = time.time() - start_time

        # Should be very fast (under 0.1 seconds)
        self.assertLess(elapsed, 0.1)

        # Verify normalization
        self.assertEqual(normalized_df.loc[0, 'Team'], 'BAL')
        self.assertEqual(normalized_df.loc[1, 'Team'], 'CLE')
        self.assertEqual(normalized_df.loc[2, 'Team'], 'LAR')

    def test_team_consistency_validation(self):
        """Test validation of team consistency across multiple DataFrames."""
        dfs = {
            'pass': pd.DataFrame({
                'Team': ['BAL', 'KC', 'DAL', 'BUF']
            }),
            'rush': pd.DataFrame({
                'Team': ['BAL', 'KC', 'NYG']  # Missing DAL, BUF; has NYG
            }),
            'receiving': pd.DataFrame({
                'Team': ['BAL', 'KC', 'DAL', 'MIA']  # Missing BUF; has MIA
            }),
            'snaps': pd.DataFrame({
                'Team': ['BAL', 'KC']  # Only has 2 teams
            })
        }

        report = TeamNormalizer.validate_team_consistency(dfs)

        # Common teams should be BAL and KC
        self.assertIn('BAL', report['common_teams'])
        self.assertIn('KC', report['common_teams'])
        self.assertEqual(len(report['common_teams']), 2)

        # Should have warnings about inconsistencies
        self.assertGreater(len(report['warnings']), 0)

        # Check specific warnings
        self.assertIn('pass', report['unique_teams'])
        self.assertIn('rush', report['unique_teams'])


if __name__ == '__main__':
    # Configure logging for tests
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestFileLoader))
    suite.addTests(loader.loadTestsFromTestCase(TestPlayerNameMapper))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceBenchmarks))
    suite.addTests(loader.loadTestsFromTestCase(TestTeamNormalizer))

    # Run tests with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)