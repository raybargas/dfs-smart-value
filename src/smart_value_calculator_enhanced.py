"""
Smart Value Calculator - ENHANCED with Tier 1 Advanced Metrics

Part of DFS Advanced Stats Migration (Phase 2: Tier 1 Metrics)
Enhances the opportunity score with TPRR, YPRR, RTE%, YACO/ATT, Success Rate

This is a copy of smart_value_calculator.py with enhancements for Tier 1 metrics.
To use, rename this file to smart_value_calculator.py or update imports.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Copy all the existing constants and helper functions from original
from .smart_value_calculator import (
    TEAM_ABBREV_TO_FULL,
    PROJECTION_GATES,
    WEIGHT_PROFILES,
    get_ceiling_boost_multiplier,
    min_max_scale_by_position,
    calculate_base_score,
    calculate_opportunity_score,
    calculate_trends_score,
    calculate_risk_score,
    calculate_matchup_score,
    calculate_leverage_score,
    calculate_regression_score,
    get_available_profiles
)


def calculate_anti_chalk_penalty(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate anti-chalk penalty to reduce ownership of highly owned players.
    
    Args:
        df: Player DataFrame with 'ownership' column
        
    Returns:
        DataFrame with 'chalk_penalty' column (negative values)
    """
    df['chalk_penalty'] = 0.0
    
    if 'ownership' in df.columns:
        # Penalty increases with ownership above 20%
        high_ownership = df['ownership'] > 20.0
        if high_ownership.any():
            penalty = (df['ownership'] - 20.0) / 80.0  # Scale 20-100% to 0-1
            penalty = penalty.clip(0, 1)  # Cap at 1
            df.loc[high_ownership, 'chalk_penalty'] = -penalty * 5.0  # Max -5 penalty
    
    return df


def calculate_base_score_enhanced(df: pd.DataFrame, weight: float) -> pd.DataFrame:
    """
    Calculate BASE score component - ENHANCED with YACO/ATT for RBs.

    PHASE 2 TIER 1 ENHANCEMENT:
    - RBs: Use YACO/ATT to validate/adjust base value (talent vs O-line)
    - QBs: Will use CPOE in Phase 3 (Tier 2)

    Args:
        df: Player DataFrame (must include 'season_ceiling' column)
        weight: Weight for this component (default 0.15)

    Returns:
        DataFrame with 'base_raw' and 'base_norm' columns
    """
    # Calculate raw value (pts per $1K)
    df['value_ratio'] = df['projection'] / (df['salary'] / 1000)
    df['base_raw'] = df['value_ratio'].copy()

    # Value Ratio Penalty (trap chalk defense)
    def get_value_penalty(value_ratio):
        if value_ratio >= 3.0:
            return 1.0   # No penalty - good value
        elif value_ratio >= 2.5:
            return 0.85  # 15% penalty - mediocre value
        else:
            return 0.70  # 30% penalty - poor value

    df['value_penalty'] = df['value_ratio'].apply(get_value_penalty)
    df['base_raw'] = df['base_raw'] * df['value_penalty']

    # PHASE 2 TIER 1: RB Enhancement with YACO/ATT
    if 'adv_yaco_att' in df.columns:
        rb_mask = df['position'] == 'RB'
        # Higher YACO = higher talent = boost base value
        # YACO typically 0-5, normalize to multiplier 0.9-1.1
        yaco_mult = 0.9 + (df.loc[rb_mask, 'adv_yaco_att'].fillna(2.5) / 25)
        yaco_mult = yaco_mult.clip(0.9, 1.1)  # Cap the multiplier
        df.loc[rb_mask, 'base_raw'] *= yaco_mult
        logger.debug(f"Applied YACO/ATT adjustment to {rb_mask.sum()} RBs")

    # Add ceiling boost for explosion potential
    if 'season_ceiling' in df.columns:
        df['ceiling_ratio'] = df['season_ceiling'] / df['projection'].replace(0, 1)
        df['ceiling_ratio'] = df['ceiling_ratio'].fillna(1.5)

        # Calculate projection-based multiplier
        df['ceiling_multiplier'] = df.apply(
            lambda row: get_ceiling_boost_multiplier(row['position'], row['projection']),
            axis=1
        )

        # Ceiling boost: 0-50% boost for high ceiling/projection ratios
        df['ceiling_boost'] = np.clip((df['ceiling_ratio'] - 1.0) / 2.0, 0, 0.5) * df['ceiling_multiplier']

        # Apply boost
        df['base_raw'] = df['base_raw'] * (1 + df['ceiling_boost'])

    # Normalize by position
    df['base_norm'] = min_max_scale_by_position(df, 'base_raw')

    # Apply weight
    df['base_score'] = df['base_norm'] * weight

    return df


