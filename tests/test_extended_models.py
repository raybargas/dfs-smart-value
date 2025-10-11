"""
Unit Tests for Extended Data Models (Phase 2)

Tests PlayerProjection, GameScenario, and LineupPortfolio models.
"""

import pytest
import sys
import numpy as np
from pathlib import Path
from typing import Dict, List

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from models import Player, Lineup
from extended_models import PlayerProjection, GameScenario, LineupPortfolio, ScenarioType


class TestPlayerProjectionCreation:
    """Test PlayerProjection model creation and extension of Player."""
    
    def test_create_valid_player_projection(self):
        """Test creating a valid PlayerProjection with all projection fields."""
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
            floor_5th=14.9,
            correlation_group="KC_PASS"
        )
        
        assert player_proj.name == "Patrick Mahomes"
        assert player_proj.mean_projection == 24.2
        assert player_proj.std_deviation == 5.8
        assert player_proj.ceiling_95th == 33.5
        assert player_proj.floor_5th == 14.9
        assert player_proj.correlation_group == "KC_PASS"
    
    def test_player_projection_inherits_from_player(self):
        """Test that PlayerProjection inherits all Player functionality."""
        player_proj = PlayerProjection(
            name="Christian McCaffrey",
            position="RB",
            salary=9200,
            projection=22.1,
            team="SF",
            opponent="ARI",
            mean_projection=22.1,
            std_deviation=6.2,
            ceiling_95th=32.3,
            floor_5th=12.0
        )
        
        # Test inherited properties
        assert player_proj.value > 0  # Inherited value calculation
        assert "Christian McCaffrey" in str(player_proj)
    
    def test_player_projection_without_correlation_group(self):
        """Test PlayerProjection with optional correlation_group as None."""
        player_proj = PlayerProjection(
            name="Travis Kelce",
            position="TE",
            salary=7500,
            projection=15.4,
            team="KC",
            opponent="LV",
            mean_projection=15.4,
            std_deviation=4.2,
            ceiling_95th=22.8,
            floor_5th=8.0,
            correlation_group=None
        )
        
        assert player_proj.correlation_group is None


