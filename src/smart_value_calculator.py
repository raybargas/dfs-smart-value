"""
Smart Value Calculator

Calculates a sophisticated, multi-factor value score that goes beyond simple projection/salary.
Incorporates opportunity metrics, trends, risk factors, and matchup quality.

Formula: Smart Value = BASE (40%) + OPPORTUNITY (30%) + TRENDS (15%) + RISK (10%) + MATCHUP (5%)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional


# Weight Profiles
WEIGHT_PROFILES = {
    'balanced': {
        'base': 0.40,
        'opportunity': 0.30,
        'trends': 0.15,
        'risk': 0.10,
        'matchup': 0.05
    },
    'cash': {
        'base': 0.45,
        'opportunity': 0.25,
        'trends': 0.10,
        'risk': 0.15,
        'matchup': 0.05
    },
    'gpp': {
        'base': 0.35,
        'opportunity': 0.25,
        'trends': 0.20,
        'risk': 0.10,
        'matchup': 0.10
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
    Calculate BASE score component (projection per $1K).
    
    Args:
        df: Player DataFrame
        weight: Weight for this component (default 0.40)
    
    Returns:
        DataFrame with 'base_raw' and 'base_norm' columns
    """
    # Calculate raw value (pts per $1K)
    df['base_raw'] = df['projection'] / (df['salary'] / 1000)
    
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


def calculate_matchup_score(df: pd.DataFrame, weight: float) -> pd.DataFrame:
    """
    Calculate MATCHUP score component (game environment quality).
    
    Currently uses projection as a proxy since Vegas game totals need to be joined.
    Future enhancement: Join Vegas lines by matchup to get actual game totals.
    
    Args:
        df: Player DataFrame
        weight: Weight for this component (default 0.05)
    
    Returns:
        DataFrame with 'matchup_score' column
    """
    # For now, use a small bonus for high projections (proxy for game script)
    # This is a placeholder until we integrate actual Vegas game totals
    matchup_norm = min_max_scale_by_position(df, 'projection')
    df['matchup_score'] = matchup_norm * weight * 0.5  # Reduce weight since it's a proxy
    
    return df


def calculate_smart_value(df: pd.DataFrame, profile: str = 'balanced', custom_weights: Optional[Dict[str, float]] = None, position_weights: Optional[Dict[str, Dict[str, float]]] = None, sub_weights: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """
    Calculate Smart Value Score using multi-factor weighted formula with optional position-specific overrides and sub-weight customization.
    
    Formula: Smart Value = BASE + OPPORTUNITY + TRENDS + RISK + MATCHUP
    
    Args:
        df: Player DataFrame with required columns (projection, salary, position, etc.)
        profile: Weight profile to use ('balanced', 'cash', 'gpp', 'custom')
        custom_weights: Optional dict of custom weights. If provided, overrides profile.
                       Should contain: 'base', 'opportunity', 'trends', 'risk', 'matchup'
        position_weights: Optional dict mapping position to weight overrides.
                         Example: {'QB': {'base': 0.50, 'opportunity': 0.20}, 'RB': {'opportunity': 0.45}}
        sub_weights: Optional dict of sub-factor weights for fine-grained control.
                    Example: {'opp_target_share': 0.60, 'opp_snap_pct': 0.30, ...}
    
    Returns:
        DataFrame with added columns:
        - smart_value: Final score
        - smart_value_tooltip: Breakdown explanation
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
            pos_df = calculate_matchup_score(pos_df, pos_weights['matchup'])
            
            # Update the main dataframe for this position
            for col in ['base_score', 'opp_score', 'trends_score', 'risk_score', 'matchup_score']:
                df.loc[pos_mask, col] = pos_df[col]
    else:
        # Calculate uniformly across all positions
        df = calculate_base_score(df, weights['base'])
        df = calculate_opportunity_score(df, weights['opportunity'], sub_weights)
        df = calculate_trends_score(df, weights['trends'], sub_weights)
        df = calculate_risk_score(df, weights['risk'], sub_weights)
        df = calculate_matchup_score(df, weights['matchup'])
    
    # Sum all components (raw score)
    df['smart_value_raw'] = (
        df['base_score'] +
        df['opp_score'] +
        df['trends_score'] +
        df['risk_score'] +
        df['matchup_score']
    )
    
    # Scale to 0-100 for intuitive interpretation
    # Use min-max scaling across all positions so scores are comparable
    smart_min = df['smart_value_raw'].min()
    smart_max = df['smart_value_raw'].max()
    
    if smart_max > smart_min:
        df['smart_value'] = ((df['smart_value_raw'] - smart_min) / (smart_max - smart_min)) * 100
    else:
        # If all scores are the same, set to 50
        df['smart_value'] = 50.0
    
    # Build tooltip breakdown
    def build_tooltip(row):
        # Show component contributions as percentages of the final 0-100 score
        # Scale the raw component scores proportionally
        if smart_max > smart_min:
            scale_factor = 100 / (smart_max - smart_min)
            base_val = row['base_score'] * scale_factor
            opp_val = row['opp_score'] * scale_factor
            trend_val = row['trends_score'] * scale_factor
            risk_val = row['risk_score'] * scale_factor
            match_val = row['matchup_score'] * scale_factor
        else:
            base_val = opp_val = trend_val = risk_val = match_val = 0
        
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
            f"  └─ Game environment quality\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Final Score: {row['smart_value']:.1f}/100\n\n"
            f"💡 0=Worst, 100=Best in this player pool"
        )
        return tooltip
    
    df['smart_value_tooltip'] = df.apply(build_tooltip, axis=1)
    
    return df


def get_available_profiles() -> Dict[str, Dict[str, float]]:
    """
    Get all available weight profiles.
    
    Returns:
        Dictionary of profile names to weight configurations
    """
    return WEIGHT_PROFILES.copy()