def calculate_opportunity_score_enhanced(df: pd.DataFrame, weight: float, sub_weights: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """
    Calculate OPPORTUNITY score - ENHANCED with Tier 1 Advanced Metrics.

    PHASE 2 TIER 1 ENHANCEMENTS:
    - WR/TE: Use TPRR (if available) instead of season_tgt
    - WR/TE: Use YPRR for efficiency component
    - WR/TE: Use RTE% for snap quality component
    - RB: Use Success Rate for floor component

    Args:
        df: Player DataFrame
        weight: Weight for this component (default 0.30)
        sub_weights: Optional dict with keys for fine-grained control

    Returns:
        DataFrame with 'opp_score' column
    """
    # Default sub-weights if not provided
    if sub_weights is None:
        sub_weights = {
            'opp_target_share': 0.35,    # Reduced from 0.60 to make room for efficiency
            'opp_efficiency': 0.30,      # NEW: YPRR-based efficiency
            'opp_snap_quality': 0.25,    # Enhanced with RTE%
            'opp_rz_targets': 0.10       # Keep red zone component
        }

    # Extract sub-weights
    tgt_weight = sub_weights.get('opp_target_share', 0.35)
    eff_weight = sub_weights.get('opp_efficiency', 0.30)
    snap_weight = sub_weights.get('opp_snap_quality', 0.25)
    rz_weight = sub_weights.get('opp_rz_targets', 0.10)

    df['opp_score'] = 0.0

    # Track metrics used for logging
    metrics_used = {'WR': [], 'TE': [], 'RB': [], 'QB': []}

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
            # RB: Enhanced with Success Rate for floor
            opp_components = 0.0

            # Primary: Snap % (workhouse indicator)
            if 'season_snap' in df.columns and pos_df['season_snap'].notna().any():
                snap_pct = pos_df['season_snap'] / 100
                opp_components += snap_pct * 0.6  # 60% weight on snaps
                metrics_used['RB'].append('season_snap')

            # PHASE 2 TIER 1: Success Rate for floor component
            if 'adv_success_rate' in df.columns and pos_df['adv_success_rate'].notna().any():
                # Normalize success rate (typically 30-60%)
                success_norm = (pos_df['adv_success_rate'] - 30) / 30
                success_norm = success_norm.clip(0, 1)
                opp_components += success_norm * 0.4  # 40% weight on success rate
                metrics_used['RB'].append('adv_success_rate')
            else:
                # Fallback: use projection as proxy for remaining weight
                proj_norm = pos_df['projection'] / pos_df['projection'].max() if pos_df['projection'].max() > 0 else 0.5
                opp_components += proj_norm * 0.4

            df.loc[pos_mask, 'opp_score'] = opp_components * weight

        elif position in ['WR', 'TE']:
            # WR/TE: ENHANCED with TPRR, YPRR, RTE%
            total_opp = 0.0

            # PHASE 2 TIER 1: TPRR for target share (if available)
            if 'adv_tprr' in df.columns and pos_df['adv_tprr'].notna().any():
                # TPRR is 0-1 scale (0-100% of routes)
                tprr_norm = pos_df['adv_tprr']
                # Normalize within position for relative comparison
                tprr_max = pos_df['adv_tprr'].max()
                if tprr_max > 0:
                    tprr_norm = pos_df['adv_tprr'] / tprr_max
                total_opp += tprr_norm * tgt_weight
                metrics_used[position].append('adv_tprr')
            elif 'season_tgt' in df.columns and pos_df['season_tgt'].notna().any():
                # Fallback to original target share
                tgt_max = pos_df['season_tgt'].max()
                if tgt_max > 0:
                    tgt_norm = pos_df['season_tgt'] / tgt_max
                    total_opp += tgt_norm * tgt_weight
                metrics_used[position].append('season_tgt')

            # PHASE 2 TIER 1: YPRR for efficiency component
            if 'adv_yprr' in df.columns and pos_df['adv_yprr'].notna().any():
                # YPRR typically 0-3 for most players, elite is 2.5+
                yprr_norm = pos_df['adv_yprr'] / 3.0  # Normalize to 0-1
                yprr_norm = yprr_norm.clip(0, 1)
                total_opp += yprr_norm * eff_weight
                metrics_used[position].append('adv_yprr')
            else:
                # Fallback: use FP/G as efficiency proxy
                if 'season_fpg' in df.columns and pos_df['season_fpg'].notna().any():
                    fpg_max = pos_df['season_fpg'].max()
                    if fpg_max > 0:
                        fpg_norm = pos_df['season_fpg'] / fpg_max
                        total_opp += fpg_norm * eff_weight
                    metrics_used[position].append('season_fpg')

            # PHASE 2 TIER 1: RTE% for snap quality
            if 'adv_rte_pct' in df.columns and pos_df['adv_rte_pct'].notna().any():
                # RTE% is already 0-100 scale
                rte_norm = pos_df['adv_rte_pct'] / 100
                total_opp += rte_norm * snap_weight
                metrics_used[position].append('adv_rte_pct')
            elif 'season_snap' in df.columns and pos_df['season_snap'].notna().any():
                # Fallback to regular snap %
                snap_norm = pos_df['season_snap'] / 100
                total_opp += snap_norm * snap_weight
                metrics_used[position].append('season_snap')

            # Red Zone Targets component (unchanged)
            if 'season_eztgt' in df.columns and pos_df['season_eztgt'].notna().any():
                rz_max = pos_df['season_eztgt'].max()
                if rz_max > 0:
                    rz_norm = pos_df['season_eztgt'] / rz_max
                    total_opp += rz_norm * rz_weight
                metrics_used[position].append('season_eztgt')

            # If no opportunity data available, use projection proxy
            if isinstance(total_opp, pd.Series) and total_opp.sum() == 0:
                total_opp = pos_df['projection'] / pos_df['projection'].max() if pos_df['projection'].max() > 0 else 0.5
            elif not isinstance(total_opp, pd.Series) and total_opp == 0:
                total_opp = pos_df['projection'] / pos_df['projection'].max() if pos_df['projection'].max() > 0 else 0.5

            df.loc[pos_mask, 'opp_score'] = total_opp * weight

    # Log which advanced metrics were used
    for position, metrics in metrics_used.items():
        if metrics:
            advanced = [m for m in metrics if m.startswith('adv_')]
            if advanced:
                logger.info(f"{position} opportunity score using advanced metrics: {advanced}")

    return df


def calculate_risk_score_enhanced(df: pd.DataFrame, weight: float, sub_weights: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """
    Calculate RISK score - ENHANCED with Success Rate for RB floor.

    PHASE 2 TIER 1 ENHANCEMENT:
    - RBs with high Success Rate get a floor bonus (reduces risk)

    Args:
        df: Player DataFrame
        weight: Weight for this component (default 0.05)
        sub_weights: Optional dict with keys 'risk_variance', 'risk_consistency', 'risk_floor'

    Returns:
        DataFrame with 'risk_score' column
    """
    # Default sub-weights if not provided
    if sub_weights is None:
        sub_weights = {
            'risk_variance': 0.40,      # Reduced to make room for floor
            'risk_consistency': 0.30,   # Reduced to make room for floor
            'risk_floor': 0.30          # NEW: Success rate based floor
        }

    # Extract sub-weights
    var_weight = sub_weights.get('risk_variance', 0.40)
    cons_weight = sub_weights.get('risk_consistency', 0.30)
    floor_weight = sub_weights.get('risk_floor', 0.30)

    df['risk_score'] = 0.0

    # XFP Variance bonus/penalty (if available)
    if 'season_var' in df.columns:
        # Negative variance (unlucky) = +0.3, Positive (lucky) = -0.2
        variance_adjustment = df['season_var'].apply(
            lambda x: 0.3 if x < -2 else (-0.2 if x > 2 else 0) if pd.notna(x) else 0
        )
        df['risk_score'] += variance_adjustment * (weight * var_weight)

    # Consistency bonus (if available)
    if 'season_cons' in df.columns:
        # Low consistency (<5) = +0.2, High (>10) = -0.2
        consistency_adjustment = df['season_cons'].apply(
            lambda x: 0.2 if x < 5 else (-0.2 if x > 10 else 0) if pd.notna(x) else 0
        )
        df['risk_score'] += consistency_adjustment * (weight * cons_weight)

    # PHASE 2 TIER 1: Success Rate floor bonus for RBs
    if 'adv_success_rate' in df.columns:
        rb_mask = df['position'] == 'RB'
        # High success rate (>50%) = +0.3 floor bonus
        # Low success rate (<35%) = -0.2 floor penalty
        success_adjustment = df.loc[rb_mask, 'adv_success_rate'].apply(
            lambda x: 0.3 if x > 50 else (-0.2 if x < 35 else 0) if pd.notna(x) else 0
        )
        df.loc[rb_mask, 'risk_score'] += success_adjustment * (weight * floor_weight)

        logger.debug(f"Applied Success Rate floor adjustment to {rb_mask.sum()} RBs")

    return df


def calculate_smart_value_enhanced(
    df: pd.DataFrame,
    profile: str = 'balanced',
    custom_weights: Optional[Dict[str, float]] = None,
    position_weights: Optional[Dict[str, Dict[str, float]]] = None,
    sub_weights: Optional[Dict[str, float]] = None,
    week: int = 6,
    use_advanced_metrics: bool = True
) -> pd.DataFrame:
    """
    Calculate Smart Value Score - ENHANCED with Tier 1 Advanced Metrics.

    PHASE 2 TIER 1 ENHANCEMENTS:
    - OPPORTUNITY: Uses TPRR, YPRR, RTE% for WR/TE; Success Rate for RB
    - BASE: Uses YACO/ATT for RB talent validation
    - RISK: Uses Success Rate for RB floor component

    Additional parameter:
        use_advanced_metrics: If False, falls back to original logic

    All other parameters same as original calculate_smart_value().
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

    # Log whether we're using advanced metrics
    advanced_columns = [col for col in df.columns if col.startswith('adv_')]
    if advanced_columns and use_advanced_metrics:
        logger.info(f"Smart Value using {len(advanced_columns)} advanced metrics: {advanced_columns[:5]}...")
    else:
        logger.info("Smart Value using original metrics only")

    # Choose enhanced or original functions based on flag
    if use_advanced_metrics and advanced_columns:
        base_func = calculate_base_score_enhanced
        opp_func = calculate_opportunity_score_enhanced
        risk_func = calculate_risk_score_enhanced
    else:
        # Use original functions (already imported)
        base_func = calculate_base_score
        opp_func = calculate_opportunity_score
        risk_func = calculate_risk_score

    # If position-specific weights provided, calculate per position
    if position_weights and 'position' in df.columns:
        # Initialize score columns
        df['base_score'] = 0.0
        df['opp_score'] = 0.0
        df['trends_score'] = 0.0
        df['risk_score'] = 0.0
        df['matchup_score'] = 0.0
        df['leverage_score'] = 0.0
        df['regression_score'] = 0.0

        for position in df['position'].unique():
            pos_mask = df['position'] == position
            pos_df = df[pos_mask].copy()

            # Use position-specific weights if available
            if position in position_weights:
                pos_weights = weights.copy()
                pos_weights.update(position_weights[position])
            else:
                pos_weights = weights

            # Calculate scores for this position
            pos_df = base_func(pos_df, pos_weights['base'])
            pos_df = opp_func(pos_df, pos_weights['opportunity'], sub_weights)
            pos_df = calculate_trends_score(pos_df, pos_weights['trends'], sub_weights)
            pos_df = risk_func(pos_df, pos_weights['risk'])
            pos_df = calculate_matchup_score(pos_df, pos_weights['matchup'], None, week)
            pos_df = calculate_leverage_score(pos_df, pos_weights.get('leverage', 0.15))
            pos_df = calculate_regression_score(pos_df, pos_weights.get('regression', 0.05))

            # Update the main dataframe for this position
            for col in ['base_score', 'opp_score', 'trends_score', 'risk_score', 'matchup_score', 'leverage_score', 'regression_score']:
                df.loc[pos_mask, col] = pos_df[col]
    else:
        # Calculate uniformly across all positions
        df = base_func(df, weights['base'])
        df = opp_func(df, weights['opportunity'], sub_weights)
        df = calculate_trends_score(df, weights['trends'], sub_weights)
        df = risk_func(df, weights['risk'])
        df = calculate_matchup_score(df, weights['matchup'], None, week)
        df = calculate_leverage_score(df, weights.get('leverage', 0.15))
        df = calculate_regression_score(df, weights.get('regression', 0.05))

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
        df['regression_score'] +
        df['chalk_penalty']  # Negative values reduce score
    )

    # Scale to 0-100 (rest of the logic same as original)
    if 'position' in df.columns:
        # Position-specific scaling
        df['_pos_min'] = df.groupby('position')['smart_value_raw'].transform('min')
        df['_pos_max'] = df.groupby('position')['smart_value_raw'].transform('max')

        def scale_position_transform(group):
            group_min = group.min()
            group_max = group.max()

            if group_max > group_min:
                return ((group - group_min) / (group_max - group_min)) * 100
            else:
                return pd.Series([50.0] * len(group), index=group.index)

        df['smart_value'] = df.groupby('position', group_keys=False)['smart_value_raw'].transform(scale_position_transform)
    else:
        # Global scaling
        df['_pos_min'] = df['smart_value_raw'].min()
        df['_pos_max'] = df['smart_value_raw'].max()

        if df['_pos_max'].iloc[0] > df['_pos_min'].iloc[0]:
            df['smart_value'] = ((df['smart_value_raw'] - df['_pos_min']) / (df['_pos_max'] - df['_pos_min'])) * 100
        else:
            df['smart_value'] = 50.0

    # Calculate global smart value
    global_min = df['smart_value_raw'].min()
    global_max = df['smart_value_raw'].max()

    if global_max > global_min:
        df['smart_value_global'] = ((df['smart_value_raw'] - global_min) / (global_max - global_min)) * 100
    else:
        df['smart_value_global'] = 50.0

    # Round scores
    df['smart_value'] = df['smart_value'].round(1)
    df['smart_value_global'] = df['smart_value_global'].round(1)

    # Build enhanced tooltip
    def build_enhanced_tooltip(row):
        # Show which advanced metrics were used
        advanced_metrics = []
        if use_advanced_metrics:
            for col in ['adv_tprr', 'adv_yprr', 'adv_rte_pct', 'adv_yaco_att', 'adv_success_rate']:
                if col in row and pd.notna(row[col]) and row[col] != 0:
                    advanced_metrics.append(col.replace('adv_', '').upper())

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
            f"Position Smart Value: {row['smart_value']:.1f}/100\n"
            f"Global Smart Value: {row['smart_value_global']:.1f}/100\n"
        )

        if advanced_metrics:
            tooltip += (
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🚀 Advanced Metrics: {', '.join(advanced_metrics)}\n"
            )

        tooltip += (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 Position SV: Best {row.get('position', 'player')} in pool\n"
            f"💡 Global SV: Best overall (cross-position)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Component Breakdown:\n\n"
            f"💰 Base Value: +{base_val:.1f} ({int(weights['base']*100)}% weight)\n"
        )

        if 'adv_yaco_att' in row and row.get('position') == 'RB' and pd.notna(row['adv_yaco_att']):
            tooltip += f"  └─ YACO/ATT adjusted: {row['adv_yaco_att']:.2f}\n"

        tooltip += (
            f"\n📊 Opportunity: +{opp_val:.1f} ({int(weights['opportunity']*100)}% weight)\n"
        )

        if advanced_metrics:
            if 'TPRR' in advanced_metrics:
                tooltip += f"  └─ TPRR: {row.get('adv_tprr', 0):.1%}\n"
            if 'YPRR' in advanced_metrics:
                tooltip += f"  └─ YPRR: {row.get('adv_yprr', 0):.2f}\n"
            if 'RTE_PCT' in advanced_metrics:
                tooltip += f"  └─ RTE%: {row.get('adv_rte_pct', 0):.1f}%\n"
            if 'SUCCESS_RATE' in advanced_metrics:
                tooltip += f"  └─ Success Rate: {row.get('adv_success_rate', 0):.1f}%\n"

        tooltip += (
            f"\n📈 Trends: {trend_val:+.1f} ({int(weights['trends']*100)}% weight)\n"
            f"  └─ Momentum, Role Trend, Recent FP\n\n"
            f"⚠️ Risk Adjust: {risk_val:+.1f} ({int(weights['risk']*100)}% weight)\n"
        )

        if row.get('position') == 'RB' and 'adv_success_rate' in row and pd.notna(row['adv_success_rate']):
            tooltip += f"  └─ Floor (Success Rate): {row['adv_success_rate']:.1f}%\n"

        tooltip += (
            f"\n🎯 Matchup: {match_val:+.1f} ({int(weights['matchup']*100)}% weight)\n"
            f"  └─ Game Total: {row.get('game_total', 0):.1f}, ITT: {row.get('team_itt', 0):.1f}\n\n"
            f"💎 Leverage: {leverage_val:+.1f} ({int(weights.get('leverage', 0)*100)}% weight)\n"
            f"  └─ Ceiling: {row.get('season_ceiling', 0):.1f}, Own: {row.get('ownership', 0):.1f}%\n"
        )

        if chalk_penalty_val < 0:
            tooltip += (
                f"\n❌ Chalk Penalty: {chalk_penalty_val:.1f}\n"
                f"  └─ High own ({row.get('ownership', 0):.1f}%) + Bad matchup\n"
            )

        tooltip += (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Final Score: {row['smart_value']:.1f}/100\n"
        )

        if advanced_metrics:
            tooltip += f"\n🔬 Enhanced with {len(advanced_metrics)} advanced metrics"

        return tooltip

    df['smart_value_tooltip'] = df.apply(build_enhanced_tooltip, axis=1)

    # Clean up helper columns
    df = df.drop(columns=['_pos_min', '_pos_max'], errors='ignore')

    # Log summary of enhancements used
    if use_advanced_metrics and advanced_columns:
        logger.info(f"Smart Value calculation complete with {len(advanced_columns)} advanced metrics")

    return df


# Create A/B testing function
def generate_ab_lineups(df: pd.DataFrame, profile: str = 'balanced', week: int = 6) -> Dict:
    """
    Generate lineups with and without advanced metrics for A/B testing.

    Args:
        df: Player DataFrame with both base and advanced metrics
        profile: Weight profile to use
        week: NFL week number

    Returns:
        Dictionary with 'with_advanced' and 'without_advanced' DataFrames
    """
    logger.info("Generating A/B test lineups...")

    # Version A: With advanced metrics
    df_with_advanced = calculate_smart_value_enhanced(
        df.copy(),
        profile=profile,
        week=week,
        use_advanced_metrics=True
    )

    # Version B: Without advanced metrics (original)
    df_without_advanced = calculate_smart_value_enhanced(
        df.copy(),
        profile=profile,
        week=week,
        use_advanced_metrics=False
    )

    # Calculate differences
    comparison = pd.DataFrame({
        'name': df['name'],
        'position': df['position'],
        'salary': df['salary'],
        'projection': df['projection'],
        'sv_with_advanced': df_with_advanced['smart_value'],
        'sv_without_advanced': df_without_advanced['smart_value'],
        'sv_difference': df_with_advanced['smart_value'] - df_without_advanced['smart_value']
    })

    # Find biggest movers
    comparison = comparison.sort_values('sv_difference', ascending=False)

    logger.info("A/B Test Summary:")
    logger.info(f"  Average SV change: {comparison['sv_difference'].mean():.2f}")
    logger.info(f"  Std Dev of change: {comparison['sv_difference'].std():.2f}")
    logger.info(f"  Max improvement: {comparison['sv_difference'].max():.2f}")
    logger.info(f"  Max decline: {comparison['sv_difference'].min():.2f}")

    # Log top movers
    top_gainers = comparison.head(5)
    top_losers = comparison.tail(5)

    logger.info("\nTop 5 Gainers from Advanced Metrics:")
    for _, player in top_gainers.iterrows():
        logger.info(f"  {player['name']} ({player['position']}): +{player['sv_difference']:.1f} SV")

    logger.info("\nTop 5 Losers from Advanced Metrics:")
    for _, player in top_losers.iterrows():
        logger.info(f"  {player['name']} ({player['position']}): {player['sv_difference']:.1f} SV")

    return {
        'with_advanced': df_with_advanced,
        'without_advanced': df_without_advanced,
        'comparison': comparison
    }