class TestPlayerProjectionValidation:
    """Test PlayerProjection validation logic."""
    
    def test_negative_std_deviation_invalid(self):
        """Test negative standard deviation raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            PlayerProjection(
                name="Player 1",
                position="QB",
                salary=8500,
                projection=20.0,
                team="TEAM",
                opponent="OPP",
                mean_projection=20.0,
                std_deviation=-2.0,  # Invalid
                ceiling_95th=28.0,
                floor_5th=12.0
            )
        
        assert "std_deviation" in str(excinfo.value).lower()
    
    def test_zero_std_deviation_valid(self):
        """Test zero standard deviation is valid (no variance)."""
        player_proj = PlayerProjection(
            name="Consistent Player",
            position="QB",
            salary=8500,
            projection=20.0,
            team="TEAM",
            opponent="OPP",
            mean_projection=20.0,
            std_deviation=0.0,  # Valid - perfectly consistent
            ceiling_95th=20.0,
            floor_5th=20.0
        )
        
        assert player_proj.std_deviation == 0.0
    
    def test_ceiling_below_floor_invalid(self):
        """Test ceiling below floor raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            PlayerProjection(
                name="Player 1",
                position="QB",
                salary=8500,
                projection=20.0,
                team="TEAM",
                opponent="OPP",
                mean_projection=20.0,
                std_deviation=5.0,
                ceiling_95th=15.0,  # Below floor
                floor_5th=18.0
            )
        
        assert "ceiling" in str(excinfo.value).lower() or "floor" in str(excinfo.value).lower()
    
    def test_mean_outside_ceiling_floor_range_invalid(self):
        """Test mean projection outside ceiling/floor range raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            PlayerProjection(
                name="Player 1",
                position="QB",
                salary=8500,
                projection=20.0,
                team="TEAM",
                opponent="OPP",
                mean_projection=30.0,  # Outside ceiling/floor range
                std_deviation=5.0,
                ceiling_95th=25.0,
                floor_5th=10.0
            )
        
        assert "mean" in str(excinfo.value).lower()


class TestPlayerProjectionProperties:
    """Test PlayerProjection computed properties."""
    
    def test_variance_property(self):
        """Test variance property calculates correctly from std_deviation."""
        player_proj = PlayerProjection(
            name="Player 1",
            position="QB",
            salary=8500,
            projection=24.2,
            team="KC",
            opponent="LV",
            mean_projection=24.2,
            std_deviation=5.0,
            ceiling_95th=32.5,
            floor_5th=15.9
        )
        
        expected_variance = 5.0 ** 2
        assert abs(player_proj.variance - expected_variance) < 0.01
        assert abs(player_proj.variance - 25.0) < 0.01
    
    def test_range_property(self):
        """Test range property calculates ceiling minus floor."""
        player_proj = PlayerProjection(
            name="Player 1",
            position="QB",
            salary=8500,
            projection=24.2,
            team="KC",
            opponent="LV",
            mean_projection=24.2,
            std_deviation=5.8,
            ceiling_95th=35.0,
            floor_5th=15.0
        )
        
        expected_range = 35.0 - 15.0
        assert abs(player_proj.range - expected_range) < 0.01
        assert abs(player_proj.range - 20.0) < 0.01


class TestGameScenarioCreation:
    """Test GameScenario model creation."""
    
    def test_create_valid_game_scenario(self):
        """Test creating a valid GameScenario with all fields."""
        adjustments = {
            "QB_KC": 1.15,
            "RB_KC": 0.90,
            "WR_LV": 1.10,
            "TE_KC": 1.05
        }
        
        scenario = GameScenario(
            scenario_id="blowout_kc_lv_001",
            scenario_type=ScenarioType.BLOWOUT,
            adjustments=adjustments,
            confidence=0.75,
            description="KC expected to blow out LV, increased passing early"
        )
        
        assert scenario.scenario_id == "blowout_kc_lv_001"
        assert scenario.scenario_type == ScenarioType.BLOWOUT
        assert scenario.adjustments["QB_KC"] == 1.15
        assert scenario.confidence == 0.75
        assert "blow out" in scenario.description.lower()
    
    def test_create_scenario_without_description(self):
        """Test creating scenario with optional description as None."""
        scenario = GameScenario(
            scenario_id="shootout_001",
            scenario_type=ScenarioType.SHOOTOUT,
            adjustments={"QB_KC": 1.20, "QB_LV": 1.18},
            confidence=0.80,
            description=None
        )
        
        assert scenario.description is None
    
    def test_all_scenario_types_valid(self):
        """Test all ScenarioType enum values are valid."""
        scenario_types = [
            ScenarioType.BLOWOUT,
            ScenarioType.SHOOTOUT,
            ScenarioType.WEATHER,
            ScenarioType.PACE,
            ScenarioType.REVENGE,
            ScenarioType.PRIMETIME,
            ScenarioType.DIVISIONAL,
            ScenarioType.CUSTOM
        ]
        
        for st in scenario_types:
            scenario = GameScenario(
                scenario_id=f"test_{st.value}",
                scenario_type=st,
                adjustments={},
                confidence=0.5
            )
            assert scenario.scenario_type == st


class TestGameScenarioValidation:
    """Test GameScenario validation logic."""
    
    def test_invalid_confidence_below_zero(self):
        """Test confidence below 0 raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            GameScenario(
                scenario_id="test_001",
                scenario_type=ScenarioType.BLOWOUT,
                adjustments={},
                confidence=-0.1  # Invalid
            )
        
        assert "confidence" in str(excinfo.value).lower()
    
    def test_invalid_confidence_above_one(self):
        """Test confidence above 1.0 raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            GameScenario(
                scenario_id="test_001",
                scenario_type=ScenarioType.BLOWOUT,
                adjustments={},
                confidence=1.5  # Invalid
            )
        
        assert "confidence" in str(excinfo.value).lower()
    
    def test_confidence_at_boundaries(self):
        """Test confidence at 0.0 and 1.0 is valid."""
        scenario_zero = GameScenario(
            scenario_id="test_zero",
            scenario_type=ScenarioType.BLOWOUT,
            adjustments={},
            confidence=0.0
        )
        
        scenario_one = GameScenario(
            scenario_id="test_one",
            scenario_type=ScenarioType.BLOWOUT,
            adjustments={},
            confidence=1.0
        )
        
        assert scenario_zero.confidence == 0.0
        assert scenario_one.confidence == 1.0
    
    def test_empty_adjustments_valid(self):
        """Test empty adjustments dictionary is valid."""
        scenario = GameScenario(
            scenario_id="test_empty",
            scenario_type=ScenarioType.CUSTOM,
            adjustments={},
            confidence=0.5
        )
        
        assert len(scenario.adjustments) == 0


class TestGameScenarioMethods:
    """Test GameScenario methods."""
    
    def test_apply_adjustment_to_player(self):
        """Test applying scenario adjustments to a player's projection."""
        adjustments = {
            "QB_KC": 1.15,
            "RB_SF": 0.90
        }
        
        scenario = GameScenario(
            scenario_id="test_001",
            scenario_type=ScenarioType.BLOWOUT,
            adjustments=adjustments,
            confidence=0.75
        )
        
        player = Player(
            name="Patrick Mahomes",
            position="QB",
            salary=8500,
            projection=24.0,
            team="KC",
            opponent="LV"
        )
        
        adjusted_proj = scenario.apply_to_player(player)
        expected_proj = 24.0 * 1.15
        assert abs(adjusted_proj - expected_proj) < 0.01
        assert abs(adjusted_proj - 27.6) < 0.01
    
    def test_apply_adjustment_no_match(self):
        """Test applying scenario when no matching adjustment exists."""
        adjustments = {
            "QB_KC": 1.15
        }
        
        scenario = GameScenario(
            scenario_id="test_001",
            scenario_type=ScenarioType.BLOWOUT,
            adjustments=adjustments,
            confidence=0.75
        )
        
        player = Player(
            name="Player",
            position="RB",
            salary=6000,
            projection=18.0,
            team="SF",
            opponent="ARI"
        )
        
        # No adjustment for RB_SF, should return original
        adjusted_proj = scenario.apply_to_player(player)
        assert abs(adjusted_proj - 18.0) < 0.01


