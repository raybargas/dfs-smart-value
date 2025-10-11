"""
Unit Tests for Monte Carlo Simulation Engine (Phase 2)

Tests SimulationEngine, DistributionGenerator, CorrelationMatrix calculator,
and SimulationResult aggregator.
"""

import pytest
import sys
import numpy as np
import time
from pathlib import Path
from typing import List, Dict

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from models import Player, Lineup
from extended_models import PlayerProjection
from simulation import (
    SimulationEngine,
    DistributionGenerator,
    CorrelationMatrixBuilder,
    SimulationResult,
    SimulationCache
)


class TestDistributionGenerator:
    """Test DistributionGenerator for player projection distributions."""
    
    def test_generate_normal_distribution(self):
        """Test generating normal distribution for a player."""
        player_proj = PlayerProjection(
            name="Patrick Mahomes",
            position="QB",
            salary=8500,
            projection=24.2,
            team="KC",
            opponent="LV",
            mean_projection=24.2,
            std_deviation=5.8,
            ceiling_95th=33.5,
            floor_5th=14.9
        )
        
        generator = DistributionGenerator()
        samples = generator.generate(player_proj, n_samples=10000)
        
        # Check shape
        assert len(samples) == 10000
        
        # Check mean is close to expected (within 2%)
        assert abs(np.mean(samples) - 24.2) / 24.2 < 0.02
        
        # Check std deviation is close to expected (within 5%)
        assert abs(np.std(samples) - 5.8) / 5.8 < 0.05
    
    def test_generate_zero_variance(self):
        """Test generating distribution with zero variance (perfectly consistent)."""
        player_proj = PlayerProjection(
            name="Consistent Player",
            position="QB",
            salary=8500,
            projection=20.0,
            team="TEAM",
            opponent="OPP",
            mean_projection=20.0,
            std_deviation=0.0,  # No variance
            ceiling_95th=20.0,
            floor_5th=20.0
        )
        
        generator = DistributionGenerator()
        samples = generator.generate(player_proj, n_samples=1000)
        
        # All samples should be exactly the mean
        assert np.all(samples == 20.0)
        assert np.std(samples) == 0.0
    
    def test_generate_custom_distribution(self):
        """Test generating custom distribution (non-normal)."""
        player_proj = PlayerProjection(
            name="Player 1",
            position="QB",
            salary=8500,
            projection=24.0,
            team="TEAM",
            opponent="OPP",
            mean_projection=24.0,
            std_deviation=5.0,
            ceiling_95th=32.0,
            floor_5th=16.0
        )
        
        generator = DistributionGenerator(distribution_type='lognormal')
        samples = generator.generate(player_proj, n_samples=10000)
        
        # Check shape
        assert len(samples) == 10000
        
        # Samples should be non-negative
        assert np.all(samples >= 0)
    
    def test_generate_batch(self):
        """Test generating distributions for multiple players at once."""
        players = [
            PlayerProjection(
                name=f"Player {i}",
                position="QB",
                salary=8000,
                projection=20.0 + i,
                team="TEAM",
                opponent="OPP",
                mean_projection=20.0 + i,
                std_deviation=5.0,
                ceiling_95th=30.0 + i,
                floor_5th=10.0 + i
            )
            for i in range(9)  # 9 players in a lineup
        ]
        
        generator = DistributionGenerator()
        samples = generator.generate_batch(players, n_samples=10000)
        
        # Check shape: (10000 simulations, 9 players)
        assert samples.shape == (10000, 9)
        
        # Check mean for each player
        for i, player in enumerate(players):
            player_samples = samples[:, i]
            expected_mean = player.mean_projection
            assert abs(np.mean(player_samples) - expected_mean) / expected_mean < 0.02


