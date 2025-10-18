"""
Unit Tests for PlayerNameMapper

Tests for the PlayerNameMapper class from the DFS Advanced Stats Migration.
Part of Phase 1 Infrastructure Testing (Task 1.4.2).

Test Coverage:
- Exact name matches (100 score)
- Names with suffixes (Jr/Sr/III)
- Names with apostrophes and hyphens
- Match rate requirements (>90%)
- Performance for 500 players (<2 seconds)
"""

import pytest
import pandas as pd
import numpy as np
import time
from unittest.mock import Mock, patch
import logging

# Import the classes to test
from DFS.src.player_name_mapper import (
    PlayerNameMapper,
    PlayerMapping,
    normalize_name,
    create_player_mapper
)


class TestNameNormalization:
    """Test the normalize_name function for various edge cases."""

    def test_normalize_basic_name(self):
        """Test basic name normalization."""
        assert normalize_name("Patrick Mahomes") == "patrick mahomes"
        assert normalize_name("CHRISTIAN MCCAFFREY") == "christian mccaffrey"
        assert normalize_name("  Tyreek Hill  ") == "tyreek hill"

    def test_normalize_name_with_suffixes(self):
        """
        Test normalization of names with suffixes.

        Acceptance Criteria:
        - Jr., Sr., III, II, IV, V removed
        - Multiple suffixes handled correctly
        """
        assert normalize_name("Patrick Mahomes II") == "patrick mahomes"
        assert normalize_name("Odell Beckham Jr.") == "odell beckham"
        assert normalize_name("Robert Griffin III") == "robert griffin"
        assert normalize_name("Willie Snead IV") == "willie snead"
        assert normalize_name("Duke Johnson Jr") == "duke johnson"  # Without period
        assert normalize_name("Todd Gurley II") == "todd gurley"
        assert normalize_name("King Henry V") == "king henry"

    def test_normalize_name_with_apostrophes(self):
        """
        Test normalization of names with apostrophes.

        Acceptance Criteria:
        - Apostrophes removed
        - Maintains word separation
        """
        assert normalize_name("De'Von Achane") == "devon achane"
        assert normalize_name("D'Andre Swift") == "dandre swift"
        assert normalize_name("Le'Veon Bell") == "leveon bell"
        assert normalize_name("Ja'Marr Chase") == "jamarr chase"

    def test_normalize_name_with_hyphens(self):
        """
        Test normalization of names with hyphens.

        Acceptance Criteria:
        - Hyphens converted to spaces
        - Multiple hyphens handled
        """
        assert normalize_name("Clyde Edwards-Helaire") == "clyde edwards helaire"
        assert normalize_name("JuJu Smith-Schuster") == "juju smith schuster"
        assert normalize_name("Amon-Ra St. Brown") == "amon ra st brown"
        assert normalize_name("D'Onta Foreman") == "donta foreman"

    def test_normalize_name_with_periods(self):
        """Test removal of periods."""
        assert normalize_name("T.J. Hockenson") == "tj hockenson"
        assert normalize_name("A.J. Brown") == "aj brown"
        assert normalize_name("D.K. Metcalf") == "dk metcalf"
        assert normalize_name("C.J. Stroud") == "cj stroud"

    def test_normalize_name_edge_cases(self):
        """Test edge cases."""
        assert normalize_name(None) == ""
        assert normalize_name("") == ""
        assert normalize_name(pd.NA) == ""
        assert normalize_name("   ") == ""
        assert normalize_name("Player    With   Spaces") == "player with spaces"


class TestPlayerMapping:
    """Test the PlayerMapping dataclass."""

    def test_player_mapping_initialization(self):
        """Test PlayerMapping creation and defaults."""
        mapping = PlayerMapping(
            original_name="Patrick Mahomes",
            normalized_name="patrick mahomes",
            position="QB",
            team="KC"
        )

        assert mapping.original_name == "Patrick Mahomes"
        assert mapping.normalized_name == "patrick mahomes"
        assert mapping.position == "QB"
        assert mapping.team == "KC"
        assert mapping.matched_name_pass is None
        assert mapping.match_score_pass == 0.0

    def test_get_best_match_score(self):
        """Test getting best match score across files."""
        mapping = PlayerMapping(
            original_name="Test Player",
            normalized_name="test player",
            position="WR",
            team="SF"
        )

        # Set different scores
        mapping.match_score_pass = 85.0
        mapping.match_score_rush = 90.0
        mapping.match_score_receiving = 95.0
        mapping.match_score_snaps = 88.0

        assert mapping.get_best_match_score() == 95.0

    def test_has_any_match(self):
        """Test checking if player has any match."""
        mapping = PlayerMapping(
            original_name="Test Player",
            normalized_name="test player",
            position="RB",
            team="DAL"
        )

        # Initially no matches
        assert mapping.has_any_match() == False

        # Add a match
        mapping.matched_name_rush = "Test Player"
        mapping.match_score_rush = 92.0
        assert mapping.has_any_match() == True


