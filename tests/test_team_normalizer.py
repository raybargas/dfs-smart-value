"""
Unit Tests for TeamNormalizer

Tests for the TeamNormalizer class from the DFS Advanced Stats Migration.
Part of Phase 1 Infrastructure Testing (Task 1.2.1).

Test Coverage:
- Team abbreviation normalization for all variations
- DataFrame normalization
- Team consistency validation
- Edge cases and error handling
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch
import logging

# Import the class to test
from DFS.src.team_normalizer import (
    TeamNormalizer,
    normalize_team,
    normalize_teams_in_dataframe
)


class TestTeamNormalizer:
    """
    Comprehensive tests for TeamNormalizer class functionality.

    Tests cover:
    - All team abbreviation variations
    - Static method behavior
    - DataFrame normalization
    - Team consistency validation
    """

    def test_normalize_team_baltimore_variations(self):
        """Test all Baltimore Ravens abbreviation variations."""
        assert TeamNormalizer.normalize_team('BLT') == 'BAL'
        assert TeamNormalizer.normalize_team('BALT') == 'BAL'
        assert TeamNormalizer.normalize_team('BAL') == 'BAL'
        assert TeamNormalizer.normalize_team('blt') == 'BAL'  # Case insensitive
        assert TeamNormalizer.normalize_team('Blt') == 'BAL'  # Mixed case

    def test_normalize_team_cleveland_variations(self):
        """Test all Cleveland Browns abbreviation variations."""
        assert TeamNormalizer.normalize_team('CLV') == 'CLE'
        assert TeamNormalizer.normalize_team('CLEV') == 'CLE'
        assert TeamNormalizer.normalize_team('CLE') == 'CLE'
        assert TeamNormalizer.normalize_team('clv') == 'CLE'  # Case insensitive

    def test_normalize_team_los_angeles_rams_variations(self):
        """Test all Los Angeles Rams abbreviation variations."""
        assert TeamNormalizer.normalize_team('LA') == 'LAR'
        assert TeamNormalizer.normalize_team('LA RAM') == 'LAR'
        assert TeamNormalizer.normalize_team('RAMS') == 'LAR'
        assert TeamNormalizer.normalize_team('LAR') == 'LAR'
        assert TeamNormalizer.normalize_team('la') == 'LAR'  # Case insensitive

    def test_normalize_team_las_vegas_variations(self):
        """Test all Las Vegas Raiders abbreviation variations."""
        assert TeamNormalizer.normalize_team('LV') == 'LVR'
        assert TeamNormalizer.normalize_team('LAS') == 'LVR'
        assert TeamNormalizer.normalize_team('RAID') == 'LVR'
        assert TeamNormalizer.normalize_team('OAK') == 'LVR'  # Old Oakland designation
        assert TeamNormalizer.normalize_team('LVR') == 'LVR'
        assert TeamNormalizer.normalize_team('lv') == 'LVR'  # Case insensitive

    def test_normalize_team_new_york_variations(self):
        """Test New York teams abbreviation variations."""
        # Giants
        assert TeamNormalizer.normalize_team('NY') == 'NYG'  # Default NY to Giants
        assert TeamNormalizer.normalize_team('NYG') == 'NYG'
        assert TeamNormalizer.normalize_team('GMEN') == 'NYG'

        # Jets
        assert TeamNormalizer.normalize_team('NYJ') == 'NYJ'
        assert TeamNormalizer.normalize_team('JETS') == 'NYJ'

    def test_normalize_team_los_angeles_chargers_variations(self):
        """Test all Los Angeles Chargers abbreviation variations."""
        assert TeamNormalizer.normalize_team('LAC') == 'LAC'
        assert TeamNormalizer.normalize_team('LA CHAR') == 'LAC'
        assert TeamNormalizer.normalize_team('CHAR') == 'LAC'
        assert TeamNormalizer.normalize_team('SD') == 'LAC'  # Old San Diego designation

    def test_normalize_team_washington_variations(self):
        """Test all Washington Commanders abbreviation variations."""
        assert TeamNormalizer.normalize_team('WAS') == 'WAS'
        assert TeamNormalizer.normalize_team('WASH') == 'WAS'
        assert TeamNormalizer.normalize_team('WSH') == 'WAS'
        assert TeamNormalizer.normalize_team('DC') == 'WAS'

    def test_normalize_team_arizona_variations(self):
        """Test all Arizona Cardinals abbreviation variations."""
        assert TeamNormalizer.normalize_team('ARI') == 'ARI'
        assert TeamNormalizer.normalize_team('ARZ') == 'ARI'
        assert TeamNormalizer.normalize_team('AZ') == 'ARI'
        assert TeamNormalizer.normalize_team('CARDS') == 'ARI'
        assert TeamNormalizer.normalize_team('PHX') == 'ARI'  # Old Phoenix designation

    def test_normalize_team_all_other_teams(self):
        """Test normalization for all other NFL teams."""
        # Test a sample of other team variations
        assert TeamNormalizer.normalize_team('KC') == 'KC'
        assert TeamNormalizer.normalize_team('KAN') == 'KC'
        assert TeamNormalizer.normalize_team('NE') == 'NE'
        assert TeamNormalizer.normalize_team('PAT') == 'NE'
        assert TeamNormalizer.normalize_team('TB') == 'TB'
        assert TeamNormalizer.normalize_team('BUCS') == 'TB'
        assert TeamNormalizer.normalize_team('SF') == 'SF'
        assert TeamNormalizer.normalize_team('49ERS') == 'SF'
        assert TeamNormalizer.normalize_team('GB') == 'GB'
        assert TeamNormalizer.normalize_team('PACK') == 'GB'
        assert TeamNormalizer.normalize_team('NO') == 'NO'
        assert TeamNormalizer.normalize_team('SAINTS') == 'NO'
        assert TeamNormalizer.normalize_team('JAC') == 'JAX'
        assert TeamNormalizer.normalize_team('JAX') == 'JAX'
        assert TeamNormalizer.normalize_team('JAGS') == 'JAX'

    def test_normalize_team_already_standard(self):
        """Test that standard abbreviations remain unchanged."""
        standard_teams = [
            'ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE',
            'DAL', 'DEN', 'DET', 'GB', 'HOU', 'IND', 'JAX', 'KC',
            'LAC', 'LAR', 'LVR', 'MIA', 'MIN', 'NE', 'NO', 'NYG',
            'NYJ', 'PHI', 'PIT', 'SEA', 'SF', 'TB', 'TEN', 'WAS'
        ]

        for team in standard_teams:
            assert TeamNormalizer.normalize_team(team) == team

    def test_normalize_team_edge_cases(self):
        """Test edge cases for team normalization."""
        # Test with None/NaN
        assert pd.isna(TeamNormalizer.normalize_team(None))
        assert pd.isna(TeamNormalizer.normalize_team(np.nan))
        assert pd.isna(TeamNormalizer.normalize_team(pd.NA))

        # Test with whitespace
        assert TeamNormalizer.normalize_team('  KC  ') == 'KC'
        assert TeamNormalizer.normalize_team('\tBLT\n') == 'BAL'

        # Test unknown team (should return as-is but log warning)
        with patch('DFS.src.team_normalizer.logger.warning') as mock_warning:
            result = TeamNormalizer.normalize_team('XYZ')
            assert result == 'XYZ'
            mock_warning.assert_called_once()

    def test_normalize_dataframe_basic(self):
        """Test DataFrame normalization with basic data."""
        # Create test DataFrame
        df = pd.DataFrame({
            'Name': ['Player 1', 'Player 2', 'Player 3', 'Player 4'],
            'Team': ['BLT', 'CLV', 'LA', 'LV'],
            'Position': ['QB', 'RB', 'WR', 'TE']
        })

        # Normalize
        normalized_df = TeamNormalizer.normalize_dataframe(df)

        # Verify
        assert normalized_df['Team'].tolist() == ['BAL', 'CLE', 'LAR', 'LVR']
        # Other columns should remain unchanged
        assert normalized_df['Name'].tolist() == ['Player 1', 'Player 2', 'Player 3', 'Player 4']
        assert normalized_df['Position'].tolist() == ['QB', 'RB', 'WR', 'TE']

    def test_normalize_dataframe_with_nan(self):
        """Test DataFrame normalization with NaN values."""
        df = pd.DataFrame({
            'Name': ['Player 1', 'Player 2', 'Player 3'],
            'Team': ['BLT', np.nan, 'CLV'],
            'Score': [10, 20, 30]
        })

        normalized_df = TeamNormalizer.normalize_dataframe(df)

        assert normalized_df['Team'].tolist()[0] == 'BAL'
        assert pd.isna(normalized_df['Team'].tolist()[1])
        assert normalized_df['Team'].tolist()[2] == 'CLE'

    def test_normalize_dataframe_no_team_column(self):
        """Test DataFrame normalization when 'Team' column is missing."""
        df = pd.DataFrame({
            'Name': ['Player 1', 'Player 2'],
            'Position': ['QB', 'RB']
        })

        # Should return DataFrame unchanged and log warning
        with patch('DFS.src.team_normalizer.logger.warning') as mock_warning:
            normalized_df = TeamNormalizer.normalize_dataframe(df)
            assert normalized_df.equals(df)
            mock_warning.assert_called_once()

    def test_normalize_dataframe_performance(self):
        """Test DataFrame normalization performance with large dataset."""
        # Create large DataFrame (5000 rows)
        teams = ['BLT', 'CLV', 'LA', 'LV', 'KC', 'SF', 'DAL', 'MIA'] * 625
        df = pd.DataFrame({
            'Name': [f'Player {i}' for i in range(5000)],
            'Team': teams,
            'Score': range(5000)
        })

        import time
        start_time = time.time()
        normalized_df = TeamNormalizer.normalize_dataframe(df)
        elapsed_time = time.time() - start_time

        # Verify performance (should be <0.1 seconds for 5000 rows)
        assert elapsed_time < 0.1, f"Normalization took {elapsed_time:.3f} seconds (target: <0.1 seconds)"

        # Verify correctness
        assert 'BAL' in normalized_df['Team'].values
        assert 'CLE' in normalized_df['Team'].values
        assert 'LAR' in normalized_df['Team'].values
        assert 'LVR' in normalized_df['Team'].values
        assert 'BLT' not in normalized_df['Team'].values

    def test_validate_team_consistency_all_consistent(self):
        """Test team consistency validation with consistent teams."""
        dataframes = {
            'pass': pd.DataFrame({'Team': ['KC', 'SF', 'DAL']}),
            'rush': pd.DataFrame({'Team': ['KC', 'SF', 'DAL']}),
            'receiving': pd.DataFrame({'Team': ['KC', 'SF', 'DAL']})
        }

        report = TeamNormalizer.validate_team_consistency(dataframes)

        assert report['valid'] == True
        assert set(report['common_teams']) == {'DAL', 'KC', 'SF'}
        assert len(report['warnings']) == 0
        assert len(report['inconsistencies']) == 0

    def test_validate_team_consistency_with_inconsistencies(self):
        """Test team consistency validation with inconsistent teams."""
        dataframes = {
            'pass': pd.DataFrame({'Team': ['KC', 'SF', 'DAL', 'NYG']}),
            'rush': pd.DataFrame({'Team': ['KC', 'SF', 'DAL']}),
            'receiving': pd.DataFrame({'Team': ['KC', 'SF', 'MIA']})
        }

        with patch('DFS.src.team_normalizer.logger.warning') as mock_warning:
            report = TeamNormalizer.validate_team_consistency(dataframes)

            # Common teams should only be those in all files
            assert set(report['common_teams']) == {'KC', 'SF'}

            # Should have warnings about unique teams
            assert len(report['warnings']) > 0
            assert mock_warning.called

    def test_validate_team_consistency_with_non_standard(self):
        """Test team consistency validation with non-standard abbreviations."""
        dataframes = {
            'pass': pd.DataFrame({'Team': ['KC', 'XYZ', 'DAL']}),  # XYZ is non-standard
            'rush': pd.DataFrame({'Team': ['KC', 'DAL']})
        }

        with patch('DFS.src.team_normalizer.logger.warning') as mock_warning:
            report = TeamNormalizer.validate_team_consistency(dataframes)

            # Should warn about non-standard team
            warnings_str = ' '.join(report['warnings'])
            assert 'XYZ' in warnings_str or 'Non-standard' in warnings_str
            assert mock_warning.called

    def test_validate_team_consistency_with_none_dataframes(self):
        """Test team consistency validation with None DataFrames."""
        dataframes = {
            'pass': pd.DataFrame({'Team': ['KC', 'SF']}),
            'rush': None,  # Missing file
            'receiving': pd.DataFrame({'Team': ['KC', 'SF']})
        }

        report = TeamNormalizer.validate_team_consistency(dataframes)

        # Should only process non-None DataFrames
        assert 'rush' not in report['teams_by_file']
        assert set(report['common_teams']) == {'KC', 'SF'}

    def test_get_team_mapping_report(self):
        """Test team mapping report generation."""
        report = TeamNormalizer.get_team_mapping_report()

        # Verify structure
        assert isinstance(report, dict)

        # Check some key mappings exist
        assert 'BAL' in report
        assert 'BLT' in report['BAL']
        assert 'BALT' in report['BAL']

        assert 'CLE' in report
        assert 'CLV' in report['CLE']

        assert 'LAR' in report
        assert 'LA' in report['LAR']

        assert 'LVR' in report
        assert 'LV' in report['LVR']
        assert 'OAK' in report['LVR']  # Old Oakland

    def test_convenience_functions(self):
        """Test module-level convenience functions."""
        # Test normalize_team function
        assert normalize_team('BLT') == 'BAL'
        assert normalize_team('CLV') == 'CLE'

        # Test normalize_teams_in_dataframe function
        df = pd.DataFrame({
            'Team': ['BLT', 'CLV', 'LA'],
            'Value': [1, 2, 3]
        })

        normalized_df = normalize_teams_in_dataframe(df)
        assert normalized_df['Team'].tolist() == ['BAL', 'CLE', 'LAR']

    def test_all_mapped_teams_are_valid(self):
        """Test that all team mappings resolve to valid NFL teams."""
        for variation, standard in TeamNormalizer.TEAM_MAPPING.items():
            assert standard in TeamNormalizer.VALID_TEAMS, \
                f"Mapping {variation} → {standard}, but {standard} is not in VALID_TEAMS"

    def test_valid_teams_count(self):
        """Test that we have exactly 32 valid NFL teams."""
        assert len(TeamNormalizer.VALID_TEAMS) == 32, \
            f"Expected 32 NFL teams, found {len(TeamNormalizer.VALID_TEAMS)}"


class TestIntegrationWithFileLoader:
    """Integration tests for TeamNormalizer with FileLoader."""

    def test_file_loader_applies_normalization(self):
        """Test that FileLoader correctly applies team normalization."""
        import tempfile
        import os
        from DFS.src.advanced_stats_loader import FileLoader, FILE_PATTERNS

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file with non-standard teams
            file_path = os.path.join(tmpdir, FILE_PATTERNS['snaps'])
            df = pd.DataFrame({
                'Name': ['Player 1', 'Player 2'],
                'Team': ['BLT', 'CLV'],
                'POS': ['QB', 'RB'],
                'W': [1, 1],
                'Snap %': [80.0, 70.0],
                'FP/G': [20.0, 15.0],
                'FP': [20.0, 15.0]
            })
            df.to_excel(file_path, index=False)

            # Load with FileLoader
            loader = FileLoader(tmpdir)
            files = loader.load_all_files()

            # Verify normalization was applied
            snaps_df = files['snaps']
            if snaps_df is not None:
                assert 'BAL' in snaps_df['Team'].values
                assert 'CLE' in snaps_df['Team'].values
                assert 'BLT' not in snaps_df['Team'].values
                assert 'CLV' not in snaps_df['Team'].values


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])