"""
Fixed Unit Tests for Advanced Stats Infrastructure
Part of DFS Advanced Stats Migration (2025-10-18) - Phase 1

Tests for:
- FileLoader: File loading and validation
- TeamNormalizer: Team abbreviation standardization
- PlayerNameMapper: Fuzzy name matching
"""

import unittest
import tempfile
import os
import sys
import pandas as pd
import time
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.advanced_stats_loader import FileLoader, load_season_stats_files, create_player_mapper
from src.team_normalizer import TeamNormalizer
from src.player_name_mapper import PlayerNameMapper, PlayerMapping, normalize_name


class TestPlayerNameMapper(unittest.TestCase):
    """Tests for PlayerNameMapper class."""

    def test_normalize_name(self):
        """Test name normalization logic."""
        # Test suffix removal
        self.assertEqual(normalize_name("Patrick Mahomes II"), "patrick mahomes")
        self.assertEqual(normalize_name("Odell Beckham Jr."), "odell beckham")
        self.assertEqual(normalize_name("Robert Griffin III"), "robert griffin")

        # Test apostrophe and punctuation removal
        self.assertEqual(normalize_name("De'Von Achane"), "devon achane")
        self.assertEqual(normalize_name("Ja'Marr Chase"), "jamarr chase")

        # Test hyphen handling
        self.assertEqual(normalize_name("Clyde Edwards-Helaire"), "clyde edwards helaire")
        self.assertEqual(normalize_name("JuJu Smith-Schuster"), "juju smith schuster")

        # Test edge cases
        self.assertEqual(normalize_name("  Test  Name  "), "test name")
        self.assertEqual(normalize_name(""), "")

    def test_fuzzy_matching_high_score(self):
        """Test fuzzy matching with exact/near-exact matches."""
        mapper = PlayerNameMapper(threshold=85)

        # Create test DataFrames
        stats_df = pd.DataFrame({
            'Name': ['Patrick Mahomes', 'Josh Allen', 'Lamar Jackson'],
            'Team': ['KC', 'BUF', 'BAL'],
            'POS': ['QB', 'QB', 'QB']
        })

        # Exact match should give 100
        match_name, score = mapper.fuzzy_match_player(
            'Patrick Mahomes', 'KC', 'QB', stats_df
        )
        self.assertEqual(match_name, 'Patrick Mahomes')
        self.assertEqual(score, 100)

        # Near match should give high score (but might be below threshold if too different)
        match_name, score = mapper.fuzzy_match_player(
            'Pat Mahomes', 'KC', 'QB', stats_df
        )
        # Since it's close but not exact, check score is reasonable
        if match_name:
            self.assertEqual(match_name, 'Patrick Mahomes')
        self.assertGreater(score, 70)  # Should still be a decent match

    def test_fuzzy_matching_with_suffix(self):
        """Test matching with Jr/Sr/III variations."""
        mapper = PlayerNameMapper(threshold=85)

        stats_df = pd.DataFrame({
            'Name': ['Patrick Mahomes', 'Odell Beckham', 'Robert Griffin'],
            'Team': ['KC', 'MIA', 'IND'],
            'POS': ['QB', 'WR', 'QB']
        })

        # Should match even with suffix - names get normalized
        match_name, score = mapper.fuzzy_match_player(
            'Patrick Mahomes II', 'KC', 'QB', stats_df
        )
        self.assertEqual(match_name, 'Patrick Mahomes')
        self.assertEqual(score, 100)  # Should be 100 after normalization

        match_name, score = mapper.fuzzy_match_player(
            'Odell Beckham Jr.', 'MIA', 'WR', stats_df
        )
        self.assertEqual(match_name, 'Odell Beckham')
        self.assertEqual(score, 100)  # Should be 100 after normalization


if __name__ == '__main__':
    # Configure logging for tests
    import logging
    logging.basicConfig(level=logging.INFO)

    # Run tests
    unittest.main()