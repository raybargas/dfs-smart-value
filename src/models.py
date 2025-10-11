"""
Data Models Module

This module defines data structures used throughout the DFS Lineup Optimizer.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

class PlayerSelection(Enum):
    """Enum for player selection states in the optimizer."""
    NORMAL = "normal"
    LOCKED = "locked"
    EXCLUDED = "excluded"

@dataclass
class Player:
    """
    Represents a DFS player with all relevant attributes.
    
    Attributes:
        name: Player's full name
        position: Position abbreviation (QB, RB, WR, TE, DST)
        salary: DraftKings salary (2000-10000)
        projection: Projected fantasy points
        team: Team abbreviation (e.g., 'KC', 'SF')
        opponent: Opponent team abbreviation
        ownership: Projected ownership percentage (0-100), optional
        player_id: Unique player identifier, optional
        selection: Player selection state for optimization (default: NORMAL)
        smart_value: Multi-factor value score (optional, for advanced optimization)
    """
    name: str
    position: str
    salary: int
    projection: float
    team: str
    opponent: str
    ownership: Optional[float] = None
    player_id: Optional[str] = None
    selection: PlayerSelection = field(default=PlayerSelection.NORMAL)
    smart_value: Optional[float] = None
    
    def __post_init__(self):
        """Validate player attributes after initialization."""
        # Validate position
        valid_positions = ['QB', 'RB', 'WR', 'TE', 'DST', 'D/ST', 'DEF']
        if self.position not in valid_positions:
            raise ValueError(
                f"Invalid position: {self.position}. "
                f"Must be one of: {', '.join(valid_positions)}"
            )
        
        # Validate salary range (DraftKings typically allows $2,000-$10,000)
        if not (2000 <= self.salary <= 10000):
            raise ValueError(
                f"Invalid salary: ${self.salary}. "
                f"Must be between $2,000 and $10,000"
            )
        
        # Validate projection is positive
        if self.projection <= 0:
            raise ValueError(
                f"Invalid projection: {self.projection}. "
                f"Must be positive"
            )
        
        # Validate ownership if provided
        if self.ownership is not None:
            if not (0 <= self.ownership <= 100):
                raise ValueError(
                    f"Invalid ownership: {self.ownership}%. "
                    f"Must be between 0-100"
                )
    
    @property
    def value(self) -> float:
        """
        Calculate points per dollar (value metric).
        
        Returns:
            float: Projection divided by salary (multiplied by 1000 for readability)
        """
        return (self.projection / self.salary) * 1000
    
    def get_selection_display(self) -> str:
        """Get display string for the player's selection state."""
        return self.selection.value.upper()
    
    def __str__(self) -> str:
        """String representation of player."""
        selection_str = f" [{self.get_selection_display()}]" if self.selection != PlayerSelection.NORMAL else ""
        return (
            f"{self.name} ({self.position}){selection_str} - "
            f"${self.salary:,} | {self.projection:.1f} pts | "
            f"{self.team} vs {self.opponent}"
        )
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"Player(name='{self.name}', position='{self.position}', "
            f"salary={self.salary}, projection={self.projection}, "
            f"selection={self.selection})"
        )