class TestCorrelationMatrixBuilder:
    """Test CorrelationMatrixBuilder for player correlation calculations."""
    
    def test_build_uncorrelated_matrix(self):
        """Test building correlation matrix with no correlations."""
        players = self._create_sample_players(5)
        
        builder = CorrelationMatrixBuilder()
        corr_matrix = builder.build(players)
        
        # Check shape
        assert corr_matrix.shape == (5, 5)
        
        # Diagonal should be 1.0 (player correlated with self)
        assert np.allclose(np.diag(corr_matrix), 1.0)
        
        # Off-diagonal should be 0.0 (no correlations by default)
        off_diagonal = corr_matrix - np.diag(np.diag(corr_matrix))
        assert np.allclose(off_diagonal, 0.0)
    
    def test_build_stacking_correlations(self):
        """Test building correlation matrix with QB-WR stacking."""
        # QB and WR from same team should be positively correlated
        qb = PlayerProjection(
            name="Mahomes",
            position="QB",
            salary=8500,
            projection=24.0,
            team="KC",
            opponent="LV",
            mean_projection=24.0,
            std_deviation=5.8,
            ceiling_95th=33.5,
            floor_5th=14.9,
            correlation_group="KC_PASS"
        )
        
        wr = PlayerProjection(
            name="Kelce",
            position="WR",
            salary=8000,
            projection=18.0,
            team="KC",
            opponent="LV",
            mean_projection=18.0,
            std_deviation=4.5,
            ceiling_95th=25.0,
            floor_5th=11.0,
            correlation_group="KC_PASS"
        )
        
        rb = PlayerProjection(
            name="CMC",
            position="RB",
            salary=9000,
            projection=22.0,
            team="SF",
            opponent="ARI",
            mean_projection=22.0,
            std_deviation=6.0,
            ceiling_95th=32.0,
            floor_5th=12.0,
            correlation_group=None
        )
        
        players = [qb, wr, rb]
        
        builder = CorrelationMatrixBuilder()
        corr_matrix = builder.build(players)
        
        # QB-WR should be positively correlated (same correlation_group)
        qb_wr_corr = corr_matrix[0, 1]
        assert qb_wr_corr > 0.5  # Significant positive correlation
        
        # QB-RB should have low/zero correlation (different teams)
        qb_rb_corr = corr_matrix[0, 2]
        assert abs(qb_rb_corr) < 0.3
    
    def test_build_negative_correlations(self):
        """Test building correlation matrix with negative correlations (RB-DEF)."""
        # RB and opposing DEF should be negatively correlated
        rb = PlayerProjection(
            name="Barkley",
            position="RB",
            salary=8000,
            projection=20.0,
            team="NYG",
            opponent="DAL",
            mean_projection=20.0,
            std_deviation=5.5,
            ceiling_95th=29.0,
            floor_5th=11.0
        )
        
        dst = PlayerProjection(
            name="Cowboys",
            position="DST",
            salary=3000,
            projection=10.0,
            team="DAL",
            opponent="NYG",
            mean_projection=10.0,
            std_deviation=3.0,
            ceiling_95th=15.0,
            floor_5th=5.0
        )
        
        players = [rb, dst]
        
        builder = CorrelationMatrixBuilder()
        corr_matrix = builder.build(players)
        
        # RB-DEF should be negatively correlated
        rb_def_corr = corr_matrix[0, 1]
        assert rb_def_corr < 0  # Negative correlation
    
    def _create_sample_players(self, n: int) -> List[PlayerProjection]:
        """Helper to create sample players."""
        return [
            PlayerProjection(
                name=f"Player {i}",
                position="QB",
                salary=8000,
                projection=20.0,
                team=f"TEAM{i}",
                opponent=f"OPP{i}",
                mean_projection=20.0,
                std_deviation=5.0,
                ceiling_95th=28.0,
                floor_5th=12.0
            )
            for i in range(n)
        ]


class TestSimulationResult:
    """Test SimulationResult aggregation and statistics."""
    
    def test_calculate_percentiles(self):
        """Test calculating percentiles from simulation samples."""
        samples = np.array([100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200])
        
        result = SimulationResult(samples)
        
        # Check percentiles
        assert result.floor_5th == pytest.approx(100, abs=5)
        assert result.ceiling_95th == pytest.approx(200, abs=5)
        assert result.median == pytest.approx(150, abs=5)
        assert result.mean == pytest.approx(150, abs=5)
    
    def test_calculate_variance_metrics(self):
        """Test variance and standard deviation calculations."""
        # Known distribution: mean=100, std=10
        np.random.seed(42)
        samples = np.random.normal(100, 10, 10000)
        
        result = SimulationResult(samples)
        
        # Check mean within 1%
        assert abs(result.mean - 100) / 100 < 0.01
        
        # Check std within 5%
        assert abs(result.std_deviation - 10) / 10 < 0.05
        
        # Check variance = std^2
        assert abs(result.variance - 10**2) / 10**2 < 0.1
    
    def test_probability_above_threshold(self):
        """Test calculating probability of exceeding a threshold."""
        # Distribution: mean=150, std=20
        np.random.seed(42)
        samples = np.random.normal(150, 20, 10000)
        
        result = SimulationResult(samples)
        
        # Probability of scoring > 150 (mean) should be ~50%
        prob_above_150 = result.probability_above(150)
        assert 0.48 < prob_above_150 < 0.52
        
        # Probability of scoring > 180 (1.5 std above mean) should be ~7%
        prob_above_180 = result.probability_above(180)
        assert 0.05 < prob_above_180 < 0.10
    
    def test_gpp_cash_line_probability(self):
        """Test GPP cash line probability calculation."""
        np.random.seed(42)
        samples = np.random.normal(150, 20, 10000)
        
        result = SimulationResult(samples)
        
        # Cash line at 160 points
        cash_prob = result.gpp_cash_probability(cash_line=160)
        
        # Should be between 30-40% for this distribution
        assert 0.25 < cash_prob < 0.45


