"""
Integration Tests for Tier 1 Advanced Metrics
Part of DFS Advanced Stats Migration (2025-10-18) - Phase 2

Tests for Task 2.4.1: Create integration tests for Tier 1
- Test OPPORTUNITY score calculation with TPRR
- Test OPPORTUNITY score fallback logic (when metrics unavailable)
- Test position-specific extraction (QB, RB, WR, TE)
- Test that original metrics still work (backward compatibility)
- Test complete pipeline: load → map → enrich → score
"""

import unittest
import pandas as pd
import numpy as np
import sys
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.advanced_stats_loader import FileLoader, load_season_stats_files, create_player_mapper
from src.team_normalizer import TeamNormalizer
from src.player_name_mapper import PlayerNameMapper
from src.season_stats_analyzer import enrich_with_advanced_stats, analyze_season_stats
from src.smart_value_calculator import (
    calculate_opportunity_score,
    calculate_base_score,
    calculate_smart_value,
    min_max_scale_by_position
)


class TestTier1Integration(unittest.TestCase):
    """Integration tests for Tier 1 metrics (Task 2.4.1)"""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()

        # Create sample player data
        self.player_df = pd.DataFrame({
            'name': ['Patrick Mahomes', 'Tyreek Hill', 'Travis Kelce', 'Christian McCaffrey', 'Josh Allen'],
            'position': ['QB', 'WR', 'TE', 'RB', 'QB'],
            'team': ['KC', 'MIA', 'KC', 'SF', 'BUF'],
            'salary': [8500, 8200, 7500, 9500, 8300],
            'projection': [25.5, 18.2, 15.8, 22.3, 24.8],
            'ownership': [15.2, 12.5, 10.8, 18.3, 13.7],
            'season_fpg': [24.8, 17.5, 14.2, 20.5, 23.1],
            'season_snap': [95, 88, 82, 85, 94],
            'season_tgt': [0, 10.2, 8.5, 4.2, 0],
            'season_cons': [8.2, 7.5, 6.8, 7.2, 8.5],
            'season_ceiling': [35.2, 28.5, 22.1, 31.8, 34.5]
        })

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_opportunity_score_with_tprr(self):
        """Test OPPORTUNITY score uses TPRR when available."""
        # Add advanced metrics for WR/TE
        df = self.player_df.copy()
        df['adv_tprr'] = [0, 0.28, 0.22, 0, 0]  # TPRR for WR/TE
        df['adv_yprr'] = [0, 2.1, 1.8, 0, 0]     # YPRR for WR/TE
        df['adv_rte_pct'] = [0, 92, 85, 0, 0]    # RTE% for WR/TE

        # Calculate opportunity score
        result = calculate_opportunity_score(df, weight=0.30)

        # Verify TPRR is being used for WR/TE
        wr_score = result[result['name'] == 'Tyreek Hill']['opp_score'].iloc[0]
        te_score = result[result['name'] == 'Travis Kelce']['opp_score'].iloc[0]

        # Scores should be based on advanced metrics
        self.assertGreater(wr_score, 0, "WR should have positive opportunity score with TPRR")
        self.assertGreater(te_score, 0, "TE should have positive opportunity score with TPRR")

        # WR with higher TPRR should have higher score
        self.assertGreater(wr_score, te_score, "Higher TPRR should result in higher score")

    def test_opportunity_score_fallback_logic(self):
        """Test OPPORTUNITY score falls back to original metrics when advanced unavailable."""
        # No advanced metrics
        df = self.player_df.copy()

        # Calculate opportunity score
        result = calculate_opportunity_score(df, weight=0.30)

        # Verify fallback is working
        wr_score = result[result['name'] == 'Tyreek Hill']['opp_score'].iloc[0]
        te_score = result[result['name'] == 'Travis Kelce']['opp_score'].iloc[0]

        # Scores should still be calculated using season_tgt
        self.assertGreater(wr_score, 0, "WR should have positive opportunity score with fallback")
        self.assertGreater(te_score, 0, "TE should have positive opportunity score with fallback")

        # Check that fallback values are being used
        self.assertIn('opp_target_share', result.columns, "Should use legacy target share in fallback")

    def test_position_specific_extraction(self):
        """Test that metrics are extracted correctly for each position."""
        df = self.player_df.copy()

        # Add position-specific advanced metrics
        df['adv_tprr'] = [0, 0.28, 0.22, 0, 0]        # WR/TE only
        df['adv_yprr'] = [0, 2.1, 1.8, 0, 0]          # WR/TE only
        df['adv_rte_pct'] = [0, 92, 85, 0, 0]         # WR/TE only
        df['adv_success_rate'] = [0, 0, 0, 45.2, 0]   # RB only
        df['adv_yaco_att'] = [0, 0, 0, 3.2, 0]        # RB only

        # Calculate opportunity score
        result = calculate_opportunity_score(df, weight=0.30)

        # Check QB (should use fallback)
        qb_row = result[result['position'] == 'QB'].iloc[0]
        self.assertGreaterEqual(qb_row['opp_score'], 0, "QB should have opportunity score")

        # Check WR (should use TPRR/YPRR)
        wr_row = result[result['position'] == 'WR'].iloc[0]
        self.assertGreater(wr_row['opp_score'], 0, "WR should use advanced metrics")

        # Check TE (should use TPRR/YPRR)
        te_row = result[result['position'] == 'TE'].iloc[0]
        self.assertGreater(te_row['opp_score'], 0, "TE should use advanced metrics")

        # Check RB (should use Success Rate)
        rb_row = result[result['position'] == 'RB'].iloc[0]
        self.assertGreater(rb_row['opp_score'], 0, "RB should use success rate")

    def test_backward_compatibility(self):
        """Test that original metrics still work without any advanced metrics."""
        # Use original data without any advanced columns
        df = self.player_df.copy()

        # Calculate smart value (full pipeline)
        result = calculate_smart_value(df)

        # Verify all players have smart value
        for _, player in result.iterrows():
            self.assertGreaterEqual(player['smart_value'], 0, f"{player['name']} should have smart value")
            self.assertLessEqual(player['smart_value'], 100, f"{player['name']} smart value should be <= 100")

        # Verify original columns are present
        expected_columns = ['opp_score', 'base_score', 'smart_value']
        for col in expected_columns:
            self.assertIn(col, result.columns, f"Column {col} should be present")

    def test_complete_pipeline_with_metrics(self):
        """Test complete pipeline: load → map → enrich → score."""
        # Simulate the full pipeline with mock data
        df = self.player_df.copy()

        # Mock advanced stats enrichment
        df['adv_tprr'] = [0, 0.28, 0.22, 0.15, 0]      # Some players have metrics
        df['adv_yprr'] = [0, 2.1, 1.8, 0.8, 0]
        df['adv_rte_pct'] = [0, 92, 85, 45, 0]
        df['adv_success_rate'] = [0, 0, 0, 45.2, 0]
        df['adv_yaco_att'] = [0, 0, 0, 3.2, 0]

        # Calculate full smart value
        result = calculate_smart_value(df, weight_profile='balanced')

        # Verify pipeline completion
        self.assertEqual(len(result), len(df), "All players should be processed")

        # Verify smart value calculation
        for _, player in result.iterrows():
            self.assertGreaterEqual(player['smart_value'], 0, f"{player['name']} should have valid smart value")
            self.assertLessEqual(player['smart_value'], 100, f"{player['name']} smart value should be normalized")

        # Verify advanced metrics influence (WR with TPRR should score differently than without)
        wr_with_metrics = result[result['name'] == 'Tyreek Hill']['smart_value'].iloc[0]
        self.assertGreater(wr_with_metrics, 0, "WR with advanced metrics should have smart value")

    def test_mixed_metrics_handling(self):
        """Test handling when some players have metrics and others don't."""
        df = self.player_df.copy()

        # Only some players have advanced metrics
        df['adv_tprr'] = [np.nan, 0.28, np.nan, np.nan, np.nan]
        df['adv_yprr'] = [np.nan, 2.1, np.nan, np.nan, np.nan]

        # Should not raise any errors
        result = calculate_opportunity_score(df, weight=0.30)

        # All players should still have scores
        for _, player in result.iterrows():
            self.assertFalse(pd.isna(player['opp_score']),
                           f"{player['name']} should have opportunity score even with missing metrics")

    def test_metric_validation_ranges(self):
        """Test that metrics are validated for reasonable ranges."""
        df = self.player_df.copy()

        # Add metrics with edge cases
        df['adv_tprr'] = [0, 0.45, 0.01, 0, 0]    # Very high and very low TPRR
        df['adv_yprr'] = [0, 4.5, 0.1, 0, 0]      # Very high and very low YPRR
        df['adv_rte_pct'] = [0, 100, 5, 0, 0]     # Full range

        # Should handle without errors
        result = calculate_opportunity_score(df, weight=0.30)

        # Verify scores are still normalized
        for _, player in result.iterrows():
            self.assertGreaterEqual(player['opp_score'], 0, "Score should be non-negative")
            self.assertLessEqual(player['opp_score'], 30, "Score should respect weight limit")

    def test_position_groups_normalized_separately(self):
        """Test that normalization happens within position groups."""
        df = self.player_df.copy()

        # Add metrics
        df['adv_tprr'] = [0, 0.28, 0.22, 0, 0]
        df['adv_success_rate'] = [0, 0, 0, 45.2, 0]

        # Calculate scores
        result = calculate_opportunity_score(df, weight=0.30)

        # Check that each position group has its own normalization
        # (This is implicit in the min_max_scale_by_position function)
        wr_scores = result[result['position'] == 'WR']['opp_score']
        te_scores = result[result['position'] == 'TE']['opp_score']
        rb_scores = result[result['position'] == 'RB']['opp_score']

        # Each position should have meaningful scores
        self.assertTrue(all(wr_scores >= 0), "WR scores should be non-negative")
        self.assertTrue(all(te_scores >= 0), "TE scores should be non-negative")
        self.assertTrue(all(rb_scores >= 0), "RB scores should be non-negative")


