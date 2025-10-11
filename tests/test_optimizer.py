"""
Unit Tests for Optimizer Module

Tests lineup generation using PuLP linear programming.
"""

import pytest
import sys
import pandas as pd
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from models import Player, Lineup
from optimizer import (
    generate_lineups,
    _generate_single_lineup,
    _dataframe_to_players,
    _build_lineup_from_players,
    _interpret_infeasibility
)
import pulp


class TestDataframeToPlayers:
    """Test DataFrame to Player object conversion."""
    
    def test_basic_conversion(self):
        """Test converting DataFrame with required fields to Player objects."""
        df = pd.DataFrame({
            'name': ['Mahomes', 'CMC'],
            'position': ['QB', 'RB'],
            'salary': [8500, 9200],
            'projection': [24.2, 22.1],
            'team': ['KC', 'SF'],
            'opponent': ['LV', 'ARI'],
            'player_id': ['123', '456']
        })
        
        players = _dataframe_to_players(df)
        
        assert len(players) == 2
        assert isinstance(players[0], Player)
        assert players[0].name == 'Mahomes'
        assert players[0].position == 'QB'
        assert players[0].salary == 8500
        assert players[0].projection == 24.2
    
    def test_conversion_with_ownership(self):
        """Test conversion includes ownership when present."""
        df = pd.DataFrame({
            'name': ['Player1'],
            'position': ['QB'],
            'salary': [8500],
            'projection': [24.2],
            'team': ['TEAM'],
            'opponent': ['OPP'],
            'player_id': ['123'],
            'ownership': [35.5]
        })
        
        players = _dataframe_to_players(df)
        assert players[0].ownership == 35.5
    
    def test_conversion_without_ownership(self):
        """Test conversion handles missing ownership field."""
        df = pd.DataFrame({
            'name': ['Player1'],
            'position': ['QB'],
            'salary': [8500],
            'projection': [24.2],
            'team': ['TEAM'],
            'opponent': ['OPP'],
            'player_id': ['123']
        })
        
        players = _dataframe_to_players(df)
        assert players[0].ownership is None


class TestBuildLineupFromPlayers:
    """Test building Lineup object from 9 selected players."""
    
    def setup_method(self):
        """Create sample players for lineup building."""
        self.qb = Player("Mahomes", "QB", 6000, 20.0, "KC", "LV")
        self.rb1 = Player("CMC", "RB", 6000, 18.0, "SF", "ARI")
        self.rb2 = Player("Barkley", "RB", 5500, 16.0, "NYG", "DAL")
        self.rb3 = Player("Walker", "RB", 5000, 14.0, "SEA", "LAR")
        self.wr1 = Player("Jefferson", "WR", 6000, 17.0, "MIN", "GB")
        self.wr2 = Player("Hill", "WR", 5500, 15.0, "MIA", "BUF")
        self.wr3 = Player("Adams", "WR", 5000, 14.0, "LV", "KC")
        self.te = Player("Kelce", "TE", 5000, 13.0, "KC", "LV")
        self.dst = Player("49ers", "DST", 3000, 10.0, "SF", "ARI")
    
    def test_build_lineup_with_wr_flex(self):
        """Test building lineup when FLEX should be WR."""
        wr_flex = Player("Brown", "WR", 4500, 12.0, "PHI", "WAS")
        
        players = [
            self.qb, self.rb1, self.rb2, 
            self.wr1, self.wr2, self.wr3, wr_flex,
            self.te, self.dst
        ]
        
        lineup = _build_lineup_from_players(players, lineup_number=1)
        
        assert lineup.lineup_id == 1
        assert lineup.qb == self.qb
        assert lineup.rb1 == self.rb1
        assert lineup.rb2 == self.rb2
        assert lineup.wr1 == self.wr1
        assert lineup.wr2 == self.wr2
        assert lineup.wr3 == self.wr3
        assert lineup.te == self.te
        assert lineup.flex == wr_flex
        assert lineup.flex.position == "WR"
        assert lineup.dst == self.dst
    
    def test_build_lineup_with_rb_flex(self):
        """Test building lineup when FLEX should be RB."""
        players = [
            self.qb, self.rb1, self.rb2, self.rb3,
            self.wr1, self.wr2, self.wr3,
            self.te, self.dst
        ]
        
        lineup = _build_lineup_from_players(players, lineup_number=2)
        
        assert lineup.flex.position == "RB"
        assert lineup.flex == self.rb3
    
    def test_build_lineup_with_te_flex(self):
        """Test building lineup when FLEX should be TE."""
        te_flex = Player("Andrews", "TE", 4500, 11.0, "BAL", "CIN")
        
        players = [
            self.qb, self.rb1, self.rb2,
            self.wr1, self.wr2, self.wr3,
            self.te, te_flex, self.dst
        ]
        
        lineup = _build_lineup_from_players(players, lineup_number=3)
        
        assert lineup.flex.position == "TE"
        assert lineup.flex == te_flex
    
    def test_flex_chooses_highest_projection(self):
        """Test that FLEX slot gets the highest projection among remaining eligible players."""
        # Create 9 players: After assigning QB, 2 RB, 3 WR, TE, DST,
        # the FLEX should be the 3rd RB (highest among remaining)
        qb = Player("QB", "QB", 6000, 20.0, "T1", "O1")
        rb1 = Player("RB1", "RB", 6000, 18.0, "T2", "O2")
        rb2 = Player("RB2", "RB", 5500, 17.0, "T3", "O3")
        rb3 = Player("RB3", "RB", 5000, 15.5, "T4", "O4")  # Will be FLEX (highest remaining)
        wr1 = Player("WR1", "WR", 6000, 16.0, "T5", "O5")
        wr2 = Player("WR2", "WR", 5500, 15.0, "T6", "O6")
        wr3 = Player("WR3", "WR", 5000, 14.0, "T7", "O7")
        te = Player("TE1", "TE", 5000, 13.0, "T8", "O8")
        dst = Player("DST", "DST", 3000, 10.0, "T9", "O9")
        
        players = [qb, rb1, rb2, rb3, wr1, wr2, wr3, te, dst]
        
        lineup = _build_lineup_from_players(players, lineup_number=1)
        
        # After assigning top 2 RBs (RB1, RB2) and top 3 WRs (WR1, WR2, WR3) and TE,
        # FLEX should be RB3 with 15.5 projection (highest remaining)
        assert lineup.flex == rb3
        assert lineup.flex.projection == 15.5
        assert lineup.flex.position == "RB"