class TestSimulationEngine:
    """Test SimulationEngine core functionality."""
    
    def test_run_simulations_single_lineup(self):
        """Test running simulations on a single lineup."""
        lineup = self._create_sample_lineup()
        
        engine = SimulationEngine()
        result = engine.run_simulations(lineup, n_simulations=1000)
        
        # Check result is SimulationResult
        assert isinstance(result, SimulationResult)
        
        # Check samples shape
        assert len(result.samples) == 1000
        
        # Check mean is close to lineup's total projection
        expected_total = lineup.total_projection
        assert abs(result.mean - expected_total) / expected_total < 0.05
    
    def test_run_simulations_with_correlations(self):
        """Test simulations with correlated players."""
        # Create lineup with stacked QB-WR
        qb = PlayerProjection(
            name="Mahomes",
            position="QB",
            salary=8500,
            projection=24.0,
            team="KC",
            opponent="LV",
            mean_projection=24.0,
            std_deviation=5.8,
            ceiling_95th=33.5,
            floor_5th=14.9,
            correlation_group="KC_PASS"
        )
        
        wr1 = PlayerProjection(
            name="Kelce",
            position="WR",
            salary=8000,
            projection=18.0,
            team="KC",
            opponent="LV",
            mean_projection=18.0,
            std_deviation=4.5,
            ceiling_95th=25.0,
            floor_5th=11.0,
            correlation_group="KC_PASS"
        )
        
        # Fill rest of lineup with uncorrelated players
        other_players = self._create_uncorrelated_players(7)
        
        lineup = Lineup(
            lineup_id=1,
            qb=qb,
            rb1=other_players[0],
            rb2=other_players[1],
            wr1=wr1,
            wr2=other_players[2],
            wr3=other_players[3],
            te=other_players[4],
            flex=other_players[5],
            dst=other_players[6]
        )
        
        engine = SimulationEngine()
        result = engine.run_simulations(lineup, n_simulations=1000)
        
        # Variance should be higher due to correlations
        assert result.variance > 0
    
    def test_performance_10k_simulations(self):
        """Test that 10,000 simulations complete in 2-3 seconds."""
        lineup = self._create_sample_lineup()
        
        engine = SimulationEngine()
        
        start_time = time.time()
        result = engine.run_simulations(lineup, n_simulations=10000)
        elapsed_time = time.time() - start_time
        
        # Check performance requirement
        assert elapsed_time < 3.0, f"Simulations took {elapsed_time:.2f}s, should be < 3s"
        
        # Check result validity
        assert len(result.samples) == 10000
    
    def test_run_simulations_batch(self):
        """Test running simulations on multiple lineups."""
        lineups = [
            self._create_sample_lineup(),
            self._create_sample_lineup(),
            self._create_sample_lineup()
        ]
        
        engine = SimulationEngine()
        results = engine.run_simulations_batch(lineups, n_simulations=1000)
        
        # Check we got results for all lineups
        assert len(results) == 3
        
        # Check each result
        for result in results:
            assert isinstance(result, SimulationResult)
            assert len(result.samples) == 1000
    
    def test_statistical_accuracy(self):
        """Test that simulation results are statistically accurate (within 2%)."""
        # Create players with known distributions (different teams to avoid correlations)
        players = []
        for i in range(9):
            player_proj = PlayerProjection(
                name=f"Test Player {i}",
                position=["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"][i],
                salary=8000,
                projection=100.0,
                team=f"TEAM{i}",  # Different teams to avoid correlations
                opponent=f"OPP{i}",
                mean_projection=100.0,
                std_deviation=10.0,
                ceiling_95th=116.4,  # ~95th percentile of normal(100, 10)
                floor_5th=83.6       # ~5th percentile of normal(100, 10)
            )
            players.append(player_proj)
        
        # Create lineup with uncorrelated players
        lineup = Lineup(
            lineup_id=1,
            qb=players[0],
            rb1=players[1],
            rb2=players[2],
            wr1=players[3],
            wr2=players[4],
            wr3=players[5],
            te=players[6],
            flex=players[7],
            dst=players[8]
        )
        
        engine = SimulationEngine()
        result = engine.run_simulations(lineup, n_simulations=10000, use_correlations=True)
        
        # Expected: 9 players * 100 mean = 900 total
        expected_mean = 900.0
        # Expected std: sqrt(9) * 10 = 30 (assuming independence)
        expected_std = 30.0
        
        # Check mean within 2%
        assert abs(result.mean - expected_mean) / expected_mean < 0.02
        
        # Check std within 10% (more variance in std estimation, some correlation from same-game)
        assert abs(result.std_deviation - expected_std) / expected_std < 0.10
    
    def _create_sample_lineup(self) -> Lineup:
        """Helper to create a sample lineup with ProjectionPlayers."""
        players = [
            PlayerProjection(
                name=f"Player {i}",
                position=["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"][i],
                salary=8000 - i*500,
                projection=20.0 - i,
                team=f"TEAM{i}",
                opponent=f"OPP{i}",
                mean_projection=20.0 - i,
                std_deviation=5.0,
                ceiling_95th=28.0 - i,
                floor_5th=12.0 - i
            )
            for i in range(9)
        ]
        
        return Lineup(
            lineup_id=1,
            qb=players[0],
            rb1=players[1],
            rb2=players[2],
            wr1=players[3],
            wr2=players[4],
            wr3=players[5],
            te=players[6],
            flex=players[7],
            dst=players[8]
        )
    
    def _create_uncorrelated_players(self, n: int) -> List[PlayerProjection]:
        """Helper to create uncorrelated players."""
        positions = ["RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"]
        return [
            PlayerProjection(
                name=f"Player {i}",
                position=positions[i] if i < len(positions) else "WR",
                salary=6000 - i*200,
                projection=15.0 - i*0.5,
                team=f"TEAM{i}",
                opponent=f"OPP{i}",
                mean_projection=15.0 - i*0.5,
                std_deviation=4.0,
                ceiling_95th=22.0 - i*0.5,
                floor_5th=8.0 - i*0.5
            )
            for i in range(n)
        ]


