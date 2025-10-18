"""
Smart Value Calculator

Calculates a sophisticated, multi-factor value score that goes beyond simple projection/salary.
Incorporates opportunity metrics, trends, risk factors, and matchup quality.

ENHANCED: Phase 2 - Tier 1 Metrics Integration (October 18, 2025)
Now uses advanced metrics (TPRR, YPRR, RTE%, Success Rate) when available with graceful fallback.

DEFAULT WEIGHTS (Tournament-Optimized for GPP):
- BASE (20%): Projection per $1K - ceiling matters more than pure value
- OPPORTUNITY (30%): Volume/usage metrics - high volume = ceiling potential
- TRENDS (15%): Momentum > consistency - embrace variance
- RISK (5%): Minimal penalty - boom/bust is good in GPP
- MATCHUP (30%): Game environment - identifies ceiling games

Formula: Smart Value = BASE + OPPORTUNITY + TRENDS + RISK + MATCHUP (scaled 0-100)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

# Configure logging
logger = logging.getLogger(__name__)

# NFL Team Abbreviation to Full Name Mapping
# Used to match DraftKings abbreviations to Vegas lines full team names
TEAM_ABBREV_TO_FULL = {
    'ARI': 'Arizona Cardinals', 'ATL': 'Atlanta Falcons', 'BAL': 'Baltimore Ravens',
    'BUF': 'Buffalo Bills', 'CAR': 'Carolina Panthers', 'CHI': 'Chicago Bears',
    'CIN': 'Cincinnati Bengals', 'CLE': 'Cleveland Browns', 'DAL': 'Dallas Cowboys',
    'DEN': 'Denver Broncos', 'DET': 'Detroit Lions', 'GB': 'Green Bay Packers',
    'HOU': 'Houston Texans', 'IND': 'Indianapolis Colts', 'JAX': 'Jacksonville Jaguars',
    'KC': 'Kansas City Chiefs', 'LV': 'Las Vegas Raiders', 'LAC': 'Los Angeles Chargers',
    'LAR': 'Los Angeles Rams', 'MIA': 'Miami Dolphins', 'MIN': 'Minnesota Vikings',
    'NE': 'New England Patriots', 'NO': 'New Orleans Saints', 'NYG': 'New York Giants',
    'NYJ': 'New York Jets', 'PHI': 'Philadelphia Eagles', 'PIT': 'Pittsburgh Steelers',
    'SF': 'San Francisco 49ers', 'SEA': 'Seattle Seahawks', 'TB': 'Tampa Bay Buccaneers',
    'TEN': 'Tennessee Titans', 'WAS': 'Washington Commanders'
}


# PHASE 4.6: Projection Gates for Ceiling Boost
# Philosophy: Ceiling upside only matters if the floor is tournament-viable
# A 9.8→18.5 spike (Gainwell) is less valuable than an 18.2→28.6 spike (DJ Moore)
# Week 6 validation: ZERO winning lineups had RBs projecting <12 pts
PROJECTION_GATES = {
    'QB': {'full': 18.0, 'half': 15.0},   # QBs score more - higher threshold
    'RB': {'full': 13.0, 'half': 10.0},   # Core position - moderate threshold
    'WR': {'full': 13.0, 'half': 10.0},   # Core position - moderate threshold
    'TE': {'full': 10.0, 'half': 8.0},    # TEs score less - lower threshold
    'DST': {'full': 6.0, 'half': 4.0}     # DSTs score differently - lowest threshold
}


def get_ceiling_boost_multiplier(position: str, projection: float) -> float:
    """
    Determine ceiling boost multiplier based on projection viability.

    PHASE 4.6: Projection-Gated Ceiling Boost
    Prevents low-projection "cute contrarian" plays (e.g., Kenneth Gainwell: 9.8 proj, 1.81 value,
    0.5% own) from achieving high Smart Value through ceiling/leverage alone.

    Philosophy:
    - Tournament lineups need ~16.7 pts/player average for 150+ pt total
    - Low-projection plays can't reach this even hitting ceiling
    - Ceiling boost should only apply to tournament-viable projections

    Args:
        position: Player position (QB, RB, WR, TE, DST)
        projection: DFS projection in points

    Returns:
        float: Multiplier for ceiling boost (1.0 = full, 0.5 = half, 0.0 = blocked)

    Examples:
        - Kenneth Gainwell RB (9.8 proj): 0.0x → ceiling boost BLOCKED
        - DJ Moore WR (18.2 proj): 1.0x → full ceiling boost
        - Jake Ferguson TE (13.6 proj): 1.0x → full boost (TE threshold: 10.0)
    """
    gates = PROJECTION_GATES.get(position, {'full': 13.0, 'half': 10.0})

    if projection >= gates['full']:
        return 1.0  # Full ceiling boost
    elif projection >= gates['half']:
        return 0.5  # Half ceiling boost
    else:
        return 0.0  # Block ceiling boost - projection too low


# Weight Profiles
# NOTE: Default 'balanced' profile optimized for balanced tournament play
# Custom configuration: Reduced matchup/leverage, increased trends/regression
# Focus: More balanced approach with stronger trend analysis and regression protection
WEIGHT_PROFILES = {
    'balanced': {
        'base': 0.15,          # Value + ceiling boost multiplier (includes explosiveness)
        'opportunity': 0.22,   # Volume metrics (adjusted from 25% to 22%)
        'trends': 0.13,        # Consistency trends (increased from 10% to 13%)
        'risk': 0.05,          # EMBRACE variance (De'Von Achane effect) - variance + consistency only
        'matchup': 0.19,       # Game environment (reduced from 25% to 19%)
        'leverage': 0.13,      # Sweet spot ownership (reduced from 20% to 13%)
        'regression': 0.13     # 80/20 regression rule (increased from 5% to 13%)
    },
    'cash': {
        'base': 0.50,          # ↑ Ultra-safe for cash games
        'opportunity': 0.25,   # Consistent volume
        'trends': 0.10,        # Stable role growth
        'risk': 0.15,          # Avoid volatility
        'matchup': 0.00,       # Don't chase ceiling games
        'leverage': 0.00,      # No leverage in cash - want floor
        'regression': 0.10     # Higher regression penalty for cash games
    },
    'gpp': {
        'base': 0.05,          # ↓ Minimal value consideration
        'opportunity': 0.30,   # Max volume = max ceiling
        'trends': 0.05,        # Minimal consistency focus
        'risk': 0.00,          # ZERO variance penalty
        'matchup': 0.25,       # ↑ Max game environment focus
        'leverage': 0.35,      # ↑↑ MAXIMUM leverage for ultra-aggressive GPP
        'regression': 0.00     # No regression penalty in GPP (embrace variance)
    }
}


def min_max_scale_by_position(df: pd.DataFrame, metric_col: str) -> pd.Series:
    """
    Scale metric to [0, 1] range within each position group.

    Args:
        df: Player DataFrame with 'position' column
        metric_col: Column name to normalize

    Returns:
        Series with normalized values [0, 1]
    """
    def scale_group(x):
        if (x.max() - x.min()) > 0:
            return (x - x.min()) / (x.max() - x.min())
        else:
            return 0.5  # If all values are the same, return middle value

    return df.groupby('position')[metric_col].transform(scale_group)


def calculate_base_score(df: pd.DataFrame, weight: float) -> pd.DataFrame:
    """
    Calculate BASE score component (projection per $1K + ceiling boost + value penalty).

    PHASE 1 IMPROVEMENT: Added ceiling boost multiplier
    Week 6 analysis showed low-projection/high-ceiling plays (Kayshon Boutte: 6.9 proj, 26.3 actual)
    were undervalued. Ceiling ratio now boosts base value for explosion potential.

    PHASE 4 IMPROVEMENT: Added value ratio penalty for trap chalk
    Week 6 analysis showed Puka Nacua (2.80 value ratio, 25.6% own) killed 4/6 lineups.
    Low value ratio players (< 3.0 pts/$1K) now get penalized to prevent trap chalk.

    Args:
        df: Player DataFrame (must include 'season_ceiling' column)
        weight: Weight for this component (default 0.15)

    Returns:
        DataFrame with 'base_raw' and 'base_norm' columns
    """
    # Calculate raw value (pts per $1K)
    df['value_ratio'] = df['projection'] / (df['salary'] / 1000)
    df['base_raw'] = df['value_ratio'].copy()

    # PHASE 4 IMPROVEMENT: Value Ratio Penalty (trap chalk defense)
    # Penalize players with poor value ratios to avoid expensive busts
    # Thresholds based on Week 6 data:
    # - Good value: 3.0+ pts/$1K (no penalty)
    # - Mediocre value: 2.5-3.0 pts/$1K (15% penalty)
    # - Poor value: < 2.5 pts/$1K (30% penalty)
    def get_value_penalty(value_ratio):
        if value_ratio >= 3.0:
            return 1.0   # No penalty - good value
        elif value_ratio >= 2.5:
            return 0.85  # 15% penalty - mediocre value (Puka was 2.80)
        else:
            return 0.70  # 30% penalty - poor value

    df['value_penalty'] = df['value_ratio'].apply(get_value_penalty)
    df['base_raw'] = df['base_raw'] * df['value_penalty']

    # PHASE 1 IMPROVEMENT: Add ceiling boost for explosion potential
    # PHASE 4.6 ENHANCEMENT: Gate ceiling boost by projection viability
    # ceiling_ratio = season_ceiling / projection (e.g., Boutte: 17.4 / 6.9 = 2.52x)
    # Players with 2.5x+ ceiling get up to 50% base boost (IF projection is tournament-viable)
    if 'season_ceiling' in df.columns:
        df['ceiling_ratio'] = df['season_ceiling'] / df['projection'].replace(0, 1)  # Avoid division by zero
        df['ceiling_ratio'] = df['ceiling_ratio'].fillna(1.5)  # Default if missing

        # PHASE 4.6: Calculate projection-based multiplier
        # Blocks ceiling boost for low-projection plays (e.g., Gainwell 9.8 pts)
        # Preserves ceiling boost for tournament-viable plays (e.g., DJ Moore 18.2 pts)
        df['ceiling_multiplier'] = df.apply(
            lambda row: get_ceiling_boost_multiplier(row['position'], row['projection']),
            axis=1
        )

        # Ceiling boost: 0-50% boost for high ceiling/projection ratios
        # (ceiling_ratio - 1.0) / 2.0 scales it so 3.0x ratio = 1.0 boost (capped at 0.5)
        # MULTIPLIED by projection gate (1.0, 0.5, or 0.0)
        df['ceiling_boost'] = np.clip((df['ceiling_ratio'] - 1.0) / 2.0, 0, 0.5) * df['ceiling_multiplier']
        df['base_raw'] = df['base_raw'] * (1.0 + df['ceiling_boost'])

    # Normalize by position (0-100 scale)
    df['base_norm'] = min_max_scale_by_position(df, 'base_raw') * 100

    # Apply weight
    df['base_score'] = df['base_norm'] * weight

    return df


def calculate_opportunity_score(df: pd.DataFrame, weight: float, sub_weights: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """
    Calculate OPPORTUNITY score component (ENHANCED with advanced metrics).

    PHASE 2 ENHANCEMENT (October 18, 2025):
    - Uses TPRR (Targets Per Route Run) if available for WR/TE, fallback to season_tgt
    - Uses YPRR (Yards Per Route Run) for efficiency component
    - Uses RTE% (Route Participation) for snap quality component
    - Uses Success Rate for floor component (RBs)

    Maintains backward compatibility: works with or without new metrics

    Args:
        df: Player DataFrame (may include 'adv_*' columns from advanced stats)
        weight: Weight for this component (default 0.30)
        sub_weights: Optional dict with sub-component weights

    Returns:
        DataFrame with enhanced 'opp_score' column
    """
    # Track which advanced metrics are being used
    metrics_used = []

    # Default sub-weights if not provided
    if sub_weights is None:
        # Phase 2: New sub-weights for advanced metrics
        if any(col in df.columns for col in ['adv_tprr', 'adv_yprr', 'adv_rte_pct', 'adv_success_rate']):
            sub_weights = {
                'opp_target_quality': 0.35,    # TPRR or season_tgt
                'opp_efficiency': 0.30,         # YPRR or FP/G proxy
                'opp_snap_quality': 0.20,       # RTE% or season_snap
                'opp_floor': 0.15               # Success Rate or consistency proxy
            }
        else:
            # Legacy sub-weights if no advanced metrics
            sub_weights = {
                'opp_target_share': 0.60,
                'opp_snap_pct': 0.30,
                'opp_rz_targets': 0.10
            }

    # Initialize opportunity components
    df['opp_score'] = 0.0

    # Check if advanced metrics are available
    has_advanced_metrics = any(col in df.columns for col in ['adv_tprr', 'adv_yprr', 'adv_rte_pct', 'adv_success_rate'])

    if has_advanced_metrics:
        # PHASE 2: Use advanced metrics with graceful fallback

        # Initialize components
        df['opp_target_quality'] = 0.0
        df['opp_efficiency'] = 0.0
        df['opp_snap_quality'] = 0.0
        df['opp_floor'] = 0.0
        df['opp_raw'] = 0.0

        # For WR/TE: Use advanced metrics
        wr_te_mask = df['position'].isin(['WR', 'TE'])

        if wr_te_mask.any():
            # Target Quality: TPRR if available
            if 'adv_tprr' in df.columns and df.loc[wr_te_mask, 'adv_tprr'].notna().any():
                # TPRR is on 0-1 scale, scale to 0-100
                df.loc[wr_te_mask, 'opp_target_quality'] = df.loc[wr_te_mask, 'adv_tprr'].fillna(0) * 100
                metrics_used.append('TPRR')
            elif 'season_tgt' in df.columns:
                # Fallback to original
                max_tgt = df.loc[wr_te_mask, 'season_tgt'].max() if df.loc[wr_te_mask, 'season_tgt'].max() > 0 else 1
                df.loc[wr_te_mask, 'opp_target_quality'] = (df.loc[wr_te_mask, 'season_tgt'].fillna(0) / max_tgt) * 100

            # Efficiency: YPRR if available
            if 'adv_yprr' in df.columns and df.loc[wr_te_mask, 'adv_yprr'].notna().any():
                # YPRR typically 0-10, scale to 0-100
                df.loc[wr_te_mask, 'opp_efficiency'] = (df.loc[wr_te_mask, 'adv_yprr'].fillna(0) / 10) * 100
                metrics_used.append('YPRR')
            elif 'season_fpg' in df.columns:
                # Fallback: use FP/G as efficiency proxy
                max_fpg = df.loc[wr_te_mask, 'season_fpg'].max() if df.loc[wr_te_mask, 'season_fpg'].max() > 0 else 1
                df.loc[wr_te_mask, 'opp_efficiency'] = (df.loc[wr_te_mask, 'season_fpg'].fillna(0) / max_fpg) * 100

            # Snap Quality: RTE% if available
            if 'adv_rte_pct' in df.columns and df.loc[wr_te_mask, 'adv_rte_pct'].notna().any():
                # RTE% is already in percentage form
                df.loc[wr_te_mask, 'opp_snap_quality'] = df.loc[wr_te_mask, 'adv_rte_pct'].fillna(0)
                metrics_used.append('RTE%')
            elif 'season_snap' in df.columns:
                # Fallback to season snap %
                df.loc[wr_te_mask, 'opp_snap_quality'] = df.loc[wr_te_mask, 'season_snap'].fillna(0)

        # For RB: Use advanced metrics
        rb_mask = df['position'] == 'RB'

        if rb_mask.any():
            # Primary: Snap % (workload)
            if 'season_snap' in df.columns:
                df.loc[rb_mask, 'opp_snap_quality'] = df.loc[rb_mask, 'season_snap'].fillna(0)

            # Floor: Success Rate if available
            if 'adv_success_rate' in df.columns and df.loc[rb_mask, 'adv_success_rate'].notna().any():
                df.loc[rb_mask, 'opp_floor'] = df.loc[rb_mask, 'adv_success_rate'].fillna(0)
                metrics_used.append('Success Rate')
            elif 'season_cons' in df.columns:
                # Fallback: use inverted consistency
                df.loc[rb_mask, 'opp_floor'] = 100 - df.loc[rb_mask, 'season_cons'].fillna(0) * 10

            # RB components
            df.loc[rb_mask, 'opp_target_quality'] = df.loc[rb_mask, 'opp_snap_quality'] * 0.5
            max_proj = df.loc[rb_mask, 'projection'].max() if df.loc[rb_mask, 'projection'].max() > 0 else 1
            df.loc[rb_mask, 'opp_efficiency'] = (df.loc[rb_mask, 'projection'].fillna(0) / max_proj) * 100

        # For QB: Keep existing logic
        qb_mask = df['position'] == 'QB'

        if qb_mask.any():
            if 'season_snap' in df.columns:
                df.loc[qb_mask, 'opp_snap_quality'] = df.loc[qb_mask, 'season_snap'].fillna(0)

            max_proj = df.loc[qb_mask, 'projection'].max() if df.loc[qb_mask, 'projection'].max() > 0 else 1
            df.loc[qb_mask, 'opp_efficiency'] = (df.loc[qb_mask, 'projection'].fillna(0) / max_proj) * 100
            df.loc[qb_mask, 'opp_target_quality'] = df.loc[qb_mask, 'opp_efficiency'] * 0.5
            df.loc[qb_mask, 'opp_floor'] = 50  # QBs have decent floor

        # Combine components
        df['opp_raw'] = (
            df['opp_target_quality'] * sub_weights.get('opp_target_quality', 0.35) +
            df['opp_efficiency'] * sub_weights.get('opp_efficiency', 0.30) +
            df['opp_snap_quality'] * sub_weights.get('opp_snap_quality', 0.20) +
            df['opp_floor'] * sub_weights.get('opp_floor', 0.15)
        )

        # Normalize by position then apply weight
        for position in df['position'].unique():
            pos_mask = df['position'] == position
            if pos_mask.any():
                pos_min = df.loc[pos_mask, 'opp_raw'].min()
                pos_max = df.loc[pos_mask, 'opp_raw'].max()

                if pos_max > pos_min:
                    df.loc[pos_mask, 'opp_score'] = ((df.loc[pos_mask, 'opp_raw'] - pos_min) /
                                                     (pos_max - pos_min)) * weight
                else:
                    df.loc[pos_mask, 'opp_score'] = 0.5 * weight

        # Log metrics used
        if metrics_used:
            logger.info(f"✅ Phase 2: Advanced metrics integrated into OPPORTUNITY score: {', '.join(metrics_used)}")

    else:
        # LEGACY: Original opportunity calculation

        # Extract sub-weights for WR/TE
        tgt_weight = sub_weights.get('opp_target_share', 0.60)
        snap_weight = sub_weights.get('opp_snap_pct', 0.30)
        rz_weight = sub_weights.get('opp_rz_targets', 0.10)

        # For each position, calculate opportunity differently
        for position in df['position'].unique():
            pos_mask = df['position'] == position
            pos_df = df[pos_mask].copy()

            if position == 'QB':
                # QB: Use projection as proxy for opportunity
                if 'season_snap' in df.columns and pos_df['season_snap'].notna().any():
                    opp_metric = pos_df['season_snap'] / 100
                else:
                    opp_metric = pos_df['projection'] / pos_df['projection'].max() if pos_df['projection'].max() > 0 else 0.5

                df.loc[pos_mask, 'opp_score'] = opp_metric * weight

            elif position == 'RB':
                # RB: Snap % is king
                if 'season_snap' in df.columns and pos_df['season_snap'].notna().any():
                    snap_pct = pos_df['season_snap'] / 100
                    opp_metric = snap_pct
                else:
                    opp_metric = pos_df['projection'] / pos_df['projection'].max() if pos_df['projection'].max() > 0 else 0.5

                df.loc[pos_mask, 'opp_score'] = opp_metric * weight

            elif position in ['WR', 'TE']:
                # WR/TE: Target Share + Snap % + RZ Targets
                total_opp = 0.0

                # Target Share component
                if 'season_tgt' in df.columns and pos_df['season_tgt'].notna().any():
                    tgt_max = pos_df['season_tgt'].max()
                    if tgt_max > 0:
                        tgt_norm = pos_df['season_tgt'] / tgt_max
                        total_opp += tgt_norm * tgt_weight

                # Snap % component
                if 'season_snap' in df.columns and pos_df['season_snap'].notna().any():
                    snap_norm = pos_df['season_snap'] / 100
                    total_opp += snap_norm * snap_weight

                # Red Zone Targets component
                if 'season_eztgt' in df.columns and pos_df['season_eztgt'].notna().any():
                    rz_max = pos_df['season_eztgt'].max()
                    if rz_max > 0:
                        rz_norm = pos_df['season_eztgt'] / rz_max
                        total_opp += rz_norm * rz_weight

                # If no opportunity data available, use projection proxy
                if isinstance(total_opp, pd.Series) and total_opp.sum() == 0:
                    total_opp = pos_df['projection'] / pos_df['projection'].max() if pos_df['projection'].max() > 0 else 0.5
                elif not isinstance(total_opp, pd.Series) and total_opp == 0:
                    total_opp = pos_df['projection'] / pos_df['projection'].max() if pos_df['projection'].max() > 0 else 0.5

                df.loc[pos_mask, 'opp_score'] = total_opp * weight

    return df


def calculate_trends_score(df: pd.DataFrame, weight: float, sub_weights: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """
    Calculate TRENDS score component (momentum, role trend, recent production) with configurable sub-weights.

    Uses:
    - Momentum (production change recent vs early)
    - Role change (snap trend W1 → W5)
    - Consistency bonus/penalty

    Args:
        df: Player DataFrame
        weight: Weight for this component (default 0.15)
        sub_weights: Optional dict with keys 'trends_momentum', 'trends_role', 'trends_consistency'
                    Defaults to {0.50, 0.30, 0.20} if not provided

    Returns:
        DataFrame with 'trends_score' column
    """
    # Default sub-weights if not provided
    if sub_weights is None:
        sub_weights = {
            'trends_momentum': 0.50,      # Recent production trend
            'trends_role': 0.30,         # Role/snap trend
            'trends_consistency': 0.20   # Consistency factor
        }

    # Extract sub-weights
    mom_weight = sub_weights.get('trends_momentum', 0.50)
    role_weight = sub_weights.get('trends_role', 0.30)
    cons_weight = sub_weights.get('trends_consistency', 0.20)

    df['trends_score'] = 0.0

    # Component 1: Momentum (recent vs early production)
    if 'season_mom' in df.columns and df['season_mom'].notna().any():
        # Normalize momentum to [0, 1] with 0.5 as neutral
        # Positive momentum (recent > early) gets boost, negative gets penalty
        mom_max = df['season_mom'].abs().max()
        if mom_max > 0:
            df['trends_momentum'] = (df['season_mom'] / mom_max + 1) / 2  # Scale to [0, 1]
        else:
            df['trends_momentum'] = 0.5
    else:
        df['trends_momentum'] = 0.5

    # Component 2: Role trend (snap % change W1 → W5)
    if 'season_trend' in df.columns and df['season_trend'].notna().any():
        # Normalize trend to [0, 1] with 0.5 as neutral
        trend_max = df['season_trend'].abs().max()
        if trend_max > 0:
            df['trends_role'] = (df['season_trend'] / trend_max + 1) / 2  # Scale to [0, 1]
        else:
            df['trends_role'] = 0.5
    else:
        df['trends_role'] = 0.5

    # Component 3: Consistency (lower is better for cash, worse for GPP)
    if 'season_cons' in df.columns and df['season_cons'].notna().any():
        # For balanced/GPP: embrace variance (higher consistency = penalty)
        # Invert consistency: low STD = consistent = lower score (we want variance)
        cons_max = df['season_cons'].max()
        if cons_max > 0:
            df['trends_consistency'] = 1 - (df['season_cons'] / cons_max)  # Invert
        else:
            df['trends_consistency'] = 0.5
    else:
        df['trends_consistency'] = 0.5

    # Combine components with sub-weights
    df['trends_raw'] = (
        df['trends_momentum'] * mom_weight +
        df['trends_role'] * role_weight +
        df['trends_consistency'] * cons_weight
    )

    # Scale to [0, 1] and apply weight
    df['trends_norm'] = min_max_scale_by_position(df, 'trends_raw')
    df['trends_score'] = df['trends_norm'] * weight

    return df


def calculate_risk_score(df: pd.DataFrame, weight: float) -> pd.DataFrame:
    """
    Calculate RISK score component (EMBRACE variance in GPP).

    GPP Philosophy: Variance is good! We want boom/bust players.
    Uses:
    - Variance metric (higher variance = BETTER for GPP)
    - Consistency penalty (too consistent = bad for GPP)

    Args:
        df: Player DataFrame
        weight: Weight for this component (default 0.05)

    Returns:
        DataFrame with 'risk_score' column
    """
    df['risk_score'] = 0.0

    # Component 1: Variance (HIGHER IS BETTER for GPP)
    if 'season_var' in df.columns and df['season_var'].notna().any():
        # Normalize variance by position
        # HIGH variance = LOW risk score (we want boom/bust)
        df['risk_variance'] = min_max_scale_by_position(df, 'season_var')
        # Invert: high variance = good
        df['risk_variance'] = 1 - df['risk_variance']  # Now high variance = high score
    else:
        df['risk_variance'] = 0.5

    # Component 2: Consistency penalty (too consistent = bad for GPP)
    if 'season_cons' in df.columns and df['season_cons'].notna().any():
        # High consistency = penalty
        df['risk_consistency'] = min_max_scale_by_position(df, 'season_cons')
        # Keep as is: high consistency = high penalty = bad
    else:
        df['risk_consistency'] = 0.5

    # Combine: Embrace variance, penalize consistency
    # Weight variance more (70%) than consistency penalty (30%)
    df['risk_raw'] = df['risk_variance'] * 0.7 + df['risk_consistency'] * 0.3

    # Since we're embracing risk, invert the final score
    # High risk (variance) = LOW penalty = GOOD
    df['risk_score'] = (1 - df['risk_raw']) * weight  # Invert so high variance = low penalty

    return df


def calculate_matchup_score(df: pd.DataFrame, weight: float, vegas_lines: Optional[pd.DataFrame] = None,
                          week: int = 6) -> pd.DataFrame:
    """
    Calculate MATCHUP score component (game environment factors).

    Uses:
    - Vegas game total (higher = more scoring)
    - Team implied total (ITT)
    - Spread (negative = favorite)

    Args:
        df: Player DataFrame with 'team' and 'opponent' columns
        weight: Weight for this component (default 0.30)
        vegas_lines: DataFrame with Vegas data (optional)
        week: Current week number

    Returns:
        DataFrame with 'matchup_score' column
    """
    df['matchup_score'] = 0.0
    df['matchup_raw'] = 0.0

    # If no Vegas lines provided, use projection proxy
    if vegas_lines is None or vegas_lines.empty:
        # Fallback: use projection as matchup proxy
        df['matchup_raw'] = min_max_scale_by_position(df, 'projection')
        df['matchup_score'] = df['matchup_raw'] * weight
        return df

    # Process Vegas lines for each player
    for idx, player in df.iterrows():
        team = player.get('team', '')
        opponent = player.get('opponent', '')

        if not team or not opponent:
            df.at[idx, 'matchup_raw'] = 0.5  # Neutral if missing data
            continue

        # Try to find game in Vegas lines
        team_full = TEAM_ABBREV_TO_FULL.get(team, team)
        opp_full = TEAM_ABBREV_TO_FULL.get(opponent, opponent)

        # Look for game in either direction (team as home or away)
        game_line = vegas_lines[
            ((vegas_lines['home_team'] == team_full) & (vegas_lines['away_team'] == opp_full)) |
            ((vegas_lines['home_team'] == opp_full) & (vegas_lines['away_team'] == team_full))
        ]

        if not game_line.empty:
            game_line = game_line.iloc[0]

            # Extract key metrics
            game_total = game_line.get('total', 45)  # Default 45 if missing

            # Determine if player's team is home or away
            if game_line['home_team'] == team_full:
                team_spread = -game_line.get('spread', 0)  # Negative spread = favorite
                team_itt = (game_total / 2) - (team_spread / 2)
            else:
                team_spread = game_line.get('spread', 0)
                team_itt = (game_total / 2) - (team_spread / 2)

            # Calculate matchup score components
            # 1. Game total factor (higher = better)
            total_factor = game_total / 50  # Normalize around 50 points

            # 2. ITT factor (higher = better)
            itt_factor = team_itt / 25  # Normalize around 25 points

            # 3. Favorite factor (negative spread = favorite = better)
            spread_factor = 1 + (-team_spread / 20)  # -10 spread = 1.5x, +10 = 0.5x

            # Combine factors (weighted)
            matchup_value = (total_factor * 0.4 + itt_factor * 0.4 + spread_factor * 0.2)

            df.at[idx, 'matchup_raw'] = matchup_value
        else:
            # No Vegas data found, use neutral
            df.at[idx, 'matchup_raw'] = 0.5

    # Normalize by position and apply weight
    df['matchup_norm'] = min_max_scale_by_position(df, 'matchup_raw')
    df['matchup_score'] = df['matchup_norm'] * weight

    return df


def calculate_leverage_score(df: pd.DataFrame, weight: float) -> pd.DataFrame:
    """
    Calculate LEVERAGE score component (ownership arbitrage).

    Philosophy: Find the ownership sweet spot
    - Too low (<2%) = likely bad play
    - Too high (>20%) = no leverage
    - Sweet spot: 5-15% ownership

    Args:
        df: Player DataFrame with 'ownership' column
        weight: Weight for this component (default 0.20)

    Returns:
        DataFrame with 'leverage_score' column
    """
    df['leverage_score'] = 0.0

    if 'ownership' not in df.columns:
        # No ownership data, use ceiling as proxy
        if 'season_ceiling' in df.columns:
            df['leverage_raw'] = min_max_scale_by_position(df, 'season_ceiling')
            df['leverage_score'] = df['leverage_raw'] * weight
        return df

    # Calculate leverage based on ownership sweet spot
    def get_leverage_multiplier(ownership):
        """
        Get leverage multiplier based on ownership %.

        <2%: 0.3x (too contrarian)
        2-5%: 0.7x (low but playable)
        5-10%: 1.0x (perfect leverage)
        10-15%: 0.9x (good leverage)
        15-20%: 0.6x (getting chalky)
        20-30%: 0.3x (too chalky)
        >30%: 0.1x (no leverage)
        """
        if ownership < 2:
            return 0.3
        elif ownership < 5:
            return 0.7
        elif ownership < 10:
            return 1.0  # Sweet spot
        elif ownership < 15:
            return 0.9  # Still good
        elif ownership < 20:
            return 0.6
        elif ownership < 30:
            return 0.3
        else:
            return 0.1  # Mega chalk

    # Apply leverage multiplier
    df['leverage_multiplier'] = df['ownership'].apply(get_leverage_multiplier)

    # Also consider ceiling for leverage plays
    if 'season_ceiling' in df.columns:
        # High ceiling + good ownership = maximum leverage
        df['leverage_raw'] = df['leverage_multiplier'] * min_max_scale_by_position(df, 'season_ceiling')
    else:
        df['leverage_raw'] = df['leverage_multiplier']

    # Normalize and apply weight
    df['leverage_norm'] = min_max_scale_by_position(df, 'leverage_raw')
    df['leverage_score'] = df['leverage_norm'] * weight

    return df


def calculate_regression_score(df: pd.DataFrame, weight: float) -> pd.DataFrame:
    """
    Calculate REGRESSION score component (80/20 rule protection).

    Philosophy: 80% of fantasy production comes from 20% of players.
    Penalize players unlikely to be in that 20%.

    Args:
        df: Player DataFrame
        weight: Weight for this component (default 0.05)

    Returns:
        DataFrame with 'regression_score' column (this is a PENALTY)
    """
    df['regression_score'] = 0.0

    # Identify the elite tier (top 20% by projection within position)
    for position in df['position'].unique():
        pos_mask = df['position'] == position
        pos_df = df[pos_mask].copy()

        if len(pos_df) > 0:
            # Get 80th percentile projection threshold
            threshold_80 = pos_df['projection'].quantile(0.8)

            # Players below 80th percentile get regression penalty
            # The further below, the higher the penalty
            below_threshold = pos_df['projection'] < threshold_80

            if below_threshold.any():
                # Calculate penalty: distance from threshold
                max_proj = pos_df['projection'].max()
                if max_proj > threshold_80:
                    penalty = (threshold_80 - pos_df['projection']) / (max_proj - threshold_80)
                    penalty = penalty.clip(0, 1)  # Cap at 1
                    df.loc[pos_mask, 'regression_penalty'] = penalty
                else:
                    df.loc[pos_mask, 'regression_penalty'] = 0
            else:
                df.loc[pos_mask, 'regression_penalty'] = 0

    # Apply regression penalty (this REDUCES score)
    df['regression_score'] = df.get('regression_penalty', 0) * weight  # This is subtracted later

    return df


def calculate_smart_value(df: pd.DataFrame,
                         profile: str = 'balanced',
                         custom_weights: Optional[Dict[str, float]] = None,
                         vegas_lines: Optional[pd.DataFrame] = None,
                         include_components: bool = False) -> pd.DataFrame:
    """
    Calculate comprehensive Smart Value score.

    Args:
        df: Player DataFrame with required columns
        profile: Weight profile ('balanced', 'cash', 'gpp')
        custom_weights: Optional custom weight dictionary
        vegas_lines: Optional Vegas lines DataFrame
        include_components: If True, keep component columns in output

    Returns:
        DataFrame with 'smart_value' column (0-100 scale)
    """
    # Get weights
    if custom_weights:
        weights = custom_weights
    else:
        weights = WEIGHT_PROFILES.get(profile, WEIGHT_PROFILES['balanced'])

    # Calculate each component
    df = calculate_base_score(df, weights['base'])
    df = calculate_opportunity_score(df, weights['opportunity'])
    df = calculate_trends_score(df, weights['trends'])
    df = calculate_risk_score(df, weights['risk'])
    df = calculate_matchup_score(df, weights['matchup'], vegas_lines)
    df = calculate_leverage_score(df, weights['leverage'])
    df = calculate_regression_score(df, weights['regression'])

    # Combine all components
    # Note: regression_score is a PENALTY (subtracted)
    df['smart_value_raw'] = (
        df.get('base_score', 0) +
        df.get('opp_score', 0) +
        df.get('trends_score', 0) +
        df.get('risk_score', 0) +
        df.get('matchup_score', 0) +
        df.get('leverage_score', 0) -
        df.get('regression_score', 0)  # Subtract regression penalty
    )

    # Scale to 0-100
    min_val = df['smart_value_raw'].min()
    max_val = df['smart_value_raw'].max()

    if max_val > min_val:
        df['smart_value'] = ((df['smart_value_raw'] - min_val) / (max_val - min_val)) * 100
    else:
        df['smart_value'] = 50  # Default if all same

    # Clean up intermediate columns if not needed
    if not include_components:
        component_cols = ['base_raw', 'base_norm', 'opp_raw', 'trends_raw', 'trends_norm',
                         'risk_raw', 'matchup_raw', 'matchup_norm', 'leverage_raw',
                         'leverage_norm', 'regression_penalty', 'smart_value_raw',
                         'value_ratio', 'value_penalty', 'ceiling_ratio', 'ceiling_boost',
                         'ceiling_multiplier', 'trends_momentum', 'trends_role',
                         'trends_consistency', 'risk_variance', 'risk_consistency',
                         'leverage_multiplier', 'opp_target_quality', 'opp_efficiency',
                         'opp_snap_quality', 'opp_floor']

        for col in component_cols:
            if col in df.columns:
                df = df.drop(columns=[col])

    return df


# Phase 2: A/B Testing Functions
def add_ab_testing_capability(df: pd.DataFrame, use_advanced_metrics: bool = True) -> pd.DataFrame:
    """
    Add A/B testing capability to compare lineups with/without advanced metrics.

    Args:
        df: Player DataFrame
        use_advanced_metrics: If True, use advanced metrics; if False, set them to None

    Returns:
        DataFrame with or without advanced metrics based on flag
    """
    if not use_advanced_metrics:
        # Create a copy to avoid modifying original
        df = df.copy()

        # List of advanced metric columns to nullify
        advanced_columns = [
            'adv_tprr', 'adv_yprr', 'adv_rte_pct',
            'adv_yaco_att', 'adv_success_rate',
            'adv_cpoe', 'adv_adot', 'adv_deep_throw_pct',
            'adv_1read_pct', 'adv_mtf_att'
        ]

        # Set advanced columns to NaN if they exist
        for col in advanced_columns:
            if col in df.columns:
                df[col] = np.nan

        logger.info("A/B Testing: Advanced metrics DISABLED")
    else:
        logger.info("A/B Testing: Advanced metrics ENABLED")

    return df


def generate_ab_comparison_report(lineups_with: pd.DataFrame, lineups_without: pd.DataFrame) -> Dict:
    """
    Generate comparison report between lineups with and without advanced metrics.

    Args:
        lineups_with: Lineups generated WITH advanced metrics
        lineups_without: Lineups generated WITHOUT advanced metrics

    Returns:
        Dictionary containing comparison metrics
    """
    report = {
        'with_advanced': {
            'count': len(lineups_with),
            'avg_projection': lineups_with['total_projection'].mean() if 'total_projection' in lineups_with.columns else 0,
            'avg_smart_value': lineups_with['total_smart_value'].mean() if 'total_smart_value' in lineups_with.columns else 0,
            'std_projection': lineups_with['total_projection'].std() if 'total_projection' in lineups_with.columns else 0,
        },
        'without_advanced': {
            'count': len(lineups_without),
            'avg_projection': lineups_without['total_projection'].mean() if 'total_projection' in lineups_without.columns else 0,
            'avg_smart_value': lineups_without['total_smart_value'].mean() if 'total_smart_value' in lineups_without.columns else 0,
            'std_projection': lineups_without['total_projection'].std() if 'total_projection' in lineups_without.columns else 0,
        },
        'improvement': {}
    }

    # Calculate improvements
    if report['without_advanced']['avg_projection'] > 0:
        report['improvement']['projection_pct'] = (
            (report['with_advanced']['avg_projection'] - report['without_advanced']['avg_projection']) /
            report['without_advanced']['avg_projection'] * 100
        )

    if report['without_advanced']['avg_smart_value'] > 0:
        report['improvement']['smart_value_pct'] = (
            (report['with_advanced']['avg_smart_value'] - report['without_advanced']['avg_smart_value']) /
            report['without_advanced']['avg_smart_value'] * 100
        )

    # Log summary
    logger.info("=" * 60)
    logger.info("A/B TEST COMPARISON REPORT")
    logger.info("=" * 60)
    logger.info(f"Lineups WITH advanced metrics:")
    logger.info(f"  Avg Projection: {report['with_advanced']['avg_projection']:.2f}")
    logger.info(f"  Avg Smart Value: {report['with_advanced']['avg_smart_value']:.2f}")
    logger.info(f"Lineups WITHOUT advanced metrics:")
    logger.info(f"  Avg Projection: {report['without_advanced']['avg_projection']:.2f}")
    logger.info(f"  Avg Smart Value: {report['without_advanced']['avg_smart_value']:.2f}")

    if 'projection_pct' in report['improvement']:
        logger.info(f"IMPROVEMENT: {report['improvement']['projection_pct']:.1f}% in projection")
    if 'smart_value_pct' in report['improvement']:
        logger.info(f"IMPROVEMENT: {report['improvement']['smart_value_pct']:.1f}% in smart value")

    logger.info("=" * 60)

    return report


def get_available_profiles() -> list:
    """
    Get list of available Smart Value profiles.
    
    Returns:
        List of profile names
    """
    return list(WEIGHT_PROFILES.keys())