class TestLineupPortfolioCreation:
    """Test LineupPortfolio model creation."""
    
    def setup_method(self):
        """Create sample lineups for portfolio testing."""
        self.lineup1 = self._create_sample_lineup(1, "Mahomes", "CMC")
        self.lineup2 = self._create_sample_lineup(2, "Allen", "Barkley")
        self.lineup3 = self._create_sample_lineup(3, "Hurts", "Henry")
    
    def _create_sample_lineup(self, lineup_id: int, qb_name: str, rb_name: str) -> Lineup:
        """Helper to create a sample lineup."""
        return Lineup(
            lineup_id=lineup_id,
            qb=Player(qb_name, "QB", 8000, 24.0, "T1", "T2"),
            rb1=Player(rb_name, "RB", 8500, 22.0, "T1", "T2"),
            rb2=Player("RB2", "RB", 6000, 16.0, "T1", "T2"),
            wr1=Player("WR1", "WR", 7000, 18.0, "T1", "T2"),
            wr2=Player("WR2", "WR", 6500, 16.0, "T1", "T2"),
            wr3=Player("WR3", "WR", 6000, 14.0, "T1", "T2"),
            te=Player("TE1", "TE", 5500, 13.0, "T1", "T2"),
            flex=Player("FLEX", "WR", 5000, 12.0, "T1", "T2"),
            dst=Player("DST", "DST", 3000, 10.0, "T1", "T2")
        )
    
    def test_create_valid_portfolio(self):
        """Test creating a valid LineupPortfolio."""
        lineups = [self.lineup1, self.lineup2, self.lineup3]
        
        portfolio = LineupPortfolio(
            portfolio_id="portfolio_001",
            lineups=lineups
        )
        
        assert portfolio.portfolio_id == "portfolio_001"
        assert len(portfolio.lineups) == 3
        assert portfolio.lineups[0] == self.lineup1
    
    def test_create_portfolio_single_lineup(self):
        """Test creating portfolio with single lineup."""
        portfolio = LineupPortfolio(
            portfolio_id="single_001",
            lineups=[self.lineup1]
        )
        
        assert len(portfolio.lineups) == 1
    
    def test_create_portfolio_empty_fails(self):
        """Test creating portfolio with empty lineups list raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            LineupPortfolio(
                portfolio_id="empty_001",
                lineups=[]  # Invalid
            )
        
        assert "lineup" in str(excinfo.value).lower()


class TestLineupPortfolioProperties:
    """Test LineupPortfolio computed properties."""
    
    def setup_method(self):
        """Create sample portfolio for testing."""
        # Create lineups with known player overlaps
        self.lineup1 = Lineup(
            lineup_id=1,
            qb=Player("Mahomes", "QB", 8000, 24.0, "KC", "LV"),
            rb1=Player("CMC", "RB", 9000, 22.0, "SF", "ARI"),  # In 2/3 lineups
            rb2=Player("Barkley", "RB", 7000, 18.0, "NYG", "DAL"),
            wr1=Player("Jefferson", "WR", 8000, 19.0, "MIN", "GB"),
            wr2=Player("Hill", "WR", 7500, 17.0, "MIA", "BUF"),
            wr3=Player("Adams", "WR", 7000, 16.0, "LV", "KC"),
            te=Player("Kelce", "TE", 7000, 15.0, "KC", "LV"),  # In 3/3 lineups
            flex=Player("AJ Brown", "WR", 6500, 14.0, "PHI", "WAS"),
            dst=Player("49ers", "DST", 3000, 10.0, "SF", "ARI")
        )
        
        self.lineup2 = Lineup(
            lineup_id=2,
            qb=Player("Allen", "QB", 8500, 25.0, "BUF", "MIA"),
            rb1=Player("CMC", "RB", 9000, 22.0, "SF", "ARI"),  # In 2/3 lineups
            rb2=Player("Henry", "RB", 7500, 19.0, "TEN", "JAX"),
            wr1=Player("Chase", "WR", 8000, 18.0, "CIN", "BAL"),
            wr2=Player("Diggs", "WR", 7500, 17.0, "BUF", "MIA"),
            wr3=Player("Waddle", "WR", 6500, 15.0, "MIA", "BUF"),
            te=Player("Kelce", "TE", 7000, 15.0, "KC", "LV"),  # In 3/3 lineups
            flex=Player("Godwin", "WR", 6000, 13.0, "TB", "ATL"),
            dst=Player("Bills", "DST", 3500, 11.0, "BUF", "MIA")
        )
        
        self.lineup3 = Lineup(
            lineup_id=3,
            qb=Player("Hurts", "QB", 8200, 26.0, "PHI", "WAS"),
            rb1=Player("Taylor", "RB", 8000, 20.0, "IND", "HOU"),
            rb2=Player("Jacobs", "RB", 7000, 17.0, "LV", "KC"),
            wr1=Player("Lamb", "WR", 8500, 20.0, "DAL", "NYG"),
            wr2=Player("Smith", "WR", 7000, 16.0, "PHI", "WAS"),
            wr3=Player("Olave", "WR", 6500, 15.0, "NO", "CAR"),
            te=Player("Kelce", "TE", 7000, 15.0, "KC", "LV"),  # In 3/3 lineups
            flex=Player("Pittman", "WR", 6000, 13.0, "IND", "HOU"),
            dst=Player("Eagles", "DST", 3000, 10.0, "PHI", "WAS")
        )
        
        self.portfolio = LineupPortfolio(
            portfolio_id="test_portfolio",
            lineups=[self.lineup1, self.lineup2, self.lineup3]
        )
    
    def test_total_exposure_calculation(self):
        """Test total_exposure property calculates player exposure correctly."""
        exposure = self.portfolio.total_exposure
        
        # Kelce in all 3 lineups = 100% exposure
        assert abs(exposure["Kelce"] - 100.0) < 0.01
        
        # CMC in 2 of 3 lineups = 66.67% exposure
        assert abs(exposure["CMC"] - 66.67) < 0.1
        
        # Mahomes in 1 of 3 lineups = 33.33% exposure
        assert abs(exposure["Mahomes"] - 33.33) < 0.1
    
    def test_portfolio_variance_calculation(self):
        """Test portfolio_variance property calculates correctly."""
        variance = self.portfolio.portfolio_variance
        
        # Variance should be non-negative
        assert variance >= 0
    
    def test_lineup_count_property(self):
        """Test lineup_count property."""
        assert self.portfolio.lineup_count == 3
    
    def test_average_projection_property(self):
        """Test average_projection across all lineups."""
        avg_proj = self.portfolio.average_projection
        
        # Calculate expected average
        total_proj = sum(lineup.total_projection for lineup in self.portfolio.lineups)
        expected_avg = total_proj / 3
        
        assert abs(avg_proj - expected_avg) < 0.01


class TestLineupPortfolioMethods:
    """Test LineupPortfolio methods."""
    
    def test_get_correlation_matrix(self):
        """Test get_correlation_matrix returns valid numpy array."""
        lineup1 = self._create_sample_lineup(1)
        lineup2 = self._create_sample_lineup(2)
        
        portfolio = LineupPortfolio(
            portfolio_id="test",
            lineups=[lineup1, lineup2]
        )
        
        corr_matrix = portfolio.get_correlation_matrix()
        
        # Check it's a numpy array
        assert isinstance(corr_matrix, np.ndarray)
        
        # Check dimensions (2 lineups = 2x2 matrix)
        assert corr_matrix.shape == (2, 2)
        
        # Diagonal should be 1.0 (lineup correlated with itself)
        assert abs(corr_matrix[0, 0] - 1.0) < 0.01
        assert abs(corr_matrix[1, 1] - 1.0) < 0.01
    
    def test_get_core_players(self):
        """Test identifying core players with exposure threshold."""
        lineup1 = Lineup(
            lineup_id=1,
            qb=Player("Mahomes", "QB", 8000, 24.0, "KC", "LV"),
            rb1=Player("CMC", "RB", 9000, 22.0, "SF", "ARI"),
            rb2=Player("Player2", "RB", 7000, 18.0, "T", "O"),
            wr1=Player("Player3", "WR", 8000, 19.0, "T", "O"),
            wr2=Player("Player4", "WR", 7500, 17.0, "T", "O"),
            wr3=Player("Player5", "WR", 7000, 16.0, "T", "O"),
            te=Player("Kelce", "TE", 7000, 15.0, "KC", "LV"),
            flex=Player("Player6", "WR", 6500, 14.0, "T", "O"),
            dst=Player("DST1", "DST", 3000, 10.0, "T", "O")
        )
        
        lineup2 = Lineup(
            lineup_id=2,
            qb=Player("Allen", "QB", 8500, 25.0, "BUF", "MIA"),
            rb1=Player("CMC", "RB", 9000, 22.0, "SF", "ARI"),  # Core
            rb2=Player("Different", "RB", 7500, 19.0, "T", "O"),
            wr1=Player("Other1", "WR", 8000, 18.0, "T", "O"),
            wr2=Player("Other2", "WR", 7500, 17.0, "T", "O"),
            wr3=Player("Other3", "WR", 6500, 15.0, "T", "O"),
            te=Player("Kelce", "TE", 7000, 15.0, "KC", "LV"),  # Core
            flex=Player("Other4", "WR", 6000, 13.0, "T", "O"),
            dst=Player("DST2", "DST", 3500, 11.0, "T", "O")
        )
        
        portfolio = LineupPortfolio(
            portfolio_id="test",
            lineups=[lineup1, lineup2]
        )
        
        # 75% threshold means player must be in both lineups
        core_players = portfolio.get_core_players(min_exposure=75.0)
        
        assert "CMC" in core_players
        assert "Kelce" in core_players
        assert "Mahomes" not in core_players  # Only in 1 lineup
    
    def _create_sample_lineup(self, lineup_id: int) -> Lineup:
        """Helper to create a sample lineup."""
        return Lineup(
            lineup_id=lineup_id,
            qb=Player(f"QB{lineup_id}", "QB", 8000, 24.0, "T1", "T2"),
            rb1=Player(f"RB1_{lineup_id}", "RB", 8500, 22.0, "T1", "T2"),
            rb2=Player(f"RB2_{lineup_id}", "RB", 6000, 16.0, "T1", "T2"),
            wr1=Player(f"WR1_{lineup_id}", "WR", 7000, 18.0, "T1", "T2"),
            wr2=Player(f"WR2_{lineup_id}", "WR", 6500, 16.0, "T1", "T2"),
            wr3=Player(f"WR3_{lineup_id}", "WR", 6000, 14.0, "T1", "T2"),
            te=Player(f"TE{lineup_id}", "TE", 5500, 13.0, "T1", "T2"),
            flex=Player(f"FLEX{lineup_id}", "WR", 5000, 12.0, "T1", "T2"),
            dst=Player(f"DST{lineup_id}", "DST", 3000, 10.0, "T1", "T2")
        )


class TestCorrelationMatrixCalculation:
    """Test correlation matrix calculations for portfolios."""
    
    def test_perfectly_correlated_lineups(self):
        """Test correlation matrix for identical lineups."""
        lineup = self._create_sample_lineup(1)
        
        portfolio = LineupPortfolio(
            portfolio_id="identical",
            lineups=[lineup, lineup]  # Same lineup twice
        )
        
        corr_matrix = portfolio.get_correlation_matrix()
        
        # All elements should be 1.0 (perfect correlation)
        assert np.allclose(corr_matrix, 1.0)
    
    def test_uncorrelated_lineups(self):
        """Test correlation matrix for completely different lineups."""
        lineup1 = Lineup(
            lineup_id=1,
            qb=Player("QB1", "QB", 8000, 24.0, "T1", "O1"),
            rb1=Player("RB1", "RB", 8500, 22.0, "T1", "O1"),
            rb2=Player("RB2", "RB", 6000, 16.0, "T1", "O1"),
            wr1=Player("WR1", "WR", 7000, 18.0, "T1", "O1"),
            wr2=Player("WR2", "WR", 6500, 16.0, "T1", "O1"),
            wr3=Player("WR3", "WR", 6000, 14.0, "T1", "O1"),
            te=Player("TE1", "TE", 5500, 13.0, "T1", "O1"),
            flex=Player("FLEX1", "WR", 5000, 12.0, "T1", "O1"),
            dst=Player("DST1", "DST", 3000, 10.0, "T1", "O1")
        )
        
        lineup2 = Lineup(
            lineup_id=2,
            qb=Player("QB2", "QB", 8000, 24.0, "T2", "O2"),
            rb1=Player("RB3", "RB", 8500, 22.0, "T2", "O2"),
            rb2=Player("RB4", "RB", 6000, 16.0, "T2", "O2"),
            wr1=Player("WR4", "WR", 7000, 18.0, "T2", "O2"),
            wr2=Player("WR5", "WR", 6500, 16.0, "T2", "O2"),
            wr3=Player("WR6", "WR", 6000, 14.0, "T2", "O2"),
            te=Player("TE2", "TE", 5500, 13.0, "T2", "O2"),
            flex=Player("FLEX2", "WR", 5000, 12.0, "T2", "O2"),
            dst=Player("DST2", "DST", 3000, 10.0, "T2", "O2")
        )
        
        portfolio = LineupPortfolio(
            portfolio_id="uncorrelated",
            lineups=[lineup1, lineup2]
        )
        
        corr_matrix = portfolio.get_correlation_matrix()
        
        # Diagonal should be 1.0
        assert abs(corr_matrix[0, 0] - 1.0) < 0.01
        assert abs(corr_matrix[1, 1] - 1.0) < 0.01
        
        # Off-diagonal should be 0.0 (no shared players)
        assert abs(corr_matrix[0, 1]) < 0.01
        assert abs(corr_matrix[1, 0]) < 0.01
    
    def _create_sample_lineup(self, lineup_id: int) -> Lineup:
        """Helper to create a sample lineup."""
        return Lineup(
            lineup_id=lineup_id,
            qb=Player("Mahomes", "QB", 8000, 24.0, "KC", "LV"),
            rb1=Player("CMC", "RB", 8500, 22.0, "SF", "ARI"),
            rb2=Player("Barkley", "RB", 6000, 16.0, "NYG", "DAL"),
            wr1=Player("Jefferson", "WR", 7000, 18.0, "MIN", "GB"),
            wr2=Player("Hill", "WR", 6500, 16.0, "MIA", "BUF"),
            wr3=Player("Adams", "WR", 6000, 14.0, "LV", "KC"),
            te=Player("Kelce", "TE", 5500, 13.0, "KC", "LV"),
            flex=Player("Brown", "WR", 5000, 12.0, "PHI", "WAS"),
            dst=Player("49ers", "DST", 3000, 10.0, "SF", "ARI")
        )