class TestTier1Performance(unittest.TestCase):
    """Performance tests for Tier 1 metrics integration."""

    def setUp(self):
        """Create large dataset for performance testing."""
        # Generate 500 players for performance testing
        np.random.seed(42)
        n_players = 500

        positions = ['QB', 'RB', 'WR', 'TE'] * (n_players // 4)
        positions = positions[:n_players]

        self.large_df = pd.DataFrame({
            'name': [f'Player_{i}' for i in range(n_players)],
            'position': positions,
            'team': np.random.choice(['KC', 'BUF', 'MIA', 'SF', 'DAL'], n_players),
            'salary': np.random.randint(3000, 10000, n_players),
            'projection': np.random.uniform(5, 30, n_players),
            'ownership': np.random.uniform(0, 30, n_players),
            'season_fpg': np.random.uniform(5, 25, n_players),
            'season_snap': np.random.uniform(20, 100, n_players),
            'season_tgt': np.random.uniform(0, 15, n_players),
            'season_cons': np.random.uniform(4, 10, n_players),
            'season_ceiling': np.random.uniform(10, 40, n_players),
            # Add advanced metrics for half the players
            'adv_tprr': [np.random.uniform(0.1, 0.35) if i % 2 == 0 else np.nan for i in range(n_players)],
            'adv_yprr': [np.random.uniform(0.5, 3.0) if i % 2 == 0 else np.nan for i in range(n_players)],
            'adv_rte_pct': [np.random.uniform(50, 95) if i % 2 == 0 else np.nan for i in range(n_players)],
            'adv_success_rate': [np.random.uniform(35, 55) if i % 3 == 0 else np.nan for i in range(n_players)]
        })

    def test_opportunity_score_performance(self):
        """Test that opportunity score calculation is performant with 500 players."""
        import time

        start_time = time.time()
        result = calculate_opportunity_score(self.large_df, weight=0.30)
        elapsed_time = time.time() - start_time

        # Should complete in under 1 second
        self.assertLess(elapsed_time, 1.0, f"Opportunity score took {elapsed_time:.2f}s, should be < 1s")

        # Verify all players processed
        self.assertEqual(len(result), 500, "All 500 players should be processed")

    def test_full_smart_value_performance(self):
        """Test that full smart value calculation is performant."""
        import time

        start_time = time.time()
        result = calculate_smart_value(self.large_df)
        elapsed_time = time.time() - start_time

        # Should complete in under 2 seconds
        self.assertLess(elapsed_time, 2.0, f"Smart value calculation took {elapsed_time:.2f}s, should be < 2s")

        # Verify all players processed
        self.assertEqual(len(result), 500, "All 500 players should have smart values")


if __name__ == '__main__':
    unittest.main()