class TestInterpretInfeasibility:
    """Test LP status code interpretation."""
    
    def test_infeasible_status(self):
        """Test interpretation of infeasible status."""
        error_msg = _interpret_infeasibility(pulp.LpStatusInfeasible, 5)
        assert "No valid lineup exists" in error_msg
    
    def test_unbounded_status(self):
        """Test interpretation of unbounded status."""
        error_msg = _interpret_infeasibility(pulp.LpStatusUnbounded, 5)
        assert "unbounded" in error_msg.lower()
    
    def test_not_solved_status(self):
        """Test interpretation of not solved status."""
        error_msg = _interpret_infeasibility(pulp.LpStatusNotSolved, 5)
        assert "failed" in error_msg.lower()


class TestGenerateSingleLineup:
    """Test single lineup generation with LP solver."""
    
    def create_sample_pool(self, size=50):
        """Create a sample player pool for testing."""
        data = {
            'name': [],
            'position': [],
            'salary': [],
            'projection': [],
            'team': [],
            'opponent': [],
            'ownership': [],
            'player_id': []
        }
        
        # Add QBs
        for i in range(min(5, size // 9)):
            data['name'].append(f'QB{i+1}')
            data['position'].append('QB')
            data['salary'].append(7000 - i * 500)
            data['projection'].append(22.0 - i * 2)
            data['team'].append(f'T{i}')
            data['opponent'].append(f'O{i}')
            data['ownership'].append(20.0 + i * 5)
            data['player_id'].append(f'qb{i}')
        
        # Add RBs
        for i in range(min(10, size // 4)):
            data['name'].append(f'RB{i+1}')
            data['position'].append('RB')
            data['salary'].append(6500 - i * 300)
            data['projection'].append(18.0 - i * 1.5)
            data['team'].append(f'T{i}')
            data['opponent'].append(f'O{i}')
            data['ownership'].append(15.0 + i * 3)
            data['player_id'].append(f'rb{i}')
        
        # Add WRs
        for i in range(min(15, size // 3)):
            data['name'].append(f'WR{i+1}')
            data['position'].append('WR')
            data['salary'].append(6000 - i * 200)
            data['projection'].append(16.0 - i * 1)
            data['team'].append(f'T{i}')
            data['opponent'].append(f'O{i}')
            data['ownership'].append(18.0 + i * 2)
            data['player_id'].append(f'wr{i}')
        
        # Add TEs
        for i in range(min(5, size // 9)):
            data['name'].append(f'TE{i+1}')
            data['position'].append('TE')
            data['salary'].append(5000 - i * 400)
            data['projection'].append(14.0 - i * 2)
            data['team'].append(f'T{i}')
            data['opponent'].append(f'O{i}')
            data['ownership'].append(12.0 + i * 3)
            data['player_id'].append(f'te{i}')
        
        # Add DSTs
        for i in range(min(5, size // 9)):
            data['name'].append(f'DST{i+1}')
            data['position'].append('DST')
            data['salary'].append(3500 - i * 100)  # Keep >= 3000
            data['projection'].append(10.0 - i)
            data['team'].append(f'T{i}')
            data['opponent'].append(f'O{i}')
            data['ownership'].append(8.0 + i * 2)
            data['player_id'].append(f'dst{i}')
        
        return pd.DataFrame(data)
    
    def test_generate_single_lineup_success(self):
        """Test successful generation of a single lineup."""
        pool_df = self.create_sample_pool(size=50)
        
        lineup, error = _generate_single_lineup(
            player_pool_df=pool_df,
            previous_lineups=[],
            max_shared=4,
            max_ownership_enabled=False,
            max_ownership_pct=None,
            lineup_number=1
        )
        
        assert lineup is not None
        assert error is None
        assert isinstance(lineup, Lineup)
        assert lineup.lineup_id == 1
        assert lineup.is_valid is True
        assert lineup.total_salary <= 50000
    
    def test_generate_lineup_respects_salary_cap(self):
        """Test that generated lineup respects $50,000 salary cap."""
        pool_df = self.create_sample_pool(size=50)
        
        lineup, error = _generate_single_lineup(
            player_pool_df=pool_df,
            previous_lineups=[],
            max_shared=4,
            max_ownership_enabled=False,
            max_ownership_pct=None,
            lineup_number=1
        )
        
        assert lineup.total_salary <= 50000
    
    def test_generate_lineup_meets_position_requirements(self):
        """Test that generated lineup meets all position requirements."""
        pool_df = self.create_sample_pool(size=50)
        
        lineup, error = _generate_single_lineup(
            player_pool_df=pool_df,
            previous_lineups=[],
            max_shared=4,
            max_ownership_enabled=False,
            max_ownership_pct=None,
            lineup_number=1
        )
        
        positions = [p.position for p in lineup.players]
        
        assert positions.count('QB') == 1
        assert positions.count('DST') >= 1
        assert sum(1 for p in lineup.players if p.position == 'RB') >= 2
        assert sum(1 for p in lineup.players if p.position == 'WR') >= 3
        assert sum(1 for p in lineup.players if p.position == 'TE') >= 1
        assert lineup.flex.position in ['RB', 'WR', 'TE']


class TestGenerateLineups:
    """Test multi-lineup generation with uniqueness constraints."""
    
    def create_sample_pool(self, size=100):
        """Create a larger sample pool for multi-lineup testing."""
        data = {
            'name': [],
            'position': [],
            'salary': [],
            'projection': [],
            'team': [],
            'opponent': [],
            'ownership': [],
            'player_id': []
        }
        
        # Add more players for uniqueness testing
        for i in range(size // 5):
            data['name'].append(f'QB{i+1}')
            data['position'].append('QB')
            data['salary'].append(7000 - i * 100)
            data['projection'].append(22.0 - i * 0.5)
            data['team'].append(f'T{i % 10}')
            data['opponent'].append(f'O{i % 10}')
            data['ownership'].append(20.0 + i * 0.5)
            data['player_id'].append(f'qb{i}')
        
        for i in range(size // 4):
            data['name'].append(f'RB{i+1}')
            data['position'].append('RB')
            data['salary'].append(6500 - i * 80)
            data['projection'].append(18.0 - i * 0.4)
            data['team'].append(f'T{i % 10}')
            data['opponent'].append(f'O{i % 10}')
            data['ownership'].append(15.0 + i * 0.3)
            data['player_id'].append(f'rb{i}')
        
        for i in range(size // 3):
            data['name'].append(f'WR{i+1}')
            data['position'].append('WR')
            data['salary'].append(6000 - i * 60)
            data['projection'].append(16.0 - i * 0.3)
            data['team'].append(f'T{i % 10}')
            data['opponent'].append(f'O{i % 10}')
            data['ownership'].append(18.0 + i * 0.2)
            data['player_id'].append(f'wr{i}')
        
        for i in range(size // 5):
            data['name'].append(f'TE{i+1}')
            data['position'].append('TE')
            data['salary'].append(5000 - i * 100)
            data['projection'].append(14.0 - i * 0.5)
            data['team'].append(f'T{i % 10}')
            data['opponent'].append(f'O{i % 10}')
            data['ownership'].append(12.0 + i * 0.4)
            data['player_id'].append(f'te{i}')
        
        for i in range(size // 5):
            data['name'].append(f'DST{i+1}')
            data['position'].append('DST')
            data['salary'].append(max(3000, 3500 - i * 20))  # Keep >= 3000
            data['projection'].append(10.0 - i * 0.3)
            data['team'].append(f'T{i % 10}')
            data['opponent'].append(f'O{i % 10}')
            data['ownership'].append(8.0 + i * 0.2)
            data['player_id'].append(f'dst{i}')
        
        return pd.DataFrame(data)
    
    def test_generate_single_lineup(self):
        """Test generating exactly 1 lineup."""
        pool_df = self.create_sample_pool(size=100)
        
        lineups, error = generate_lineups(
            player_pool_df=pool_df,
            lineup_count=1,
            uniqueness_pct=0.55,
            max_ownership_enabled=False,
            max_ownership_pct=None
        )
        
        assert error is None
        assert len(lineups) == 1
        assert lineups[0].is_valid is True
    
    def test_generate_multiple_lineups(self):
        """Test generating 5 lineups with 55% uniqueness."""
        pool_df = self.create_sample_pool(size=100)
        
        lineups, error = generate_lineups(
            player_pool_df=pool_df,
            lineup_count=5,
            uniqueness_pct=0.55,
            max_ownership_enabled=False,
            max_ownership_pct=None
        )
        
        assert error is None
        assert len(lineups) == 5
        for lineup in lineups:
            assert lineup.is_valid is True
    
    def test_uniqueness_constraint_enforced(self):
        """Test that uniqueness constraint is enforced between lineups."""
        pool_df = self.create_sample_pool(size=100)
        uniqueness_pct = 0.55
        max_shared = int(9 * (1 - uniqueness_pct))  # 4 players
        
        lineups, error = generate_lineups(
            player_pool_df=pool_df,
            lineup_count=5,
            uniqueness_pct=uniqueness_pct,
            max_ownership_enabled=False,
            max_ownership_pct=None
        )
        
        assert error is None
        
        # Check all pairs of lineups
        for i in range(len(lineups)):
            for j in range(i + 1, len(lineups)):
                lineup1_names = set(p.name for p in lineups[i].players)
                lineup2_names = set(p.name for p in lineups[j].players)
                shared = len(lineup1_names & lineup2_names)
                assert shared <= max_shared, f"Lineups {i+1} and {j+1} share {shared} players, max allowed is {max_shared}"
    
    def test_generate_lineups_with_tight_uniqueness(self):
        """Test that tight uniqueness with small pool returns partial results."""
        # Very small pool makes tight uniqueness infeasible
        pool_df = self.create_sample_pool(size=20)
        
        lineups, error = generate_lineups(
            player_pool_df=pool_df,
            lineup_count=15,  # Request more than feasible
            uniqueness_pct=0.80,  # Extremely tight (max 1 shared player)
            max_ownership_enabled=False,
            max_ownership_pct=None
        )
        
        # Should get some lineups but not all 15
        assert len(lineups) < 15
        assert error is not None
        assert "Could not generate lineup" in error
        
        # All generated lineups should be valid
        for lineup in lineups:
            assert lineup.is_valid is True


class TestOwnershipConstraint:
    """Test ownership filtering in optimization."""
    
    def create_pool_with_ownership(self):
        """Create pool with specific ownership values."""
        data = {
            'name': ['QB_High', 'QB_Low', 'RB1', 'RB2', 'RB3', 'WR1', 'WR2', 'WR3', 'WR4', 'TE1', 'DST1'],
            'position': ['QB', 'QB', 'RB', 'RB', 'RB', 'WR', 'WR', 'WR', 'WR', 'TE', 'DST'],
            'salary': [8000, 6000, 6500, 6000, 5500, 6000, 5500, 5000, 4500, 5000, 3000],
            'projection': [24.0, 20.0, 18.0, 17.0, 16.0, 16.0, 15.0, 14.0, 13.0, 13.0, 10.0],
            'team': ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8', 'T9', 'T10', 'T11'],
            'opponent': ['O1', 'O2', 'O3', 'O4', 'O5', 'O6', 'O7', 'O8', 'O9', 'O10', 'O11'],
            'ownership': [45.0, 12.0, 35.0, 25.0, 15.0, 30.0, 20.0, 15.0, 10.0, 18.0, 8.0],
            'player_id': ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11']
        }
        return pd.DataFrame(data)
    
    def test_ownership_constraint_applied(self):
        """Test that ownership constraint filters high-ownership players."""
        pool_df = self.create_pool_with_ownership()
        
        lineups, error = generate_lineups(
            player_pool_df=pool_df,
            lineup_count=1,
            uniqueness_pct=0.55,
            max_ownership_enabled=True,
            max_ownership_pct=0.30  # 30% max
        )
        
        assert error is None
        assert len(lineups) == 1
        
        # Check no player exceeds 30% ownership
        for player in lineups[0].players:
            if player.ownership is not None:
                assert player.ownership <= 30.0, f"{player.name} has {player.ownership}% ownership, exceeds 30% limit"

