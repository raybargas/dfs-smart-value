"""
Monte Carlo Simulation Engine (Phase 2)

This module provides Monte Carlo simulation capabilities for DFS lineup analysis,
including distribution generation, correlation modeling, and result aggregation.
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import pickle

from models import Player, Lineup
from extended_models import PlayerProjection


class DistributionGenerator:
    """
    Generates probability distributions for player projections.
    
    Supports normal and lognormal distributions with player-specific variance.
    Uses vectorized NumPy operations for performance.
    """
    
    def __init__(self, distribution_type: str = 'normal', random_seed: Optional[int] = None):
        """
        Initialize distribution generator.
        
        Args:
            distribution_type: Type of distribution ('normal' or 'lognormal')
            random_seed: Optional seed for reproducibility
        """
        self.distribution_type = distribution_type
        if random_seed is not None:
            np.random.seed(random_seed)
    
    def generate(self, player: PlayerProjection, n_samples: int) -> np.ndarray:
        """
        Generate distribution samples for a single player.
        
        Args:
            player: PlayerProjection with mean and std_deviation
            n_samples: Number of samples to generate
            
        Returns:
            np.ndarray: Array of projection samples
        """
        if player.std_deviation == 0:
            # No variance - return constant array
            return np.full(n_samples, player.mean_projection)
        
        if self.distribution_type == 'normal':
            samples = np.random.normal(
                loc=player.mean_projection,
                scale=player.std_deviation,
                size=n_samples
            )
            # Ensure non-negative (fantasy points can't be negative)
            samples = np.maximum(samples, 0)
            
        elif self.distribution_type == 'lognormal':
            # For lognormal, convert mean/std to mu/sigma parameters
            mean = player.mean_projection
            std = player.std_deviation
            
            # Lognormal parameters
            mu = np.log(mean**2 / np.sqrt(mean**2 + std**2))
            sigma = np.sqrt(np.log(1 + (std**2 / mean**2)))
            
            samples = np.random.lognormal(
                mean=mu,
                sigma=sigma,
                size=n_samples
            )
        else:
            raise ValueError(f"Unknown distribution type: {self.distribution_type}")
        
        return samples
    
    def generate_batch(self, players: List[PlayerProjection], n_samples: int) -> np.ndarray:
        """
        Generate distributions for multiple players at once (vectorized).
        
        Args:
            players: List of PlayerProjection objects
            n_samples: Number of samples per player
            
        Returns:
            np.ndarray: Array of shape (n_samples, n_players)
        """
        n_players = len(players)
        samples = np.zeros((n_samples, n_players))
        
        for i, player in enumerate(players):
            samples[:, i] = self.generate(player, n_samples)
        
        return samples


class CorrelationMatrixBuilder:
    """
    Builds correlation matrices for player projections.
    
    Implements correlation rules:
    - QB-WR/TE stacking: Positive correlation for same team
    - RB-DEF: Negative correlation for opposing teams
    - Game environment: Correlations within same game
    """
    
    # Default correlation values
    DEFAULT_QB_RECEIVER_CORR = 0.60  # QB-WR/TE same team
    DEFAULT_RB_DEF_CORR = -0.35      # RB-opposing DEF
    DEFAULT_GAME_ENV_CORR = 0.20     # Players in same game
    
    def __init__(
        self,
        qb_receiver_corr: float = DEFAULT_QB_RECEIVER_CORR,
        rb_def_corr: float = DEFAULT_RB_DEF_CORR,
        game_env_corr: float = DEFAULT_GAME_ENV_CORR
    ):
        """
        Initialize correlation matrix builder.
        
        Args:
            qb_receiver_corr: Correlation for QB-WR/TE stacking
            rb_def_corr: Correlation for RB-opposing DEF
            game_env_corr: Correlation for same-game players
        """
        self.qb_receiver_corr = qb_receiver_corr
        self.rb_def_corr = rb_def_corr
        self.game_env_corr = game_env_corr
    
    def build(self, players: List[PlayerProjection]) -> np.ndarray:
        """
        Build correlation matrix for a list of players.
        
        Args:
            players: List of PlayerProjection objects
            
        Returns:
            np.ndarray: Correlation matrix of shape (n_players, n_players)
        """
        n = len(players)
        corr_matrix = np.eye(n)  # Start with identity (1.0 on diagonal)
        
        for i in range(n):
            for j in range(i + 1, n):
                # Calculate correlation between players i and j
                corr = self._calculate_correlation(players[i], players[j])
                corr_matrix[i, j] = corr
                corr_matrix[j, i] = corr  # Symmetric
        
        return corr_matrix
    
    def _calculate_correlation(self, player1: PlayerProjection, player2: PlayerProjection) -> float:
        """
        Calculate correlation between two players based on positions and teams.
        
        Args:
            player1: First player
            player2: Second player
            
        Returns:
            float: Correlation coefficient
        """
        # Check for correlation_group first (explicit stacking)
        if (player1.correlation_group and player2.correlation_group and
            player1.correlation_group == player2.correlation_group):
            return self.qb_receiver_corr
        
        # QB-Receiver stacking (same team)
        if self._is_qb_receiver_stack(player1, player2):
            return self.qb_receiver_corr
        
        # RB-DEF negative correlation (opposing teams)
        if self._is_rb_def_opposition(player1, player2):
            return self.rb_def_corr
        
        # Same game environment (weak positive correlation)
        if self._is_same_game(player1, player2):
            return self.game_env_corr
        
        # No correlation by default
        return 0.0
    
    def _is_qb_receiver_stack(self, p1: PlayerProjection, p2: PlayerProjection) -> bool:
        """Check if players form a QB-receiver stack."""
        positions = {p1.position, p2.position}
        
        # One must be QB, other must be WR or TE
        is_qb_receiver = ('QB' in positions and
                         ('WR' in positions or 'TE' in positions))
        
        # Must be on same team
        same_team = p1.team == p2.team
        
        return is_qb_receiver and same_team
    
    def _is_rb_def_opposition(self, p1: PlayerProjection, p2: PlayerProjection) -> bool:
        """Check if players are RB vs opposing DEF."""
        positions = {p1.position, p2.position}
        
        # One must be RB, other must be DST/DEF
        is_rb_def = ('RB' in positions and
                    ('DST' in positions or 'D/ST' in positions or 'DEF' in positions))
        
        if not is_rb_def:
            return False
        
        # RB's team must be DEF's opponent (or vice versa)
        rb = p1 if p1.position == 'RB' else p2
        dst = p1 if p1.position in ['DST', 'D/ST', 'DEF'] else p2
        
        return rb.opponent == dst.team or rb.team == dst.opponent
    
    def _is_same_game(self, p1: PlayerProjection, p2: PlayerProjection) -> bool:
        """Check if players are in the same game."""
        # Players are in same game if:
        # - Same team, OR
        # - One's team is the other's opponent
        return (p1.team == p2.team or
                p1.team == p2.opponent or
                p1.opponent == p2.team)


@dataclass
class SimulationResult:
    """
    Aggregates and analyzes simulation results.
    
    Provides statistics and probability calculations from simulation samples.
    """
    samples: np.ndarray  # Array of simulation outcomes
    
    def __post_init__(self):
        """Calculate cached statistics."""
        self._mean = float(np.mean(self.samples))
        self._std_deviation = float(np.std(self.samples))
        self._variance = float(np.var(self.samples))
        self._median = float(np.median(self.samples))
        self._floor_5th = float(np.percentile(self.samples, 5))
        self._ceiling_95th = float(np.percentile(self.samples, 95))
    
    @property
    def mean(self) -> float:
        """Mean of simulation samples."""
        return self._mean
    
    @property
    def std_deviation(self) -> float:
        """Standard deviation of simulation samples."""
        return self._std_deviation
    
    @property
    def variance(self) -> float:
        """Variance of simulation samples."""
        return self._variance
    
    @property
    def median(self) -> float:
        """Median of simulation samples."""
        return self._median
    
    @property
    def floor_5th(self) -> float:
        """5th percentile (floor) of simulation samples."""
        return self._floor_5th
    
    @property
    def ceiling_95th(self) -> float:
        """95th percentile (ceiling) of simulation samples."""
        return self._ceiling_95th
    
    def probability_above(self, threshold: float) -> float:
        """
        Calculate probability of exceeding a threshold.
        
        Args:
            threshold: Score threshold
            
        Returns:
            float: Probability (0.0 to 1.0)
        """
        return float(np.mean(self.samples > threshold))
    
    def probability_below(self, threshold: float) -> float:
        """
        Calculate probability of scoring below a threshold.
        
        Args:
            threshold: Score threshold
            
        Returns:
            float: Probability (0.0 to 1.0)
        """
        return float(np.mean(self.samples < threshold))
    
    def gpp_cash_probability(self, cash_line: float) -> float:
        """
        Calculate probability of cashing in a GPP.
        
        Args:
            cash_line: Minimum score needed to cash
            
        Returns:
            float: Probability of cashing (0.0 to 1.0)
        """
        return self.probability_above(cash_line)
    
    def percentile(self, p: float) -> float:
        """
        Get value at a specific percentile.
        
        Args:
            p: Percentile (0-100)
            
        Returns:
            float: Value at percentile p
        """
        return float(np.percentile(self.samples, p))
    
    def __str__(self) -> str:
        """String representation of results."""
        return (
            f"SimulationResult: "
            f"Mean={self.mean:.1f}, "
            f"Median={self.median:.1f}, "
            f"Floor={self.floor_5th:.1f}, "
            f"Ceiling={self.ceiling_95th:.1f}, "
            f"StdDev={self.std_deviation:.1f}"
        )


class SimulationCache:
    """
    LRU cache for simulation results.
    
    Caches results by lineup to avoid re-running identical simulations.
    """
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        """
        Initialize simulation cache.
        
        Args:
            max_size: Maximum number of cached results
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[SimulationResult, datetime]] = {}
        self._access_order: List[str] = []
    
    def _get_lineup_hash(self, lineup: Lineup) -> str:
        """
        Generate hash key for a lineup.
        
        Args:
            lineup: Lineup to hash
            
        Returns:
            str: Hash key
        """
        # Create deterministic string representation
        player_names = [p.name for p in lineup.players]
        lineup_str = "|".join(sorted(player_names))
        
        # Hash it
        return hashlib.md5(lineup_str.encode()).hexdigest()
    
    def has(self, lineup: Lineup) -> bool:
        """
        Check if lineup is in cache and not expired.
        
        Args:
            lineup: Lineup to check
            
        Returns:
            bool: True if cached and not expired
        """
        key = self._get_lineup_hash(lineup)
        
        if key not in self._cache:
            return False
        
        # Check expiry
        _, timestamp = self._cache[key]
        if datetime.now() - timestamp > timedelta(seconds=self.ttl_seconds):
            # Expired - remove it
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return False
        
        return True
    
    def get(self, lineup: Lineup) -> Optional[SimulationResult]:
        """
        Get cached result for a lineup.
        
        Args:
            lineup: Lineup to get result for
            
        Returns:
            Optional[SimulationResult]: Cached result or None if not found
        """
        if not self.has(lineup):
            return None
        
        key = self._get_lineup_hash(lineup)
        result, _ = self._cache[key]
        
        # Update access order (LRU)
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        
        return result
    
    def set(self, lineup: Lineup, result: SimulationResult) -> None:
        """
        Cache a simulation result.
        
        Args:
            lineup: Lineup to cache result for
            result: SimulationResult to cache
        """
        key = self._get_lineup_hash(lineup)
        
        # Check if we need to evict (LRU)
        if len(self._cache) >= self.max_size and key not in self._cache:
            # Remove least recently used
            if self._access_order:
                lru_key = self._access_order.pop(0)
                del self._cache[lru_key]
        
        # Add to cache
        self._cache[key] = (result, datetime.now())
        
        # Update access order
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
    
    def clear(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
        self._access_order.clear()


class SimulationEngine:
    """
    Monte Carlo simulation engine for DFS lineup analysis.
    
    Runs vectorized simulations with correlation support and caching.
    Optimized to run 10,000 simulations in 2-3 seconds.
    """
    
    def __init__(
        self,
        distribution_generator: Optional[DistributionGenerator] = None,
        correlation_builder: Optional[CorrelationMatrixBuilder] = None,
        enable_cache: bool = True,
        cache_size: int = 100
    ):
        """
        Initialize simulation engine.
        
        Args:
            distribution_generator: Optional custom distribution generator
            correlation_builder: Optional custom correlation matrix builder
            enable_cache: Whether to enable result caching
            cache_size: Size of result cache
        """
        self.generator = distribution_generator or DistributionGenerator()
        self.correlation_builder = correlation_builder or CorrelationMatrixBuilder()
        self.cache = SimulationCache(max_size=cache_size) if enable_cache else None
    
    def run_simulations(
        self,
        lineup: Lineup,
        n_simulations: int = 10000,
        use_correlations: bool = True
    ) -> SimulationResult:
        """
        Run Monte Carlo simulations on a single lineup.
        
        Args:
            lineup: Lineup to simulate
            n_simulations: Number of simulations to run
            use_correlations: Whether to apply player correlations
            
        Returns:
            SimulationResult: Aggregated simulation results
        """
        # Check cache
        if self.cache and self.cache.has(lineup):
            return self.cache.get(lineup)
        
        # Ensure players are PlayerProjection objects
        players = self._ensure_player_projections(lineup.players)
        
        # Generate uncorrelated samples
        samples = self.generator.generate_batch(players, n_simulations)
        
        # Apply correlations if requested
        if use_correlations:
            samples = self._apply_correlations(samples, players)
        
        # Sum across players to get total lineup scores
        lineup_scores = np.sum(samples, axis=1)
        
        # Create result
        result = SimulationResult(lineup_scores)
        
        # Cache result
        if self.cache:
            self.cache.set(lineup, result)
        
        return result
    
    def run_simulations_batch(
        self,
        lineups: List[Lineup],
        n_simulations: int = 10000,
        use_correlations: bool = True
    ) -> List[SimulationResult]:
        """
        Run simulations on multiple lineups.
        
        Args:
            lineups: List of lineups to simulate
            n_simulations: Number of simulations per lineup
            use_correlations: Whether to apply player correlations
            
        Returns:
            List[SimulationResult]: Results for each lineup
        """
        results = []
        for lineup in lineups:
            result = self.run_simulations(lineup, n_simulations, use_correlations)
            results.append(result)
        return results
    
    def _ensure_player_projections(self, players: List[Player]) -> List[PlayerProjection]:
        """
        Ensure all players are PlayerProjection objects.
        
        If a player is a base Player, converts it to PlayerProjection
        with default variance settings.
        
        Args:
            players: List of Player or PlayerProjection objects
            
        Returns:
            List[PlayerProjection]: List of PlayerProjection objects
        """
        result = []
        for player in players:
            if isinstance(player, PlayerProjection):
                result.append(player)
            else:
                # Convert Player to PlayerProjection with default variance
                # Use 24% of projection as standard deviation (rule of thumb)
                std_dev = player.projection * 0.24
                proj = PlayerProjection(
                    name=player.name,
                    position=player.position,
                    salary=player.salary,
                    projection=player.projection,
                    team=player.team,
                    opponent=player.opponent,
                    ownership=player.ownership,
                    player_id=player.player_id,
                    selection=player.selection,
                    mean_projection=player.projection,
                    std_deviation=std_dev,
                    ceiling_95th=player.projection * 1.40,  # +40% for ceiling
                    floor_5th=player.projection * 0.60      # -40% for floor
                )
                result.append(proj)
        return result
    
    def _apply_correlations(
        self,
        samples: np.ndarray,
        players: List[PlayerProjection]
    ) -> np.ndarray:
        """
        Apply correlation matrix to samples using Cholesky decomposition.
        
        Args:
            samples: Uncorrelated samples (n_simulations x n_players)
            players: List of players
            
        Returns:
            np.ndarray: Correlated samples
        """
        # Build correlation matrix
        corr_matrix = self.correlation_builder.build(players)
        
        # Check if matrix is identity (no correlations)
        if np.allclose(corr_matrix, np.eye(len(players))):
            return samples  # No correlations to apply
        
        # Standardize samples (mean=0, std=1)
        means = np.mean(samples, axis=0)
        stds = np.std(samples, axis=0)
        
        # Avoid division by zero
        stds = np.where(stds == 0, 1, stds)
        
        standardized = (samples - means) / stds
        
        try:
            # Apply Cholesky decomposition to correlation matrix
            L = np.linalg.cholesky(corr_matrix)
            
            # Apply correlation: correlated = standardized @ L.T
            correlated_std = standardized @ L.T
            
            # Unstandardize
            correlated = correlated_std * stds + means
            
            # Ensure non-negative (fantasy points can't be negative)
            correlated = np.maximum(correlated, 0)
            
            return correlated
            
        except np.linalg.LinAlgError:
            # Matrix is not positive definite - return original samples
            # This can happen with extreme correlation values
            return samples

