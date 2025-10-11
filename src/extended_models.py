"""
Extended Data Models Module (Phase 2)

This module defines extended data structures for Monte Carlo simulation,
game scenarios, and portfolio optimization.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from enum import Enum
import numpy as np

from models import Player, Lineup


class ScenarioType(Enum):
    """Enum for game scenario types."""
    BLOWOUT = "blowout"
    SHOOTOUT = "shootout"
    WEATHER = "weather"
    PACE = "pace"
    REVENGE = "revenge"
    PRIMETIME = "primetime"
    DIVISIONAL = "divisional"
    CUSTOM = "custom"


@dataclass
class PlayerProjection(Player):
    """
    Extended Player model with projection distribution fields for Monte Carlo simulation.
    
    Extends the base Player class with statistical fields for variance analysis:
    - mean_projection: Expected mean fantasy points
    - std_deviation: Standard deviation for distribution
    - ceiling_95th: 95th percentile outcome
    - floor_5th: 5th percentile outcome
    - correlation_group: Optional grouping for stacking correlations
    
    Attributes:
        mean_projection: Expected value of projection distribution
        std_deviation: Standard deviation (must be >= 0)
        ceiling_95th: 95th percentile projection
        floor_5th: 5th percentile projection
        correlation_group: Optional identifier for correlation groups (e.g., "KC_PASS", "SF_RUN")
    """
    mean_projection: float = field(default=0.0)
    std_deviation: float = field(default=0.0)
    ceiling_95th: float = field(default=0.0)
    floor_5th: float = field(default=0.0)
    correlation_group: Optional[str] = field(default=None)
    
    def __post_init__(self):
        """Validate player projection attributes after initialization."""
        # Call parent validation first
        super().__post_init__()
        
        # Validate std_deviation is non-negative
        if self.std_deviation < 0:
            raise ValueError(
                f"Invalid std_deviation: {self.std_deviation}. "
                f"Must be non-negative (>= 0)"
            )
        
        # Validate ceiling >= floor
        if self.ceiling_95th < self.floor_5th:
            raise ValueError(
                f"Invalid ceiling/floor: ceiling ({self.ceiling_95th}) "
                f"must be >= floor ({self.floor_5th})"
            )
        
        # Validate mean is within reasonable range of ceiling/floor
        # Allow some tolerance for edge cases
        if self.ceiling_95th > 0 and self.floor_5th >= 0:
            if self.mean_projection > self.ceiling_95th or self.mean_projection < self.floor_5th:
                raise ValueError(
                    f"Invalid mean_projection: {self.mean_projection}. "
                    f"Must be between floor ({self.floor_5th}) and ceiling ({self.ceiling_95th})"
                )
    
    @property
    def variance(self) -> float:
        """
        Calculate variance from standard deviation.
        
        Returns:
            float: Variance (std_deviation squared)
        """
        return self.std_deviation ** 2
    
    @property
    def range(self) -> float:
        """
        Calculate projection range (ceiling minus floor).
        
        Returns:
            float: Difference between ceiling and floor
        """
        return self.ceiling_95th - self.floor_5th
    
    def __str__(self) -> str:
        """String representation with projection distribution."""
        base_str = super().__str__()
        dist_str = f" | σ={self.std_deviation:.1f} | Range: {self.floor_5th:.1f}-{self.ceiling_95th:.1f}"
        return base_str + dist_str


@dataclass
class GameScenario:
    """
    Represents a game scenario with adjustments to player projections.
    
    Game scenarios capture different narrative situations (blowouts, shootouts,
    weather impacts, etc.) and their impact on player usage and production.
    
    Attributes:
        scenario_id: Unique identifier for this scenario
        scenario_type: Type of scenario from ScenarioType enum
        adjustments: Dictionary mapping player keys to adjustment factors
                    Keys format: "{POSITION}_{TEAM}" (e.g., "QB_KC", "RB_SF")
                    Values: Multiplicative factors (e.g., 1.15 = +15%, 0.90 = -10%)
        confidence: Confidence level in this scenario (0.0 to 1.0)
        description: Optional human-readable description of the scenario
    """
    scenario_id: str
    scenario_type: ScenarioType
    adjustments: Dict[str, float]
    confidence: float
    description: Optional[str] = None
    
    def __post_init__(self):
        """Validate scenario attributes after initialization."""
        # Validate confidence is between 0 and 1
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Invalid confidence: {self.confidence}. "
                f"Must be between 0.0 and 1.0"
            )
    
    def apply_to_player(self, player: Player) -> float:
        """
        Apply scenario adjustments to a player's projection.
        
        Args:
            player: Player to apply adjustments to
            
        Returns:
            float: Adjusted projection value
        """
        # Build adjustment key: "{POSITION}_{TEAM}"
        adjustment_key = f"{player.position}_{player.team}"
        
        # Get adjustment factor (default to 1.0 if not found)
        adjustment_factor = self.adjustments.get(adjustment_key, 1.0)
        
        # Return adjusted projection
        return player.projection * adjustment_factor
    
    def get_team_adjustments(self, team: str) -> Dict[str, float]:
        """
        Get all adjustments for a specific team.
        
        Args:
            team: Team abbreviation
            
        Returns:
            Dict[str, float]: Dictionary of position -> adjustment factor for the team
        """
        team_adjustments = {}
        for key, value in self.adjustments.items():
            if key.endswith(f"_{team}"):
                position = key.split("_")[0]
                team_adjustments[position] = value
        return team_adjustments
    
    def __str__(self) -> str:
        """String representation of scenario."""
        desc = f" - {self.description}" if self.description else ""
        return (
            f"Scenario {self.scenario_id} ({self.scenario_type.value}): "
            f"{len(self.adjustments)} adjustments, "
            f"confidence={self.confidence:.0%}{desc}"
        )


@dataclass
class LineupPortfolio:
    """
    Represents a portfolio of multiple lineups for multi-entry optimization.
    
    A portfolio groups multiple lineups together for analysis of exposure,
    correlation, and overall variance. Enables intelligent hedging strategies
    and portfolio-level optimization.
    
    Attributes:
        portfolio_id: Unique identifier for this portfolio
        lineups: List of Lineup objects in the portfolio
    """
    portfolio_id: str
    lineups: List[Lineup]
    
    def __post_init__(self):
        """Validate portfolio attributes after initialization."""
        # Validate at least one lineup
        if not self.lineups or len(self.lineups) == 0:
            raise ValueError(
                "Invalid portfolio: must contain at least one lineup"
            )
    
    @property
    def lineup_count(self) -> int:
        """
        Get number of lineups in portfolio.
        
        Returns:
            int: Count of lineups
        """
        return len(self.lineups)
    
    @property
    def total_exposure(self) -> Dict[str, float]:
        """
        Calculate player exposure across all lineups in portfolio.
        
        Exposure is the percentage of lineups containing each player.
        
        Returns:
            Dict[str, float]: Player name -> exposure percentage (0-100)
        """
        player_counts: Dict[str, int] = {}
        
        # Count appearances of each player
        for lineup in self.lineups:
            for player in lineup.players:
                player_counts[player.name] = player_counts.get(player.name, 0) + 1
        
        # Calculate exposure percentages
        total_lineups = len(self.lineups)
        exposure = {
            player_name: (count / total_lineups) * 100
            for player_name, count in player_counts.items()
        }
        
        return exposure
    
    @property
    def average_projection(self) -> float:
        """
        Calculate average projected points across all lineups.
        
        Returns:
            float: Mean of all lineup projections
        """
        if not self.lineups:
            return 0.0
        
        total_proj = sum(lineup.total_projection for lineup in self.lineups)
        return total_proj / len(self.lineups)
    
    @property
    def portfolio_variance(self) -> float:
        """
        Calculate variance of projections across lineups.
        
        Returns:
            float: Variance of lineup projections
        """
        if len(self.lineups) < 2:
            return 0.0
        
        projections = [lineup.total_projection for lineup in self.lineups]
        return float(np.var(projections))
    
    def get_correlation_matrix(self) -> np.ndarray:
        """
        Calculate correlation matrix for all lineups in portfolio.
        
        Correlation is based on shared players between lineups.
        Two lineups with many shared players have high correlation.
        
        Returns:
            np.ndarray: NxN correlation matrix where N = number of lineups
                       Values range from 0 (no shared players) to 1 (identical)
        """
        n_lineups = len(self.lineups)
        corr_matrix = np.zeros((n_lineups, n_lineups))
        
        for i in range(n_lineups):
            for j in range(n_lineups):
                if i == j:
                    # Lineup perfectly correlated with itself
                    corr_matrix[i, j] = 1.0
                else:
                    # Calculate correlation based on shared players
                    lineup_i_players = set(p.name for p in self.lineups[i].players)
                    lineup_j_players = set(p.name for p in self.lineups[j].players)
                    
                    shared_players = len(lineup_i_players & lineup_j_players)
                    total_players = 9  # DFS lineup has 9 players
                    
                    # Correlation = fraction of shared players
                    corr_matrix[i, j] = shared_players / total_players
        
        return corr_matrix
    
    def get_core_players(self, min_exposure: float = 75.0) -> List[str]:
        """
        Identify core players who appear in most lineups.
        
        Args:
            min_exposure: Minimum exposure percentage to be considered core (default: 75%)
            
        Returns:
            List[str]: List of player names with exposure >= min_exposure
        """
        exposure = self.total_exposure
        core_players = [
            player_name
            for player_name, exp_pct in exposure.items()
            if exp_pct >= min_exposure
        ]
        return sorted(core_players)
    
    def get_differentiation_players(self, max_exposure: float = 25.0) -> List[str]:
        """
        Identify differentiation players who appear in few lineups.
        
        Args:
            max_exposure: Maximum exposure percentage for differentiation (default: 25%)
            
        Returns:
            List[str]: List of player names with exposure <= max_exposure
        """
        exposure = self.total_exposure
        diff_players = [
            player_name
            for player_name, exp_pct in exposure.items()
            if exp_pct <= max_exposure
        ]
        return sorted(diff_players)
    
    def __str__(self) -> str:
        """String representation of portfolio."""
        return (
            f"Portfolio {self.portfolio_id}: "
            f"{len(self.lineups)} lineups, "
            f"Avg Projection: {self.average_projection:.1f}, "
            f"Variance: {self.portfolio_variance:.2f}"
        )

