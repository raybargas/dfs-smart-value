"""
Unit Tests for Models Module

Tests Player data class and validation logic.
"""

import pytest
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from models import Player, Lineup, PlayerSelection


class TestPlayerCreation:
    """Test Player object creation."""
    
    def test_create_valid_player(self):
        """Test creating a valid player object."""
        player = Player(
            name="Patrick Mahomes",
            position="QB",
            salary=8500,
            projection=24.2,
            team="KC",
            opponent="LV"
        )
        
        assert player.name == "Patrick Mahomes"
        assert player.position == "QB"
        assert player.salary == 8500
        assert player.projection == 24.2
        assert player.team == "KC"
        assert player.opponent == "LV"
        assert player.ownership is None
        assert player.player_id is None
    
    def test_create_player_with_optional_fields(self):
        """Test creating player with optional fields."""
        player = Player(
            name="Christian McCaffrey",
            position="RB",
            salary=9200,
            projection=22.1,
            team="SF",
            opponent="@ARI",
            ownership=32.0,
            player_id="14876890"
        )
        
        assert player.ownership == 32.0
        assert player.player_id == "14876890"


class TestPlayerValidation:
    """Test Player validation logic."""
    
    def test_invalid_position(self):
        """Test invalid position raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            Player(
                name="Player 1",
                position="WR1",  # Invalid
                salary=8500,
                projection=20.0,
                team="TEAM",
                opponent="OPP"
            )
        
        assert "position" in str(excinfo.value).lower()
        assert "WR1" in str(excinfo.value)
    
    def test_valid_position_variations(self):
        """Test D/ST and DEF are valid positions."""
        player1 = Player(
            name="49ers",
            position="DST",
            salary=3500,
            projection=12.0,
            team="SF",
            opponent="ARI"
        )
        
        player2 = Player(
            name="Bills",
            position="D/ST",
            salary=3500,
            projection=12.0,
            team="BUF",
            opponent="MIA"
        )
        
        assert player1.position == "DST"
        assert player2.position == "D/ST"
    
    def test_salary_too_low(self):
        """Test salary below minimum raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            Player(
                name="Player 1",
                position="QB",
                salary=2000,  # Too low
                projection=20.0,
                team="TEAM",
                opponent="OPP"
            )
        
        assert "salary" in str(excinfo.value).lower()
        assert "2000" in str(excinfo.value)
    
    def test_salary_too_high(self):
        """Test salary above maximum raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            Player(
                name="Player 1",
                position="QB",
                salary=15000,  # Too high
                projection=20.0,
                team="TEAM",
                opponent="OPP"
            )
        
        assert "salary" in str(excinfo.value).lower()
    
    def test_salary_at_boundaries(self):
        """Test salary at min and max boundaries is valid."""
        player_min = Player(
            name="Player Min",
            position="QB",
            salary=3000,
            projection=10.0,
            team="TEAM",
            opponent="OPP"
        )
        
        player_max = Player(
            name="Player Max",
            position="QB",
            salary=10000,
            projection=30.0,
            team="TEAM",
            opponent="OPP"
        )
        
        assert player_min.salary == 3000
        assert player_max.salary == 10000
    
    def test_negative_projection(self):
        """Test negative projection raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            Player(
                name="Player 1",
                position="QB",
                salary=8500,
                projection=-5.0,  # Invalid
                team="TEAM",
                opponent="OPP"
            )
        
        assert "projection" in str(excinfo.value).lower()
    
    def test_zero_projection(self):
        """Test zero projection raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            Player(
                name="Player 1",
                position="QB",
                salary=8500,
                projection=0.0,  # Invalid
                team="TEAM",
                opponent="OPP"
            )
        
        assert "projection" in str(excinfo.value).lower()
    
    def test_ownership_below_zero(self):
        """Test ownership below 0% raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            Player(
                name="Player 1",
                position="QB",
                salary=8500,
                projection=20.0,
                team="TEAM",
                opponent="OPP",
                ownership=-10.0  # Invalid
            )
        
        assert "ownership" in str(excinfo.value).lower()
    
    def test_ownership_above_hundred(self):
        """Test ownership above 100% raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            Player(
                name="Player 1",
                position="QB",
                salary=8500,
                projection=20.0,
                team="TEAM",
                opponent="OPP",
                ownership=150.0  # Invalid
            )
        
        assert "ownership" in str(excinfo.value).lower()
    
    def test_ownership_at_boundaries(self):
        """Test ownership at 0% and 100% is valid."""
        player_zero = Player(
            name="Player Zero",
            position="QB",
            salary=8500,
            projection=20.0,
            team="TEAM",
            opponent="OPP",
            ownership=0.0
        )
        
        player_hundred = Player(
            name="Player Hundred",
            position="QB",
            salary=8500,
            projection=20.0,
            team="TEAM",
            opponent="OPP",
            ownership=100.0
        )
        
        assert player_zero.ownership == 0.0
        assert player_hundred.ownership == 100.0


class TestPlayerProperties:
    """Test Player computed properties."""
    
    def test_value_calculation(self):
        """Test value property calculates correctly."""
        player = Player(
            name="Patrick Mahomes",
            position="QB",
            salary=8500,
            projection=24.2,
            team="KC",
            opponent="LV"
        )
        
        expected_value = (24.2 / 8500) * 1000
        assert abs(player.value - expected_value) < 0.01
    
    def test_value_comparison(self):
        """Test comparing player values."""
        player1 = Player(
            name="Player 1",
            position="QB",
            salary=8500,
            projection=24.0,
            team="TEAM1",
            opponent="OPP1"
        )
        
        player2 = Player(
            name="Player 2",
            position="QB",
            salary=7500,
            projection=24.0,
            team="TEAM2",
            opponent="OPP2"
        )
        
        # Same projection, lower salary = better value
        assert player2.value > player1.value


class TestPlayerStringMethods:
    """Test Player string representations."""
    
    def test_str_method(self):
        """Test __str__ returns readable representation."""
        player = Player(
            name="Patrick Mahomes",
            position="QB",
            salary=8500,
            projection=24.2,
            team="KC",
            opponent="LV"
        )
        
        str_repr = str(player)
        assert "Patrick Mahomes" in str_repr
        assert "QB" in str_repr
        assert "8,500" in str_repr or "8500" in str_repr
        assert "24.2" in str_repr
        assert "KC" in str_repr
        assert "LV" in str_repr
    
    def test_repr_method(self):
        """Test __repr__ returns developer-friendly representation."""
        player = Player(
            name="Patrick Mahomes",
            position="QB",
            salary=8500,
            projection=24.2,
            team="KC",
            opponent="LV"
        )
        
        repr_str = repr(player)
        assert "Player(" in repr_str
        assert "Patrick Mahomes" in repr_str
        assert "QB" in repr_str
        assert "8500" in repr_str
        assert "24.2" in repr_str


class TestLineupCreation:
    """Test Lineup object creation."""
    
    def setup_method(self):
        """Create sample players for lineup testing."""
        self.qb = Player("Mahomes", "QB", 8500, 24.2, "KC", "LV")
        self.rb1 = Player("CMC", "RB", 9200, 22.1, "SF", "ARI")
        self.rb2 = Player("Barkley", "RB", 8000, 18.5, "NYG", "DAL")
        self.wr1 = Player("Jefferson", "WR", 8500, 19.3, "MIN", "GB")
        self.wr2 = Player("Hill", "WR", 8200, 17.8, "MIA", "BUF")
        self.wr3 = Player("Adams", "WR", 7800, 16.5, "LV", "KC")
        self.te = Player("Kelce", "TE", 7500, 15.4, "KC", "LV")
        self.flex = Player("Brown", "WR", 7000, 14.2, "PHI", "WAS")
        self.dst = Player("49ers", "DST", 3500, 12.0, "SF", "ARI")
    
    def test_create_valid_lineup(self):
        """Test creating a valid lineup object."""
        lineup = Lineup(
            lineup_id=1,
            qb=self.qb,
            rb1=self.rb1,
            rb2=self.rb2,
            wr1=self.wr1,
            wr2=self.wr2,
            wr3=self.wr3,
            te=self.te,
            flex=self.flex,
            dst=self.dst
        )
        
        assert lineup.lineup_id == 1
        assert lineup.qb == self.qb
        assert lineup.rb1 == self.rb1
        assert lineup.flex == self.flex


class TestLineupProperties:
    """Test Lineup computed properties."""
    
    def setup_method(self):
        """Create sample lineup for testing."""
        self.qb = Player("Mahomes", "QB", 8500, 24.2, "KC", "LV")
        self.rb1 = Player("CMC", "RB", 9200, 22.1, "SF", "ARI")
        self.rb2 = Player("Barkley", "RB", 8000, 18.5, "NYG", "DAL")
        self.wr1 = Player("Jefferson", "WR", 8500, 19.3, "MIN", "GB")
        self.wr2 = Player("Hill", "WR", 8200, 17.8, "MIA", "BUF")
        self.wr3 = Player("Adams", "WR", 7800, 16.5, "LV", "KC")
        self.te = Player("Kelce", "TE", 7500, 15.4, "KC", "LV")
        self.flex = Player("Brown", "WR", 7000, 14.2, "PHI", "WAS")
        self.dst = Player("49ers", "DST", 3500, 12.0, "SF", "ARI")
        
        self.lineup = Lineup(
            lineup_id=1,
            qb=self.qb,
            rb1=self.rb1,
            rb2=self.rb2,
            wr1=self.wr1,
            wr2=self.wr2,
            wr3=self.wr3,
            te=self.te,
            flex=self.flex,
            dst=self.dst
        )
    
    def test_players_property(self):
        """Test players property returns all 9 players."""
        players = self.lineup.players
        assert len(players) == 9
        assert self.qb in players
        assert self.rb1 in players
        assert self.rb2 in players
        assert self.wr1 in players
        assert self.wr2 in players
        assert self.wr3 in players
        assert self.te in players
        assert self.flex in players
        assert self.dst in players
    
    def test_total_salary_calculation(self):
        """Test total_salary property calculates correctly."""
        expected_salary = 8500 + 9200 + 8000 + 8500 + 8200 + 7800 + 7500 + 7000 + 3500
        assert self.lineup.total_salary == expected_salary
        assert self.lineup.total_salary == 68200
    
    def test_total_projection_calculation(self):
        """Test total_projection property calculates correctly."""
        expected_projection = 24.2 + 22.1 + 18.5 + 19.3 + 17.8 + 16.5 + 15.4 + 14.2 + 12.0
        assert abs(self.lineup.total_projection - expected_projection) < 0.01
        assert abs(self.lineup.total_projection - 160.0) < 0.01
    
    def test_salary_remaining_calculation(self):
        """Test salary_remaining property calculates correctly."""
        expected_remaining = 50000 - 68200
        assert self.lineup.salary_remaining == expected_remaining
        assert self.lineup.salary_remaining == -18200  # Over cap
    
    def test_salary_remaining_under_cap(self):
        """Test salary_remaining with lineup under cap."""
        # Create cheaper lineup
        lineup = Lineup(
            lineup_id=1,
            qb=Player("QB1", "QB", 6000, 18.0, "T1", "T2"),
            rb1=Player("RB1", "RB", 5500, 15.0, "T1", "T2"),
            rb2=Player("RB2", "RB", 5000, 14.0, "T1", "T2"),
            wr1=Player("WR1", "WR", 5500, 14.0, "T1", "T2"),
            wr2=Player("WR2", "WR", 5000, 13.0, "T1", "T2"),
            wr3=Player("WR3", "WR", 4500, 12.0, "T1", "T2"),
            te=Player("TE1", "TE", 4500, 11.0, "T1", "T2"),
            flex=Player("FLEX1", "RB", 4000, 10.0, "T1", "T2"),
            dst=Player("DST1", "DST", 3000, 8.0, "T1", "T2")
        )
        
        assert lineup.total_salary == 43000
        assert lineup.salary_remaining == 7000


class TestLineupValidation:
    """Test Lineup is_valid property validation logic."""
    
    def setup_method(self):
        """Create sample valid lineup for testing."""
        self.qb = Player("Mahomes", "QB", 6000, 20.0, "KC", "LV")
        self.rb1 = Player("CMC", "RB", 6000, 18.0, "SF", "ARI")
        self.rb2 = Player("Barkley", "RB", 5500, 16.0, "NYG", "DAL")
        self.wr1 = Player("Jefferson", "WR", 6000, 17.0, "MIN", "GB")
        self.wr2 = Player("Hill", "WR", 5500, 15.0, "MIA", "BUF")
        self.wr3 = Player("Adams", "WR", 5000, 14.0, "LV", "KC")
        self.te = Player("Kelce", "TE", 5000, 13.0, "KC", "LV")
        self.flex = Player("Brown", "WR", 4500, 12.0, "PHI", "WAS")
        self.dst = Player("49ers", "DST", 3000, 10.0, "SF", "ARI")
    
    def test_valid_lineup(self):
        """Test that a valid lineup passes validation."""
        lineup = Lineup(
            lineup_id=1,
            qb=self.qb,
            rb1=self.rb1,
            rb2=self.rb2,
            wr1=self.wr1,
            wr2=self.wr2,
            wr3=self.wr3,
            te=self.te,
            flex=self.flex,
            dst=self.dst
        )
        
        assert lineup.is_valid is True
        assert lineup.total_salary == 46500
        assert lineup.total_salary <= 50000
    
    def test_invalid_salary_over_cap(self):
        """Test lineup over salary cap is invalid."""
        lineup = Lineup(
            lineup_id=1,
            qb=Player("QB", "QB", 9000, 25.0, "T", "O"),
            rb1=Player("RB1", "RB", 9000, 22.0, "T", "O"),
            rb2=Player("RB2", "RB", 8000, 20.0, "T", "O"),
            wr1=Player("WR1", "WR", 8500, 19.0, "T", "O"),
            wr2=Player("WR2", "WR", 8000, 18.0, "T", "O"),
            wr3=Player("WR3", "WR", 7500, 17.0, "T", "O"),
            te=Player("TE", "TE", 7000, 16.0, "T", "O"),
            flex=Player("FLEX", "RB", 6500, 15.0, "T", "O"),
            dst=Player("DST", "DST", 3000, 10.0, "T", "O")
        )
        
        assert lineup.total_salary > 50000
        assert lineup.is_valid is False
    
    def test_invalid_duplicate_players(self):
        """Test lineup with duplicate players is invalid."""
        same_player = Player("Mahomes", "QB", 6000, 20.0, "KC", "LV")
        
        lineup = Lineup(
            lineup_id=1,
            qb=same_player,
            rb1=Player("RB1", "RB", 6000, 18.0, "T", "O"),
            rb2=Player("RB2", "RB", 5500, 16.0, "T", "O"),
            wr1=Player("WR1", "WR", 6000, 17.0, "T", "O"),
            wr2=Player("WR2", "WR", 5500, 15.0, "T", "O"),
            wr3=Player("WR3", "WR", 5000, 14.0, "T", "O"),
            te=same_player,  # Duplicate!
            flex=Player("FLEX", "WR", 4500, 12.0, "T", "O"),
            dst=Player("DST", "DST", 3000, 10.0, "T", "O")
        )
        
        assert lineup.is_valid is False
    
    def test_invalid_missing_qb(self):
        """Test lineup without QB is invalid."""
        lineup = Lineup(
            lineup_id=1,
            qb=Player("NotQB", "RB", 6000, 20.0, "T", "O"),  # Wrong position
            rb1=self.rb1,
            rb2=self.rb2,
            wr1=self.wr1,
            wr2=self.wr2,
            wr3=self.wr3,
            te=self.te,
            flex=self.flex,
            dst=self.dst
        )
        
        assert lineup.is_valid is False
    
    def test_invalid_missing_dst(self):
        """Test lineup without DST is invalid."""
        lineup = Lineup(
            lineup_id=1,
            qb=self.qb,
            rb1=self.rb1,
            rb2=self.rb2,
            wr1=self.wr1,
            wr2=self.wr2,
            wr3=self.wr3,
            te=self.te,
            flex=self.flex,
            dst=Player("NotDST", "QB", 3000, 10.0, "T", "O")  # Wrong position
        )
        
        assert lineup.is_valid is False
    
    def test_invalid_insufficient_rbs(self):
        """Test lineup with less than 2 RBs is invalid."""
        lineup = Lineup(
            lineup_id=1,
            qb=self.qb,
            rb1=self.rb1,
            rb2=Player("NotRB", "WR", 5500, 16.0, "T", "O"),  # Should be RB
            wr1=self.wr1,
            wr2=self.wr2,
            wr3=self.wr3,
            te=self.te,
            flex=Player("FLEX", "WR", 4500, 12.0, "T", "O"),  # FLEX is WR
            dst=self.dst
        )
        
        # Only 1 RB total (rb1), need at least 2
        assert lineup.is_valid is False
    
    def test_invalid_insufficient_wrs(self):
        """Test lineup with less than 3 WRs is invalid."""
        lineup = Lineup(
            lineup_id=1,
            qb=self.qb,
            rb1=self.rb1,
            rb2=self.rb2,
            wr1=self.wr1,
            wr2=self.wr2,
            wr3=Player("NotWR", "RB", 5000, 14.0, "T", "O"),  # Should be WR
            te=self.te,
            flex=Player("FLEX", "RB", 4500, 12.0, "T", "O"),  # FLEX is RB
            dst=self.dst
        )
        
        # Only 2 WRs total, need at least 3
        assert lineup.is_valid is False
    
    def test_invalid_insufficient_tes(self):
        """Test lineup with no TEs is invalid."""
        lineup = Lineup(
            lineup_id=1,
            qb=self.qb,
            rb1=self.rb1,
            rb2=self.rb2,
            wr1=self.wr1,
            wr2=self.wr2,
            wr3=self.wr3,
            te=Player("NotTE", "WR", 5000, 13.0, "T", "O"),  # Should be TE
            flex=Player("FLEX", "WR", 4500, 12.0, "T", "O"),  # FLEX is WR
            dst=self.dst
        )
        
        # No TEs, need at least 1
        assert lineup.is_valid is False
    
    def test_invalid_flex_position(self):
        """Test FLEX must be RB, WR, or TE."""
        lineup = Lineup(
            lineup_id=1,
            qb=self.qb,
            rb1=self.rb1,
            rb2=self.rb2,
            wr1=self.wr1,
            wr2=self.wr2,
            wr3=self.wr3,
            te=self.te,
            flex=Player("FLEX", "QB", 4500, 12.0, "T", "O"),  # Invalid FLEX position
            dst=self.dst
        )
        
        assert lineup.is_valid is False
    
    def test_valid_flex_positions(self):
        """Test that FLEX can be RB, WR, or TE."""
        # FLEX as RB
        lineup_rb = Lineup(
            lineup_id=1,
            qb=self.qb,
            rb1=self.rb1,
            rb2=self.rb2,
            wr1=self.wr1,
            wr2=self.wr2,
            wr3=self.wr3,
            te=self.te,
            flex=Player("FLEX_RB", "RB", 4500, 12.0, "T", "O"),
            dst=self.dst
        )
        assert lineup_rb.is_valid is True
        
        # FLEX as WR
        lineup_wr = Lineup(
            lineup_id=2,
            qb=self.qb,
            rb1=self.rb1,
            rb2=self.rb2,
            wr1=self.wr1,
            wr2=self.wr2,
            wr3=self.wr3,
            te=self.te,
            flex=Player("FLEX_WR", "WR", 4500, 12.0, "T", "O"),
            dst=self.dst
        )
        assert lineup_wr.is_valid is True
        
        # FLEX as TE
        lineup_te = Lineup(
            lineup_id=3,
            qb=self.qb,
            rb1=self.rb1,
            rb2=self.rb2,
            wr1=self.wr1,
            wr2=self.wr2,
            wr3=self.wr3,
            te=self.te,
            flex=Player("FLEX_TE", "TE", 4500, 12.0, "T", "O"),
            dst=self.dst
        )
        assert lineup_te.is_valid is True
    
    def test_position_requirements_with_flex(self):
        """Test that position requirements count FLEX appropriately."""
        # 2 RBs + 1 RB at FLEX = 3 total RBs (valid)
        lineup = Lineup(
            lineup_id=1,
            qb=self.qb,
            rb1=self.rb1,
            rb2=self.rb2,
            wr1=self.wr1,
            wr2=self.wr2,
            wr3=self.wr3,
            te=self.te,
            flex=Player("FLEX_RB", "RB", 4500, 12.0, "T", "O"),
            dst=self.dst
        )
        
        assert lineup.is_valid is True
        rb_count = sum(1 for p in lineup.players if p.position == "RB")
        assert rb_count == 3


class TestLineupStringMethods:
    """Test Lineup string representations."""
    
    def test_str_method(self):
        """Test __str__ returns readable representation."""
        lineup = Lineup(
            lineup_id=1,
            qb=Player("Mahomes", "QB", 6000, 20.0, "KC", "LV"),
            rb1=Player("CMC", "RB", 6000, 18.0, "SF", "ARI"),
            rb2=Player("Barkley", "RB", 5500, 16.0, "NYG", "DAL"),
            wr1=Player("Jefferson", "WR", 6000, 17.0, "MIN", "GB"),
            wr2=Player("Hill", "WR", 5500, 15.0, "MIA", "BUF"),
            wr3=Player("Adams", "WR", 5000, 14.0, "LV", "KC"),
            te=Player("Kelce", "TE", 5000, 13.0, "KC", "LV"),
            flex=Player("Brown", "WR", 4500, 12.0, "PHI", "WAS"),
            dst=Player("49ers", "DST", 3000, 10.0, "SF", "ARI")
        )
        
        str_repr = str(lineup)
        assert "Lineup #1" in str_repr
        assert "Mahomes" in str_repr
        assert "QB:" in str_repr
        assert "RB:" in str_repr
        assert "WR:" in str_repr
        assert "TE:" in str_repr
        assert "FLEX:" in str_repr
        assert "DST:" in str_repr
        assert "46,500" in str_repr or "46500" in str_repr
        assert "135.0" in str_repr  # Total projection