@dataclass
class Lineup:
    """
    Represents a generated DFS lineup with 9 players.
    
    A DraftKings-valid lineup consists of:
    - 1 QB (Quarterback)
    - 2 RB (Running Backs)
    - 3 WR (Wide Receivers)
    - 1 TE (Tight End)
    - 1 FLEX (can be RB, WR, or TE)
    - 1 DST (Defense/Special Teams)
    
    Attributes:
        lineup_id: Unique identifier for this lineup
        qb: Quarterback player
        rb1: First running back
        rb2: Second running back
        wr1: First wide receiver
        wr2: Second wide receiver
        wr3: Third wide receiver
        te: Tight end player
        flex: FLEX player (must be RB, WR, or TE)
        dst: Defense/Special Teams
    """
    lineup_id: int
    qb: Player
    rb1: Player
    rb2: Player
    wr1: Player
    wr2: Player
    wr3: Player
    te: Player
    flex: Player  # Can be RB, WR, or TE
    dst: Player
    
    @property
    def players(self) -> List[Player]:
        """
        Return all 9 players as a list.
        
        Returns:
            List[Player]: All players in the lineup
        """
        return [
            self.qb, self.rb1, self.rb2, 
            self.wr1, self.wr2, self.wr3, 
            self.te, self.flex, self.dst
        ]
    
    @property
    def total_salary(self) -> int:
        """
        Calculate total salary used by all players.
        
        Returns:
            int: Sum of all player salaries
        """
        return sum(p.salary for p in self.players)
    
    @property
    def total_projection(self) -> float:
        """
        Calculate total projected points for the lineup.
        
        Returns:
            float: Sum of all player projections
        """
        return sum(p.projection for p in self.players)
    
    @property
    def salary_remaining(self) -> int:
        """
        Calculate salary remaining under the $50,000 cap.
        
        Returns:
            int: Salary remaining (negative if over cap)
        """
        return 50000 - self.total_salary
    
    @property
    def is_valid(self) -> bool:
        """
        Validate lineup meets all DraftKings requirements.
        
        Checks:
        - Salary cap: Total salary <= $50,000
        - No duplicate players
        - Exactly 9 players
        - Position requirements:
          - Exactly 1 QB
          - At least 2 RB (including FLEX)
          - At least 3 WR (including FLEX)
          - At least 1 TE (including FLEX)
          - Exactly 1 DST
          - FLEX must be RB, WR, or TE
        
        Returns:
            bool: True if lineup is valid, False otherwise
        """
        # Check salary cap
        if self.total_salary > 50000:
            return False
        
        # Check no duplicate players (compare by name)
        player_names = [p.name for p in self.players]
        if len(player_names) != len(set(player_names)):
            return False
        
        # Check exactly 9 players
        if len(self.players) != 9:
            return False
        
        # Count positions
        positions = [p.position for p in self.players]
        
        # Check exactly 1 QB
        if positions.count('QB') != 1:
            return False
        
        # Check exactly 1 DST (can be DST, D/ST, or DEF)
        dst_count = sum(1 for pos in positions if pos in ['DST', 'D/ST', 'DEF'])
        if dst_count != 1:
            return False
        
        # Check RB count (at least 2 from RB1, RB2, FLEX)
        rb_count = sum(1 for p in [self.rb1, self.rb2, self.flex] if p.position == 'RB')
        if rb_count < 2:
            return False
        
        # Check WR count (at least 3 from WR1, WR2, WR3, FLEX)
        wr_count = sum(1 for p in [self.wr1, self.wr2, self.wr3, self.flex] if p.position == 'WR')
        if wr_count < 3:
            return False
        
        # Check TE count (at least 1 from TE, FLEX)
        te_count = sum(1 for p in [self.te, self.flex] if p.position == 'TE')
        if te_count < 1:
            return False
        
        # Check FLEX must be RB, WR, or TE
        if self.flex.position not in ['RB', 'WR', 'TE']:
            return False
        
        return True
    
    def __str__(self) -> str:
        """
        String representation of lineup with all players and totals.
        
        Returns:
            str: Formatted lineup display
        """
        return (
            f"Lineup #{self.lineup_id}: "
            f"${self.total_salary:,} | {self.total_projection:.1f} pts\n"
            f"  QB:   {self.qb.name} (${self.qb.salary:,})\n"
            f"  RB:   {self.rb1.name} (${self.rb1.salary:,})\n"
            f"  RB:   {self.rb2.name} (${self.rb2.salary:,})\n"
            f"  WR:   {self.wr1.name} (${self.wr1.salary:,})\n"
            f"  WR:   {self.wr2.name} (${self.wr2.salary:,})\n"
            f"  WR:   {self.wr3.name} (${self.wr3.salary:,})\n"
            f"  TE:   {self.te.name} (${self.te.salary:,})\n"
            f"  FLEX: {self.flex.name} ({self.flex.position}, ${self.flex.salary:,})\n"
            f"  DST:  {self.dst.name} (${self.dst.salary:,})"
        )

