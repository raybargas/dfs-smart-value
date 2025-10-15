"""
Smart Value Calculator

Calculates a sophisticated, multi-factor value score that goes beyond simple projection/salary.
Incorporates opportunity metrics, trends, risk factors, and matchup quality.

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


# Weight Profiles
# NOTE: Default 'balanced' profile is TOURNAMENT-OPTIMIZED based on Week 6 winners analysis
# Week 6 post-mortem: Leverage plays (Pickens 10.6%, McConkey 14.1%) were undervalued
# PHASE 1 IMPROVEMENTS: Doubled leverage weight, rebalanced opportunity/matchup
WEIGHT_PROFILES = {
    'balanced': {
        'base': 0.15,          # Value + ceiling boost multiplier (includes explosiveness)
        'opportunity': 0.25,   # ↓ Volume metrics (reduced 5% to balance leverage increase)
        'trends': 0.10,        # Consistency matters less in tournaments
        'risk': 0.05,          # EMBRACE variance (De'Von Achane effect)
        'matchup': 0.25,       # ↓ Game environment (reduced 5% to balance leverage increase)
        'leverage': 0.20       # ↑↑ DOUBLED from 0.10 - Sweet spot ownership now impactful
    },
    'cash': {
        'base': 0.50,          # ↑ Ultra-safe for cash games
        'opportunity': 0.25,   # Consistent volume
        'trends': 0.10,        # Stable role growth
        'risk': 0.15,          # Avoid volatility
        'matchup': 0.00,       # Don't chase ceiling games
        'leverage': 0.00       # No leverage in cash - want floor
    },
    'gpp': {
        'base': 0.05,          # ↓ Minimal value consideration
        'opportunity': 0.30,   # Max volume = max ceiling
        'trends': 0.05,        # Minimal consistency focus
        'risk': 0.00,          # ZERO variance penalty
        'matchup': 0.25,       # ↑ Max game environment focus
        'leverage': 0.35       # ↑↑ MAXIMUM leverage for ultra-aggressive GPP
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
    Calculate BASE score component (projection per $1K + ceiling boost).
    
    PHASE 1 IMPROVEMENT: Added ceiling boost multiplier
    Week 6 analysis showed low-projection/high-ceiling plays (Kayshon Boutte: 6.9 proj, 26.3 actual)
    were undervalued. Ceiling ratio now boosts base value for explosion potential.
    
    Args:
        df: Player DataFrame (must include 'season_ceiling' column)
        weight: Weight for this component (default 0.15)
    
    Returns:
        DataFrame with 'base_raw' and 'base_norm' columns
    """
    # Calculate raw value (pts per $1K)
    df['base_raw'] = df['projection'] / (df['salary'] / 1000)
    
    # PHASE 1 IMPROVEMENT: Add ceiling boost for explosion potential
    # ceiling_ratio = season_ceiling / projection (e.g., Boutte: 17.4 / 6.9 = 2.52x)
    # Players with 2.5x+ ceiling get up to 50% base boost
    if 'season_ceiling' in df.columns:
        df['ceiling_ratio'] = df['season_ceiling'] / df['projection'].replace(0, 1)  # Avoid division by zero
        df['ceiling_ratio'] = df['ceiling_ratio'].fillna(1.5)  # Default if missing
        
        # Ceiling boost: 0-50% boost for high ceiling/projection ratios
        # (ceiling_ratio - 1.0) / 2.0 scales it so 3.0x ratio = 1.0 boost (capped at 0.5)
        df['ceiling_boost'] = np.clip((df['ceiling_ratio'] - 1.0) / 2.0, 0, 0.5)
        
        # Apply boost: base_raw * (1 + boost)
        # Example: Boutte with 2.52x ratio → 0.38 boost → 38% increase to base value
        df['base_raw'] = df['base_raw'] * (1 + df['ceiling_boost'])
    
    # Normalize by position
    df['base_norm'] = min_max_scale_by_position(df, 'base_raw')
    
    # Apply weight
    df['base_score'] = df['base_norm'] * weight
    
    return df