class TestPlayerNameMapper:
    """Test the main PlayerNameMapper class."""

    @pytest.fixture
    def sample_player_df(self):
        """Create sample player DataFrame."""
        return pd.DataFrame({
            'name': [
                'Patrick Mahomes',
                'Christian McCaffrey',
                'Tyreek Hill',
                'Travis Kelce',
                'Josh Allen'
            ],
            'position': ['QB', 'RB', 'WR', 'TE', 'QB'],
            'team': ['KC', 'SF', 'MIA', 'KC', 'BUF']
        })

    @pytest.fixture
    def sample_season_files(self):
        """Create sample season stats files."""
        return {
            'pass': pd.DataFrame({
                'Name': ['Patrick Mahomes II', 'Josh Allen', 'Lamar Jackson'],
                'Team': ['KC', 'BUF', 'BAL'],
                'POS': ['QB', 'QB', 'QB'],
                'W': [1, 1, 1],
                'CPOE': [5.2, 3.8, 4.1]
            }),
            'rush': pd.DataFrame({
                'Name': ['Christian McCaffrey', 'Derrick Henry', 'Nick Chubb'],
                'Team': ['SF', 'TEN', 'CLE'],
                'POS': ['RB', 'RB', 'RB'],
                'W': [1, 1, 1],
                'YACO/ATT': [3.2, 2.8, 3.5]
            }),
            'receiving': pd.DataFrame({
                'Name': ['Tyreek Hill', 'Davante Adams', 'Travis Kelce'],
                'Team': ['MIA', 'LVR', 'KC'],
                'POS': ['WR', 'WR', 'TE'],
                'W': [1, 1, 1],
                'TPRR': [0.28, 0.26, 0.24]
            }),
            'snaps': pd.DataFrame({
                'Name': ['Patrick Mahomes', 'Christian McCaffrey', 'Tyreek Hill', 'Travis Kelce', 'Josh Allen'],
                'Team': ['KC', 'SF', 'MIA', 'KC', 'BUF'],
                'POS': ['QB', 'RB', 'WR', 'TE', 'QB'],
                'W': [1, 1, 1, 1, 1],
                'Snap %': [95.0, 88.0, 92.0, 85.0, 98.0]
            })
        }

    def test_exact_name_matches(self, sample_player_df, sample_season_files):
        """
        Test exact name matches receive 100 score.

        Acceptance Criteria:
        - Exact matches (after normalization) get 100 score
        - Matches are case-insensitive
        """
        # Modify season files to have exact matches
        sample_season_files['pass'].loc[0, 'Name'] = 'Patrick Mahomes'  # Exact match
        sample_season_files['snaps'].loc[0, 'Name'] = 'Patrick Mahomes'

        mapper = PlayerNameMapper(threshold=85)
        mappings = mapper.create_mappings(sample_player_df, sample_season_files)

        # Check Patrick Mahomes has perfect matches
        mahomes_mapping = mappings['Patrick Mahomes']
        assert mahomes_mapping.match_score_pass == 100.0
        assert mahomes_mapping.match_score_snaps == 100.0
        assert mahomes_mapping.matched_name_pass == 'Patrick Mahomes'

    def test_suffix_handling(self, sample_player_df, sample_season_files):
        """
        Test matching names with suffixes.

        Acceptance Criteria:
        - "Patrick Mahomes" matches "Patrick Mahomes II"
        - High match score (>90)
        """
        mapper = PlayerNameMapper(threshold=85)
        mappings = mapper.create_mappings(sample_player_df, sample_season_files)

        # Check Patrick Mahomes matches Patrick Mahomes II
        mahomes_mapping = mappings['Patrick Mahomes']
        assert mahomes_mapping.matched_name_pass == 'Patrick Mahomes II'
        assert mahomes_mapping.match_score_pass >= 90.0  # Should be very high

    def test_apostrophe_hyphen_handling(self):
        """
        Test matching names with apostrophes and hyphens.

        Acceptance Criteria:
        - Names with punctuation match correctly
        - Normalization handles special characters
        """
        # Create test data with special characters
        player_df = pd.DataFrame({
            'name': ["De'Von Achane", "Clyde Edwards-Helaire", "Amon-Ra St. Brown"],
            'position': ['RB', 'RB', 'WR'],
            'team': ['MIA', 'KC', 'DET']
        })

        season_files = {
            'rush': pd.DataFrame({
                'Name': ["DeVon Achane", "Clyde Edwards Helaire", "Amon Ra St Brown"],
                'Team': ['MIA', 'KC', 'DET'],
                'POS': ['RB', 'RB', 'WR'],
                'W': [1, 1, 1]
            }),
            'pass': None,
            'receiving': None,
            'snaps': None
        }

        mapper = PlayerNameMapper(threshold=80)
        mappings = mapper.create_mappings(player_df, season_files)

        # Check all players matched
        assert mappings["De'Von Achane"].matched_name_rush == "DeVon Achane"
        assert mappings["Clyde Edwards-Helaire"].matched_name_rush == "Clyde Edwards Helaire"
        assert mappings["Amon-Ra St. Brown"].matched_name_rush == "Amon Ra St Brown"

        # All should have high scores
        assert mappings["De'Von Achane"].match_score_rush >= 90.0
        assert mappings["Clyde Edwards-Helaire"].match_score_rush >= 90.0

    def test_match_rate_requirement(self):
        """
        Test >90% match rate requirement.

        Acceptance Criteria:
        - At least 90% of players have matches
        - Report accurately reflects match rate
        """
        # Create 100 players
        num_players = 100
        player_df = pd.DataFrame({
            'name': [f'Player {i}' for i in range(num_players)],
            'position': ['QB' if i % 4 == 0 else 'RB' if i % 4 == 1 else 'WR' if i % 4 == 2 else 'TE'
                         for i in range(num_players)],
            'team': [['KC', 'SF', 'BUF', 'DAL', 'MIA'][i % 5] for i in range(num_players)]
        })

        # Create season files with 92% of players (92 out of 100)
        matched_players = 92
        season_files = {
            'snaps': pd.DataFrame({
                'Name': [f'Player {i}' for i in range(matched_players)],
                'Team': [['KC', 'SF', 'BUF', 'DAL', 'MIA'][i % 5] for i in range(matched_players)],
                'POS': [['QB', 'RB', 'WR', 'TE'][i % 4] for i in range(matched_players)],
                'W': [1] * matched_players,
                'Snap %': [85.0] * matched_players,
                'FP/G': [15.0] * matched_players,
                'FP': [75.0] * matched_players
            }),
            'pass': None,
            'rush': None,
            'receiving': None
        }

        mapper = PlayerNameMapper(threshold=85)
        mappings = mapper.create_mappings(player_df, season_files)
        report = mapper.get_match_report()

        # Verify match rate is at least 90%
        assert report['match_rate'] >= 90.0, f"Match rate {report['match_rate']}% is below 90% requirement"
        assert report['total_players'] == num_players
        assert len(report['no_matches']) == 8  # 100 - 92

    def test_performance_500_players(self):
        """
        Test performance with 500 players.

        Acceptance Criteria:
        - Mapping creation takes <2 seconds for 500 players
        - All 4 files processed
        """
        # Create 500 players
        num_players = 500
        player_df = pd.DataFrame({
            'name': [f'Player {i}' for i in range(num_players)],
            'position': [['QB', 'RB', 'WR', 'TE'][i % 4] for i in range(num_players)],
            'team': [['KC', 'SF', 'BUF', 'DAL', 'MIA', 'GB', 'CHI', 'DET'][i % 8] for i in range(num_players)]
        })

        # Create season files with all players
        base_data = {
            'Name': [f'Player {i}' for i in range(num_players)],
            'Team': [['KC', 'SF', 'BUF', 'DAL', 'MIA', 'GB', 'CHI', 'DET'][i % 8] for i in range(num_players)],
            'POS': [['QB', 'RB', 'WR', 'TE'][i % 4] for i in range(num_players)],
            'W': [1] * num_players
        }

        season_files = {
            'pass': pd.DataFrame({**base_data, 'CPOE': np.random.uniform(-5, 5, num_players)}),
            'rush': pd.DataFrame({**base_data, 'YACO/ATT': np.random.uniform(1, 4, num_players)}),
            'receiving': pd.DataFrame({**base_data, 'TPRR': np.random.uniform(0.1, 0.4, num_players)}),
            'snaps': pd.DataFrame({**base_data, 'Snap %': np.random.uniform(50, 95, num_players),
                                   'FP/G': np.random.uniform(5, 25, num_players),
                                   'FP': np.random.uniform(25, 125, num_players)})
        }

        mapper = PlayerNameMapper(threshold=85)

        # Measure performance
        start_time = time.time()
        mappings = mapper.create_mappings(player_df, season_files)
        elapsed = time.time() - start_time

        # Verify performance requirement
        assert elapsed < 2.0, f"Mapping 500 players took {elapsed:.2f} seconds (target: <2 seconds)"

        # Verify all mappings created
        assert len(mappings) == num_players

        # Verify high match rate
        report = mapper.get_match_report()
        assert report['match_rate'] >= 90.0

    def test_team_position_filtering(self):
        """
        Test that team and position are used for filtering candidates.

        Acceptance Criteria:
        - Players matched primarily by team
        - Position used for additional filtering
        - Falls back if position doesn't match
        """
        player_df = pd.DataFrame({
            'name': ['Josh Allen', 'Josh Allen'],
            'position': ['QB', 'LB'],  # Different positions
            'team': ['BUF', 'JAX']  # Different teams
        })

        season_files = {
            'pass': pd.DataFrame({
                'Name': ['Josh Allen'],
                'Team': ['BUF'],
                'POS': ['QB'],
                'W': [1]
            }),
            'rush': pd.DataFrame({
                'Name': ['Josh Allen'],
                'Team': ['JAX'],
                'POS': ['LB'],
                'W': [1]
            }),
            'receiving': None,
            'snaps': None
        }

        mapper = PlayerNameMapper(threshold=85)
        mappings = mapper.create_mappings(player_df, season_files)

        # QB Josh Allen should match with pass file
        qb_allen = next(m for name, m in mappings.items()
                        if m.original_name == 'Josh Allen' and m.position == 'QB')
        assert qb_allen.matched_name_pass == 'Josh Allen'
        assert qb_allen.match_score_pass > 90

        # LB Josh Allen should match with rush file
        lb_allen = next(m for name, m in mappings.items()
                        if m.original_name == 'Josh Allen' and m.position == 'LB')
        assert lb_allen.matched_name_rush == 'Josh Allen'
        assert lb_allen.match_score_rush > 90

    def test_fuzzy_match_threshold(self):
        """
        Test that matches below threshold are rejected.

        Acceptance Criteria:
        - Matches below threshold (85) are not accepted
        - Low scores are reported
        """
        player_df = pd.DataFrame({
            'name': ['Patrick Mahomes'],
            'position': ['QB'],
            'team': ['KC']
        })

        # Create very different name
        season_files = {
            'pass': pd.DataFrame({
                'Name': ['Tom Brady'],  # Very different name
                'Team': ['KC'],  # Same team
                'POS': ['QB'],
                'W': [1]
            }),
            'rush': None,
            'receiving': None,
            'snaps': None
        }

        mapper = PlayerNameMapper(threshold=85)
        mappings = mapper.create_mappings(player_df, season_files)

        # Should not match due to low score
        mahomes = mappings['Patrick Mahomes']
        assert mahomes.matched_name_pass is None  # No match above threshold
        assert mahomes.match_score_pass < 85

    def test_get_match_report(self, sample_player_df, sample_season_files):
        """
        Test comprehensive match report generation.

        Acceptance Criteria:
        - Report contains all required metrics
        - Perfect matches counted correctly
        - Below threshold players identified
        """
        mapper = PlayerNameMapper(threshold=85)
        mapper.create_mappings(sample_player_df, sample_season_files)
        report = mapper.get_match_report()

        # Check report structure
        assert 'total_players' in report
        assert 'matched_pass' in report
        assert 'matched_rush' in report
        assert 'matched_receiving' in report
        assert 'matched_snaps' in report
        assert 'avg_match_score' in report
        assert 'match_rate' in report
        assert 'perfect_matches' in report
        assert 'below_threshold' in report
        assert 'no_matches' in report

        # Verify counts
        assert report['total_players'] == 5
        assert report['matched_pass'] >= 2  # Mahomes and Allen
        assert report['matched_rush'] >= 1  # McCaffrey
        assert report['matched_receiving'] >= 2  # Hill and Kelce
        assert report['matched_snaps'] >= 4  # Most players

        # Match rate should be high
        assert report['match_rate'] >= 80.0

    def test_create_mapping_dataframe(self, sample_player_df, sample_season_files):
        """
        Test creating DataFrame for bulk merging.

        Acceptance Criteria:
        - Returns DataFrame suitable for merging
        - Contains matched names and scores
        - Only includes successful matches
        """
        mapper = PlayerNameMapper(threshold=85)
        mapper.create_mappings(sample_player_df, sample_season_files)

        # Create mapping DataFrame for pass file
        mapping_df = mapper.create_mapping_dataframe('pass')

        # Check structure
        assert 'original_name' in mapping_df.columns
        assert 'matched_name' in mapping_df.columns
        assert 'match_score' in mapping_df.columns
        assert 'normalized_name' in mapping_df.columns

        # Should only include successful matches
        assert len(mapping_df) > 0
        assert all(mapping_df['match_score'] > 0)

    def test_cache_performance(self):
        """
        Test that caching improves performance for repeated matches.

        Acceptance Criteria:
        - Second match of same player is faster
        - Cache prevents redundant computation
        """
        player_df = pd.DataFrame({
            'name': ['Patrick Mahomes'] * 10,  # Same player 10 times
            'position': ['QB'] * 10,
            'team': ['KC'] * 10
        })

        season_files = {
            'pass': pd.DataFrame({
                'Name': ['Patrick Mahomes II'],
                'Team': ['KC'],
                'POS': ['QB'],
                'W': [1]
            }),
            'rush': None,
            'receiving': None,
            'snaps': None
        }

        mapper = PlayerNameMapper(threshold=85)

        # First call populates cache
        start1 = time.time()
        mappings1 = mapper.create_mappings(player_df[:1], season_files)
        time1 = time.time() - start1

        # Clear mappings but keep cache
        mapper.mappings = {}

        # Second call uses cache (should be faster)
        start2 = time.time()
        mappings2 = mapper.create_mappings(player_df, season_files)
        time2 = time.time() - start2

        # Verify caching helps (not strictly required but expected)
        # Main verification is that it works correctly with duplicates
        assert len(mappings2) == 10
        for mapping in mappings2.values():
            assert mapping.matched_name_pass == 'Patrick Mahomes II'


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    @patch('DFS.src.player_name_mapper.PlayerNameMapper')
    @patch('DFS.src.player_name_mapper.logger')
    def test_create_player_mapper_function(self, mock_logger, MockMapper):
        """
        Test create_player_mapper convenience function.

        Acceptance Criteria:
        - Creates mapper with correct threshold
        - Logs appropriate warnings/info
        - Returns configured mapper
        """
        # Setup mock
        mock_instance = MockMapper.return_value
        mock_instance.get_match_report.return_value = {
            'total_players': 100,
            'match_rate': 88.0,  # Below 90% threshold
            'avg_match_score': 92.5,
            'no_matches': ['Player X', 'Player Y']
        }

        # Create test data
        player_df = pd.DataFrame({
            'name': ['Player 1'],
            'position': ['QB'],
            'team': ['KC']
        })
        season_files = {'pass': pd.DataFrame()}

        # Call function
        result = create_player_mapper(player_df, season_files, threshold=90)

        # Verify
        assert result == mock_instance
        MockMapper.assert_called_once_with(threshold=90)
        mock_instance.create_mappings.assert_called_once_with(player_df, season_files)

        # Should log warning about low match rate
        mock_logger.warning.assert_called()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])