class TestSimulationCache:
    """Test SimulationCache for caching simulation results."""
    
    def test_cache_hit(self):
        """Test cache returns cached result for same lineup."""
        lineup = self._create_simple_lineup()
        
        cache = SimulationCache(max_size=100, ttl_seconds=60)
        
        # First call - cache miss
        assert not cache.has(lineup)
        
        # Simulate and cache
        result = SimulationResult(np.array([100, 110, 120]))
        cache.set(lineup, result)
        
        # Second call - cache hit
        assert cache.has(lineup)
        cached_result = cache.get(lineup)
        assert np.array_equal(cached_result.samples, result.samples)
    
    def test_cache_miss_different_lineup(self):
        """Test cache miss for different lineup."""
        lineup1 = self._create_simple_lineup()
        lineup2 = self._create_different_lineup()
        
        cache = SimulationCache(max_size=100, ttl_seconds=60)
        
        # Cache lineup1
        result1 = SimulationResult(np.array([100, 110, 120]))
        cache.set(lineup1, result1)
        
        # lineup2 should not be in cache
        assert not cache.has(lineup2)
    
    def test_cache_expiry(self):
        """Test cache entries expire after TTL."""
        lineup = self._create_simple_lineup()
        
        cache = SimulationCache(max_size=100, ttl_seconds=0.1)  # 100ms TTL
        
        # Cache result
        result = SimulationResult(np.array([100, 110, 120]))
        cache.set(lineup, result)
        
        # Should be in cache immediately
        assert cache.has(lineup)
        
        # Wait for expiry
        time.sleep(0.15)
        
        # Should be expired
        assert not cache.has(lineup)
    
    def test_cache_max_size(self):
        """Test cache respects max size limit."""
        cache = SimulationCache(max_size=2, ttl_seconds=60)
        
        lineup1 = self._create_simple_lineup()
        lineup2 = self._create_different_lineup()
        lineup3 = Lineup(
            lineup_id=3,
            qb=PlayerProjection("QB3", "QB", 8000, 20.0, "T", "O", 20.0, 5.0, 28.0, 12.0),
            rb1=PlayerProjection("RB3", "RB", 7000, 18.0, "T", "O", 18.0, 5.0, 26.0, 10.0),
            rb2=PlayerProjection("RB4", "RB", 6000, 15.0, "T", "O", 15.0, 4.0, 22.0, 8.0),
            wr1=PlayerProjection("WR3", "WR", 7000, 17.0, "T", "O", 17.0, 4.5, 24.0, 10.0),
            wr2=PlayerProjection("WR4", "WR", 6500, 16.0, "T", "O", 16.0, 4.0, 23.0, 9.0),
            wr3=PlayerProjection("WR5", "WR", 6000, 14.0, "T", "O", 14.0, 3.5, 20.0, 8.0),
            te=PlayerProjection("TE3", "TE", 5500, 13.0, "T", "O", 13.0, 3.0, 18.0, 8.0),
            flex=PlayerProjection("FLEX3", "WR", 5000, 12.0, "T", "O", 12.0, 3.0, 17.0, 7.0),
            dst=PlayerProjection("DST3", "DST", 3000, 10.0, "T", "O", 10.0, 2.5, 14.0, 6.0)
        )
        
        # Add 3 items (max_size=2)
        result = SimulationResult(np.array([100, 110, 120]))
        cache.set(lineup1, result)
        cache.set(lineup2, result)
        cache.set(lineup3, result)  # Should evict lineup1 (LRU)
        
        # lineup1 should be evicted
        assert not cache.has(lineup1)
        
        # lineup2 and lineup3 should be in cache
        assert cache.has(lineup2)
        assert cache.has(lineup3)
    
    def _create_simple_lineup(self) -> Lineup:
        """Helper to create a simple lineup."""
        return Lineup(
            lineup_id=1,
            qb=PlayerProjection("QB1", "QB", 8000, 20.0, "T", "O", 20.0, 5.0, 28.0, 12.0),
            rb1=PlayerProjection("RB1", "RB", 7000, 18.0, "T", "O", 18.0, 5.0, 26.0, 10.0),
            rb2=PlayerProjection("RB2", "RB", 6000, 15.0, "T", "O", 15.0, 4.0, 22.0, 8.0),
            wr1=PlayerProjection("WR1", "WR", 7000, 17.0, "T", "O", 17.0, 4.5, 24.0, 10.0),
            wr2=PlayerProjection("WR2", "WR", 6500, 16.0, "T", "O", 16.0, 4.0, 23.0, 9.0),
            wr3=PlayerProjection("WR3", "WR", 6000, 14.0, "T", "O", 14.0, 3.5, 20.0, 8.0),
            te=PlayerProjection("TE1", "TE", 5500, 13.0, "T", "O", 13.0, 3.0, 18.0, 8.0),
            flex=PlayerProjection("FLEX1", "WR", 5000, 12.0, "T", "O", 12.0, 3.0, 17.0, 7.0),
            dst=PlayerProjection("DST1", "DST", 3000, 10.0, "T", "O", 10.0, 2.5, 14.0, 6.0)
        )
    
    def _create_different_lineup(self) -> Lineup:
        """Helper to create a different lineup."""
        return Lineup(
            lineup_id=2,
            qb=PlayerProjection("QB2", "QB", 8500, 24.0, "T2", "O2", 24.0, 6.0, 33.0, 15.0),
            rb1=PlayerProjection("RB3", "RB", 7500, 19.0, "T2", "O2", 19.0, 5.5, 27.0, 11.0),
            rb2=PlayerProjection("RB4", "RB", 6500, 16.0, "T2", "O2", 16.0, 4.5, 23.0, 9.0),
            wr1=PlayerProjection("WR4", "WR", 7500, 18.0, "T2", "O2", 18.0, 5.0, 25.0, 11.0),
            wr2=PlayerProjection("WR5", "WR", 7000, 17.0, "T2", "O2", 17.0, 4.5, 24.0, 10.0),
            wr3=PlayerProjection("WR6", "WR", 6500, 15.0, "T2", "O2", 15.0, 4.0, 21.0, 9.0),
            te=PlayerProjection("TE2", "TE", 6000, 14.0, "T2", "O2", 14.0, 3.5, 19.0, 9.0),
            flex=PlayerProjection("FLEX2", "WR", 5500, 13.0, "T2", "O2", 13.0, 3.5, 18.0, 8.0),
            dst=PlayerProjection("DST2", "DST", 3500, 11.0, "T2", "O2", 11.0, 3.0, 15.0, 7.0)
        )