def calculate_opportunity_score(df: pd.DataFrame, weight: float, sub_weights: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """
    Calculate OPPORTUNITY score component (position-specific volume/usage indicators).
    
    QB: Uses Vegas ITT (if available) or defaults to projection-based proxy
    RB: Uses Snap %
    WR/TE: Uses Target Share + Snap % + Red Zone Targets (with configurable sub-weights)
    
    Args:
        df: Player DataFrame
        weight: Weight for this component (default 0.30)
        sub_weights: Optional dict with keys 'opp_target_share', 'opp_snap_pct', 'opp_rz_targets'
                    Defaults to {0.60, 0.30, 0.10} if not provided
    
    Returns:
        DataFrame with 'opp_score' column
    """
    # Default sub-weights if not provided
    if sub_weights is None:
        sub_weights = {
            'opp_target_share': 0.60,
            'opp_snap_pct': 0.30,
            'opp_rz_targets': 0.10
        }
    
    # Extract sub-weights for WR/TE
    tgt_weight = sub_weights.get('opp_target_share', 0.60)
    snap_weight = sub_weights.get('opp_snap_pct', 0.30)
    rz_weight = sub_weights.get('opp_rz_targets', 0.10)
    df['opp_score'] = 0.0
    
    # For each position, calculate opportunity differently
    for position in df['position'].unique():
        pos_mask = df['position'] == position
        pos_df = df[pos_mask].copy()
        
        if position == 'QB':
            # QB: Use projection as proxy for opportunity (better QBs get more pass attempts)
            # Normalize projection within QB group
            if 'season_snap' in df.columns and pos_df['season_snap'].notna().any():
                # Use snap % if available
                opp_metric = pos_df['season_snap'] / 100  # Already a percentage
            else:
                # Fallback to projection-based proxy
                opp_metric = pos_df['projection'] / pos_df['projection'].max() if pos_df['projection'].max() > 0 else 0.5
            
            df.loc[pos_mask, 'opp_score'] = opp_metric * weight
        
        elif position == 'RB':
            # RB: Snap % is king (workhouse indicator)
            if 'season_snap' in df.columns and pos_df['season_snap'].notna().any():
                snap_pct = pos_df['season_snap'] / 100
                opp_metric = snap_pct
            else:
                # Fallback: use projection as proxy
                opp_metric = pos_df['projection'] / pos_df['projection'].max() if pos_df['projection'].max() > 0 else 0.5
            
            df.loc[pos_mask, 'opp_score'] = opp_metric * weight
        
        elif position in ['WR', 'TE']:
            # WR/TE: Target Share + Snap % + RZ Targets (configurable sub-weights)
            total_opp = 0.0
            
            # Target Share component (if available)
            if 'season_tgt' in df.columns and pos_df['season_tgt'].notna().any():
                # Normalize target share within position
                tgt_max = pos_df['season_tgt'].max()
                if tgt_max > 0:
                    tgt_norm = pos_df['season_tgt'] / tgt_max
                    total_opp += tgt_norm * tgt_weight  # Use custom sub-weight
            
            # Snap % component (if available)
            if 'season_snap' in df.columns and pos_df['season_snap'].notna().any():
                snap_norm = pos_df['season_snap'] / 100
                total_opp += snap_norm * snap_weight  # Use custom sub-weight
            
            # Red Zone Targets component (if available)
            if 'season_eztgt' in df.columns and pos_df['season_eztgt'].notna().any():
                rz_max = pos_df['season_eztgt'].max()
                if rz_max > 0:
                    rz_norm = pos_df['season_eztgt'] / rz_max
                    total_opp += rz_norm * rz_weight  # Use custom sub-weight
            
            # If no opportunity data available, use projection proxy
            if total_opp.sum() == 0:
                total_opp = pos_df['projection'] / pos_df['projection'].max() if pos_df['projection'].max() > 0 else 0.5
            
            df.loc[pos_mask, 'opp_score'] = total_opp * weight
    
    return df


def calculate_trends_score(df: pd.DataFrame, weight: float, sub_weights: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """
    Calculate TRENDS score component (momentum, role trend, recent production) with configurable sub-weights.
    
    Uses:
    - Momentum (production change recent vs early)
    - Trend (snap % change W1→W5)
    - FP/G (recent production level)
    
    Args:
        df: Player DataFrame
        weight: Weight for this component (default 0.15)
        sub_weights: Optional dict with keys 'trends_momentum', 'trends_trend', 'trends_fpg'
                    Defaults to {0.50, 0.30, 0.20} if not provided
    
    Returns:
        DataFrame with 'trends_score' column
    """
    # Default sub-weights if not provided
    if sub_weights is None:
        sub_weights = {
            'trends_momentum': 0.50,
            'trends_trend': 0.30,
            'trends_fpg': 0.20
        }
    
    # Extract sub-weights
    mom_weight = sub_weights.get('trends_momentum', 0.50)
    trend_weight = sub_weights.get('trends_trend', 0.30)
    fpg_weight = sub_weights.get('trends_fpg', 0.20)
    df['trends_score'] = 0.0
    
    # Momentum component (if available)
    if 'season_mom' in df.columns:
        # Normalize momentum: +/-10 FP is max/min
        mom_norm = df['season_mom'].clip(-10, 10) / 10  # Range: [-1, 1]
        mom_norm = (mom_norm + 1) / 2  # Convert to [0, 1]
        df['trends_score'] += mom_norm * (weight * mom_weight)  # Use custom sub-weight
    
    # Trend component (if available)
    if 'season_trend' in df.columns:
        # Normalize trend: +/-30% snap change is max/min
        trend_norm = df['season_trend'].clip(-30, 30) / 30  # Range: [-1, 1]
        trend_norm = (trend_norm + 1) / 2  # Convert to [0, 1]
        df['trends_score'] += trend_norm * (weight * trend_weight)  # Use custom sub-weight
    
    # FP/G component (if available)
    if 'season_fpg' in df.columns:
        # Normalize FP/G by position (high scorers get credit)
        fpg_norm = min_max_scale_by_position(df, 'season_fpg')
        df['trends_score'] += fpg_norm * (weight * fpg_weight)  # Use custom sub-weight
    
    return df


def calculate_risk_score(df: pd.DataFrame, weight: float, sub_weights: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """
    Calculate RISK score component (regression risk, variance/luck, consistency) with configurable sub-weights.
    
    Uses:
    - Regression Risk (80/20 rule) - penalty for players who scored 20+ last week
    - XFP Variance (luck indicator) - bonus for unlucky players, penalty for lucky
    - Consistency (snap % volatility) - bonus for stable roles
    
    Args:
        df: Player DataFrame
        weight: Weight for this component (default 0.10)
        sub_weights: Optional dict with keys 'risk_regression', 'risk_variance', 'risk_consistency'
                    Defaults to {0.50, 0.30, 0.20} if not provided
    
    Returns:
        DataFrame with 'risk_score' column
    """
    # Default sub-weights if not provided
    if sub_weights is None:
        sub_weights = {
            'risk_regression': 0.50,
            'risk_variance': 0.30,
            'risk_consistency': 0.20
        }
    
    # Extract sub-weights
    reg_weight = sub_weights.get('risk_regression', 0.50)
    var_weight = sub_weights.get('risk_variance', 0.30)
    cons_weight = sub_weights.get('risk_consistency', 0.20)
    df['risk_score'] = 0.0
    
    # Regression penalty (if available)
    if 'regression_risk' in df.columns:
        # -0.5 for regression warning, 0 otherwise
        regression_adjustment = df['regression_risk'].apply(
            lambda x: -0.5 if isinstance(x, str) and '⚠️' in x else 0
        )
        df['risk_score'] += regression_adjustment * (weight * reg_weight)  # Use custom sub-weight
    
    # XFP Variance bonus/penalty (if available)
    if 'season_var' in df.columns:
        # Negative variance (unlucky) = +0.3, Positive (lucky) = -0.2
        variance_adjustment = df['season_var'].apply(
            lambda x: 0.3 if x < -2 else (-0.2 if x > 2 else 0) if pd.notna(x) else 0
        )
        df['risk_score'] += variance_adjustment * (weight * var_weight)  # Use custom sub-weight
    
    # Consistency bonus (if available)
    if 'season_cons' in df.columns:
        # Low consistency (<5) = +0.2, High (>10) = -0.2
        consistency_adjustment = df['season_cons'].apply(
            lambda x: 0.2 if x < 5 else (-0.2 if x > 10 else 0) if pd.notna(x) else 0
        )
        df['risk_score'] += consistency_adjustment * (weight * cons_weight)  # Use custom sub-weight
    
    return df


def calculate_matchup_score(df: pd.DataFrame, weight: float, week: int = 6) -> pd.DataFrame:
    """
    Calculate MATCHUP score component (game environment quality) using Vegas lines.
    
    Uses actual Vegas data (game totals, ITT) to identify ceiling games:
    - High game totals (50+) = shootout environment
    - High ITT = team expected to score
    - Combined score identifies best game stacks
    
    Args:
        df: Player DataFrame with 'team' column
        weight: Weight for this component (default 0.20)
        week: NFL week number for Vegas lines lookup
    
    Returns:
        DataFrame with 'matchup_score' column
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.database_models import VegasLine
    
    try:
        # Load Vegas lines from database
        engine = create_engine('sqlite:///dfs_optimizer.db')
        Session = sessionmaker(bind=engine)
        session = Session()
        
        vegas_lines = session.query(VegasLine).filter_by(week=week).all()
        session.close()
        
        if not vegas_lines:
            # Fallback: use projection as proxy if no Vegas data
            matchup_norm = min_max_scale_by_position(df, 'projection')
            df['matchup_score'] = matchup_norm * weight * 0.5
            df['game_total'] = 0
            df['team_itt'] = 0
            return df
        
        # Build Vegas lookup: team -> {game_total, itt}
        vegas_map = {}
        for line in vegas_lines:
            vegas_map[line.home_team] = {
                'game_total': line.total if line.total else 45.0,  # Default to 45
                'itt': line.home_itt if line.home_itt else 22.5
            }
            vegas_map[line.away_team] = {
                'game_total': line.total if line.total else 45.0,
                'itt': line.away_itt if line.away_itt else 22.5
            }
        
        # Map Vegas data to players
        df['game_total'] = df['team'].map(lambda t: vegas_map.get(t, {}).get('game_total', 45.0))
        df['team_itt'] = df['team'].map(lambda t: vegas_map.get(t, {}).get('itt', 22.5))
        
        # Calculate matchup score using both game total and ITT
        # Game total indicates shootout potential (50+ = ceiling game)
        # ITT indicates team-specific scoring expectation
        
        # Normalize game total (range typically 38-56)
        game_total_norm = (df['game_total'] - 38) / (56 - 38)
        game_total_norm = game_total_norm.clip(0, 1)
        
        # Normalize ITT by position (different scoring expectations)
        itt_norm = min_max_scale_by_position(df, 'team_itt')
        
        # Combined matchup score: 60% game total, 40% ITT
        # High total = ceiling game for both teams
        # High ITT = this specific team expected to score
        matchup_raw = (game_total_norm * 0.6) + (itt_norm * 0.4)
        df['matchup_score'] = matchup_raw * weight
        
        return df
        
    except Exception as e:
        # Fallback on error
        print(f"Warning: Could not load Vegas data for matchup score: {e}")
        matchup_norm = min_max_scale_by_position(df, 'projection')
        df['matchup_score'] = matchup_norm * weight * 0.5
        df['game_total'] = 0
        df['team_itt'] = 0
        return df


def calculate_leverage_score(df: pd.DataFrame, weight: float) -> pd.DataFrame:
    """
    Calculate LEVERAGE score component (ceiling + low ownership = tournament gold).
    
    Based on Week 6 winning analysis:
    - De'Von Achane: 34.0 pts at 4.7% own = massive leverage
    - George Pickens: 34.8 pts at 10.6% own = ceiling at reasonable own
    - Puka Nacua: 4.8 pts at 30.8% own = chalk bust
    
    Formula: (Ceiling Ratio) × (Ownership Discount) × (Matchup Quality)
    
    Where:
    - Ceiling Ratio = season_ceiling / projection (upside factor)
    - Ownership Discount = 1 / (ownership% / 100) (contrarian boost)
    - Matchup Quality = game_total normalization (ceiling game indicator)
    
    Args:
        df: Player DataFrame with season_ceiling, projection, ownership, game_total
        weight: Weight for this component (default 0.15 balanced, 0.25 GPP)
    
    Returns:
        DataFrame with 'leverage_score' column
    """
    # Calculate ceiling ratio (how much upside vs projection)
    df['ceiling_ratio'] = df['season_ceiling'] / df['projection'].replace(0, 1)
    df['ceiling_ratio'] = df['ceiling_ratio'].clip(upper=3.0)  # Cap at 3x to avoid outliers
    
    # Normalize ceiling ratio by position (different expectations)
    ceiling_norm = min_max_scale_by_position(df, 'ceiling_ratio')
    
    # Calculate ownership discount using SWEET SPOT approach
    # Philosophy: "Smart contrarian, not cute contrarian"
    # Rewards 8-15% owned (optimal leverage zone), doesn't penalize good chalk
    # 
    # Ownership Tiers:
    #   < 8%:  2.5x - Ultra-contrarian (risky dart throws, slight penalty)
    #   8-15%: 3.0x - OPTIMAL leverage zone (best risk/reward)
    #   15-25%: 2.0x - Popular but still good leverage
    #   25%+:  1.0x - Chalk plays (neutral, no penalty or bonus)
    df['ownership_pct'] = df['ownership'].clip(lower=1.0)  # Min 1% to avoid divide by zero
    
    def sweet_spot_discount(own):
        """Calculate ownership discount with sweet spot bias"""
        if 8.0 <= own <= 15.0:
            return 3.0  # Optimal leverage zone
        elif own < 8.0:
            return 2.5  # Ultra-contrarian (slightly discouraged)
        elif own <= 25.0:
            return 2.0  # Popular but acceptable
        else:
            return 1.0  # Chalk (neutral)
    
    df['own_discount'] = df['ownership_pct'].apply(sweet_spot_discount)
    
    # Normalize ownership discount
    own_norm = (df['own_discount'] - df['own_discount'].min()) / (df['own_discount'].max() - df['own_discount'].min() + 0.001)
    
    # Use matchup quality (game total) as multiplier
    # High game totals (50+) indicate ceiling environments
    if 'game_total' in df.columns:
        game_total_norm = (df['game_total'] - 38) / (56 - 38)
        game_total_norm = game_total_norm.clip(0, 1)
    else:
        game_total_norm = 0.5  # Neutral if no data
    
    # Combined leverage score
    # 40% ceiling ratio, 40% ownership discount, 20% game total
    leverage_raw = (ceiling_norm * 0.4) + (own_norm * 0.4) + (game_total_norm * 0.2)
    
    df['leverage_score'] = leverage_raw * weight
    
    # Apply TE position penalty (50% reduction)
    # TEs are TD-dependent, low-volume, and game-script-sensitive
    # They need a higher discount than RB/WR to reflect true reliability
    # Based on Week 6 + double TE analysis:
    # - TE leverage wins are 0.5x less frequent than RB/WR
    # - 9/11 lineups had double TE (massive over-leverage)
    # - Top 100 Week 6: <10% had double TE
    # - Increased penalty allows legitimate TE2 plays while preventing over-use
    if 'position' in df.columns:
        te_mask = df['position'] == 'TE'
        df.loc[te_mask, 'leverage_score'] *= 0.50  # 50% penalty (was 30%)
    
    return df


def calculate_anti_chalk_penalty(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply ANTI-CHALK penalty to high-owned players in bad matchups.
    
    Based on Week 6 busts:
    - Puka Nacua: 30.8% own, 4.8 pts in low-scoring game = BUST
    - Emeka Egbuka: 26.1% own, 4.4 pts = BUST
    - Javonte Williams: 25.7% own, 8.4 pts in bad offense = BUST
    
    Criteria for chalk penalty:
    - Ownership > 25%
    - Game total < 45 (low-scoring environment)
    
    Penalty: -15 to -20 Smart Value points
    
    Args:
        df: Player DataFrame with ownership, game_total columns
    
    Returns:
        DataFrame with 'chalk_penalty' column (negative values)
    """
    df['chalk_penalty'] = 0.0
    
    if 'ownership' not in df.columns or 'game_total' not in df.columns:
        return df
    
    # Identify chalk players in bad spots
    high_own = df['ownership'] > 25
    bad_matchup = df['game_total'] < 45
    
    chalk_trap = high_own & bad_matchup
    
    # Progressive penalty based on ownership level
    # 25-30% own = -15 pts, 30-40% own = -20 pts, 40%+ own = -25 pts
    penalty_amounts = []
    for idx, row in df.iterrows():
        if chalk_trap[idx]:
            own = row['ownership']
            if own >= 40:
                penalty_amounts.append(-25)
            elif own >= 30:
                penalty_amounts.append(-20)
            else:
                penalty_amounts.append(-15)
        else:
            penalty_amounts.append(0)
    
    df['chalk_penalty'] = penalty_amounts
    
    return df


def calculate_smart_value(df: pd.DataFrame, profile: str = 'balanced', custom_weights: Optional[Dict[str, float]] = None, position_weights: Optional[Dict[str, Dict[str, float]]] = None, sub_weights: Optional[Dict[str, float]] = None, week: int = 6) -> pd.DataFrame:
    """
    Calculate Smart Value Score using multi-factor weighted formula with optional position-specific overrides and sub-weight customization.
    
    Formula: Smart Value = BASE + OPPORTUNITY + TRENDS + RISK + MATCHUP + LEVERAGE - CHALK_PENALTY
    
    NEW (Week 6 Analysis):
    - LEVERAGE: Rewards ceiling potential + low ownership (De'Von Achane effect)
    - CHALK_PENALTY: Punishes high ownership in bad matchups (Puka Nacua trap)
    
    Args:
        df: Player DataFrame with required columns (projection, salary, position, etc.)
        profile: Weight profile to use ('balanced', 'cash', 'gpp', 'custom')
        custom_weights: Optional dict of custom weights. If provided, overrides profile.
                       Should contain: 'base', 'opportunity', 'trends', 'risk', 'matchup', 'leverage'
        position_weights: Optional dict mapping position to weight overrides.
                         Example: {'QB': {'base': 0.50, 'opportunity': 0.20}, 'RB': {'opportunity': 0.45}}
        sub_weights: Optional dict of sub-factor weights for fine-grained control.
                    Example: {'opp_target_share': 0.60, 'opp_snap_pct': 0.30, ...}
        week: NFL week number for Vegas lines lookup (default: 6)
    
    Returns:
        DataFrame with added columns:
        - smart_value: Final score (0-100 scale)
        - smart_value_tooltip: Breakdown explanation
        - leverage_score: Tournament leverage component
        - chalk_penalty: Anti-chalk adjustment
        - Individual component scores for debugging
    """
    # Use custom weights if provided, otherwise use profile
    if custom_weights is not None:
        weights = custom_weights
        profile = 'custom'
    else:
        if profile not in WEIGHT_PROFILES:
            raise ValueError(f"Profile '{profile}' not found. Available: {list(WEIGHT_PROFILES.keys())}")
        weights = WEIGHT_PROFILES[profile]
    
    df = df.copy()
    
    # If position-specific weights provided, calculate per position
    if position_weights and 'position' in df.columns:
        # Initialize score columns
        df['base_score'] = 0.0
        df['opp_score'] = 0.0
        df['trends_score'] = 0.0
        df['risk_score'] = 0.0
        df['matchup_score'] = 0.0
        df['leverage_score'] = 0.0
        
        for position in df['position'].unique():
            pos_mask = df['position'] == position
            pos_df = df[pos_mask].copy()
            
            # Use position-specific weights if available, otherwise use global weights
            if position in position_weights:
                pos_weights = weights.copy()
                pos_weights.update(position_weights[position])
            else:
                pos_weights = weights
            
            # Calculate scores for this position
            pos_df = calculate_base_score(pos_df, pos_weights['base'])
            pos_df = calculate_opportunity_score(pos_df, pos_weights['opportunity'], sub_weights)
            pos_df = calculate_trends_score(pos_df, pos_weights['trends'], sub_weights)
            pos_df = calculate_risk_score(pos_df, pos_weights['risk'], sub_weights)
            pos_df = calculate_matchup_score(pos_df, pos_weights['matchup'], week)
            pos_df = calculate_leverage_score(pos_df, pos_weights.get('leverage', 0.15))
            
            # Update the main dataframe for this position
            for col in ['base_score', 'opp_score', 'trends_score', 'risk_score', 'matchup_score', 'leverage_score']:
                df.loc[pos_mask, col] = pos_df[col]
    else:
        # Calculate uniformly across all positions
        df = calculate_base_score(df, weights['base'])
        df = calculate_opportunity_score(df, weights['opportunity'], sub_weights)
        df = calculate_trends_score(df, weights['trends'], sub_weights)
        df = calculate_risk_score(df, weights['risk'], sub_weights)
        df = calculate_matchup_score(df, weights['matchup'], week)
        df = calculate_leverage_score(df, weights.get('leverage', 0.15))
    
    # Apply anti-chalk penalty (independent of position)
    df = calculate_anti_chalk_penalty(df)
    
    # Sum all components (raw score)
    df['smart_value_raw'] = (
        df['base_score'] +
        df['opp_score'] +
        df['trends_score'] +
        df['risk_score'] +
        df['matchup_score'] +
        df['leverage_score'] +
        df['chalk_penalty']  # Negative values reduce score
    )
    
    # Scale to 0-100 for intuitive interpretation
    # Use POSITION-SPECIFIC min-max scaling so each position has its own 0-100 range
    # This prevents QBs from being compressed by RB/WR dominance
    # Rationale: You're comparing QBs to QBs, RBs to RBs (different roster slots)
    
    if 'position' in df.columns:
        # Store position-specific min/max for tooltip calculation
        df['_pos_min'] = df.groupby('position')['smart_value_raw'].transform('min')
        df['_pos_max'] = df.groupby('position')['smart_value_raw'].transform('max')
        
        # Calculate position-specific 0-100 scores
        def scale_position_group(group):
            group_min = group['smart_value_raw'].min()
            group_max = group['smart_value_raw'].max()
            
            if group_max > group_min:
                return ((group['smart_value_raw'] - group_min) / (group_max - group_min)) * 100
            else:
                # If all scores in position are the same, set to 50
                return 50.0
        
        df['smart_value'] = df.groupby('position', group_keys=False).apply(scale_position_group).reset_index(drop=True)
    else:
        # Fallback: global scaling if no position column
        df['_pos_min'] = df['smart_value_raw'].min()
        df['_pos_max'] = df['smart_value_raw'].max()
        
        if df['_pos_max'].iloc[0] > df['_pos_min'].iloc[0]:
            df['smart_value'] = ((df['smart_value_raw'] - df['_pos_min']) / (df['_pos_max'] - df['_pos_min'])) * 100
        else:
            df['smart_value'] = 50.0
    
    # Build tooltip breakdown
    def build_tooltip(row):
        # Show component contributions as percentages of the final 0-100 score
        # Scale the raw component scores proportionally using position-specific min/max
        pos_min = row['_pos_min']
        pos_max = row['_pos_max']
        
        if pos_max > pos_min:
            scale_factor = 100 / (pos_max - pos_min)
            base_val = row['base_score'] * scale_factor
            opp_val = row['opp_score'] * scale_factor
            trend_val = row['trends_score'] * scale_factor
            risk_val = row['risk_score'] * scale_factor
            match_val = row['matchup_score'] * scale_factor
            leverage_val = row['leverage_score'] * scale_factor
            chalk_penalty_val = row['chalk_penalty'] * scale_factor
        else:
            base_val = opp_val = trend_val = risk_val = match_val = leverage_val = chalk_penalty_val = 0
        
        tooltip = (
            f"Smart Value: {row['smart_value']:.1f}/100\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Component Breakdown:\n\n"
            f"💰 Base Value: +{base_val:.1f} ({int(weights['base']*100)}% weight)\n"
            f"  └─ Projection per $1K: {row['base_raw']:.2f}\n\n"
            f"📊 Opportunity: +{opp_val:.1f} ({int(weights['opportunity']*100)}% weight)\n"
            f"  └─ Volume/Usage indicators\n\n"
            f"📈 Trends: {trend_val:+.1f} ({int(weights['trends']*100)}% weight)\n"
            f"  └─ Momentum, Role Trend, Recent FP\n\n"
            f"⚠️ Risk Adjust: {risk_val:+.1f} ({int(weights['risk']*100)}% weight)\n"
            f"  └─ Regression, Variance, Consistency\n\n"
            f"🎯 Matchup: {match_val:+.1f} ({int(weights['matchup']*100)}% weight)\n"
            f"  └─ Game Total: {row.get('game_total', 0):.1f}, ITT: {row.get('team_itt', 0):.1f}\n\n"
            f"💎 Leverage: {leverage_val:+.1f} ({int(weights.get('leverage', 0)*100)}% weight)\n"
            f"  └─ Ceiling: {row.get('season_ceiling', 0):.1f}, Own: {row.get('ownership', 0):.1f}%\n"
        )
        
        # Add chalk penalty if applicable
        if chalk_penalty_val < 0:
            tooltip += (
                f"\n❌ Chalk Penalty: {chalk_penalty_val:.1f}\n"
                f"  └─ High own ({row.get('ownership', 0):.1f}%) + Bad matchup\n"
            )
        
        tooltip += (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Final Score: {row['smart_value']:.1f}/100\n\n"
            f"💡 Score is relative to other {row.get('position', 'players')}s\n"
            f"   100 = Best {row.get('position', 'player')} available\n"
            f"   0 = Worst {row.get('position', 'player')} available"
        )
        return tooltip
    
    df['smart_value_tooltip'] = df.apply(build_tooltip, axis=1)
    
    # Clean up helper columns
    df = df.drop(columns=['_pos_min', '_pos_max'], errors='ignore')
    
    return df


def get_available_profiles() -> Dict[str, Dict[str, float]]:
    """
    Get all available weight profiles.
    
    Returns:
        Dictionary of profile names to weight configurations
    """
    return WEIGHT_PROFILES.copy()

