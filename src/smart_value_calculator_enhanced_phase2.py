"""
Enhanced Smart Value Calculator - Phase 2: Tier 1 Metrics Integration

This module enhances the calculate_opportunity_score function to use advanced metrics
when available, with graceful fallback to original metrics.

Part of DFS Advanced Stats Migration (Phase 2: Tier 1 Metrics)
Created: October 18, 2025
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
import logging

# Configure logging
logger = logging.getLogger(__name__)


def calculate_opportunity_score_enhanced(df: pd.DataFrame, weight: float,
                                        sub_weights: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """
    Calculate OPPORTUNITY score component (ENHANCED with advanced metrics).

    New in Phase 2:
    - Uses TPRR (Targets Per Route Run) if available, fallback to season_tgt
    - Uses YPRR (Yards Per Route Run) for efficiency component
    - Uses RTE% (Route Participation) for snap quality component
    - Uses Success Rate for floor component (RBs)

    Maintains backward compatibility: works with or without new metrics

    Args:
        df: Player DataFrame (may include 'adv_*' columns from advanced stats)
        weight: Weight for this component (default 0.30)
        sub_weights: Optional dict with keys for sub-component weights

    Returns:
        DataFrame with enhanced 'opp_score' column
    """
    # Default sub-weights if not provided
    if sub_weights is None:
        sub_weights = {
            'opp_target_quality': 0.35,    # TPRR or season_tgt
            'opp_efficiency': 0.30,         # YPRR or FP/G proxy
            'opp_snap_quality': 0.20,       # RTE% or season_snap
            'opp_floor': 0.15               # Success Rate or consistency proxy
        }

    # Initialize opportunity components
    df['opp_target_quality'] = 0.0
    df['opp_efficiency'] = 0.0
    df['opp_snap_quality'] = 0.0
    df['opp_floor'] = 0.0
    df['opp_raw'] = 0.0
    df['opp_score'] = 0.0

    # Track which metrics are being used
    metrics_used = []

    # For WR/TE: Use advanced metrics if available
    wr_te_mask = df['position'].isin(['WR', 'TE'])

    if wr_te_mask.any():
        # Target Quality: TPRR if available, fallback to season_tgt
        if 'adv_tprr' in df.columns and df.loc[wr_te_mask, 'adv_tprr'].notna().any():
            # TPRR is on 0-1 scale, scale to 0-100 for score
            df.loc[wr_te_mask, 'opp_target_quality'] = df.loc[wr_te_mask, 'adv_tprr'].fillna(0) * 100
            metrics_used.append('TPRR')
            logger.info("✅ Using TPRR for WR/TE target quality")
        elif 'season_tgt' in df.columns:
            # Fallback to original target share
            df.loc[wr_te_mask, 'opp_target_quality'] = df.loc[wr_te_mask, 'season_tgt'].fillna(0)
            logger.info("⚠️ Falling back to season_tgt for WR/TE (TPRR not available)")

        # Efficiency: YPRR if available
        if 'adv_yprr' in df.columns and df.loc[wr_te_mask, 'adv_yprr'].notna().any():
            # YPRR typically 0-10, scale to 0-100
            df.loc[wr_te_mask, 'opp_efficiency'] = (df.loc[wr_te_mask, 'adv_yprr'].fillna(0) / 10) * 100
            metrics_used.append('YPRR')
            logger.info("✅ Using YPRR for WR/TE efficiency")
        elif 'season_fpg' in df.columns:
            # Fallback: use FP/G as efficiency proxy
            max_fpg = df.loc[wr_te_mask, 'season_fpg'].max() if df.loc[wr_te_mask, 'season_fpg'].max() > 0 else 1
            df.loc[wr_te_mask, 'opp_efficiency'] = (df.loc[wr_te_mask, 'season_fpg'].fillna(0) / max_fpg) * 100
            logger.info("⚠️ Falling back to season_fpg for WR/TE efficiency (YPRR not available)")

        # Snap Quality: RTE% if available
        if 'adv_rte_pct' in df.columns and df.loc[wr_te_mask, 'adv_rte_pct'].notna().any():
            # RTE% is already in percentage form (0-100)
            df.loc[wr_te_mask, 'opp_snap_quality'] = df.loc[wr_te_mask, 'adv_rte_pct'].fillna(0)
            metrics_used.append('RTE%')
            logger.info("✅ Using RTE% for WR/TE snap quality")
        elif 'season_snap' in df.columns:
            # Fallback to season snap %
            df.loc[wr_te_mask, 'opp_snap_quality'] = df.loc[wr_te_mask, 'season_snap'].fillna(0)
            logger.info("⚠️ Falling back to season_snap for WR/TE (RTE% not available)")

    # For RB: Use advanced metrics if available
    rb_mask = df['position'] == 'RB'

    if rb_mask.any():
        # For RBs, opportunity is more about workload and efficiency

        # Primary opportunity: Snap % (workload indicator)
        if 'season_snap' in df.columns:
            df.loc[rb_mask, 'opp_snap_quality'] = df.loc[rb_mask, 'season_snap'].fillna(0)

        # Floor: Success Rate if available
        if 'adv_success_rate' in df.columns and df.loc[rb_mask, 'adv_success_rate'].notna().any():
            # Success Rate is 0-100
            df.loc[rb_mask, 'opp_floor'] = df.loc[rb_mask, 'adv_success_rate'].fillna(0)
            metrics_used.append('Success Rate')
            logger.info("✅ Using Success Rate for RB floor")
        elif 'season_cons' in df.columns:
            # Fallback: use consistency as floor proxy (invert it - lower consistency = higher floor)
            df.loc[rb_mask, 'opp_floor'] = 100 - df.loc[rb_mask, 'season_cons'].fillna(0) * 10
            logger.info("⚠️ Falling back to season_cons for RB floor (Success Rate not available)")

        # RB Efficiency: Could use YACO/ATT if needed (not in OPPORTUNITY but useful)
        # Leaving for BASE score enhancement

        # For RBs, weight more toward snap quality and floor
        df.loc[rb_mask, 'opp_target_quality'] = df.loc[rb_mask, 'opp_snap_quality'] * 0.5  # Use snap as proxy
        df.loc[rb_mask, 'opp_efficiency'] = df.loc[rb_mask, 'projection'].fillna(0) * 2  # Use projection as proxy

    # For QB: Keep existing logic
    qb_mask = df['position'] == 'QB'

    if qb_mask.any():
        # QB opportunity based on snap % and projection
        if 'season_snap' in df.columns:
            df.loc[qb_mask, 'opp_snap_quality'] = df.loc[qb_mask, 'season_snap'].fillna(0)

        # Use projection as opportunity proxy
        max_proj = df.loc[qb_mask, 'projection'].max() if df.loc[qb_mask, 'projection'].max() > 0 else 1
        df.loc[qb_mask, 'opp_efficiency'] = (df.loc[qb_mask, 'projection'].fillna(0) / max_proj) * 100
        df.loc[qb_mask, 'opp_target_quality'] = df.loc[qb_mask, 'opp_efficiency'] * 0.5
        df.loc[qb_mask, 'opp_floor'] = 50  # QBs generally have decent floor

    # Combine components into raw opportunity score
    df['opp_raw'] = (
        df['opp_target_quality'] * sub_weights.get('opp_target_quality', 0.35) +
        df['opp_efficiency'] * sub_weights.get('opp_efficiency', 0.30) +
        df['opp_snap_quality'] * sub_weights.get('opp_snap_quality', 0.20) +
        df['opp_floor'] * sub_weights.get('opp_floor', 0.15)
    )

    # Normalize by position (0-100 scale) then apply weight
    for position in df['position'].unique():
        pos_mask = df['position'] == position
        if pos_mask.any():
            pos_min = df.loc[pos_mask, 'opp_raw'].min()
            pos_max = df.loc[pos_mask, 'opp_raw'].max()

            if pos_max > pos_min:
                df.loc[pos_mask, 'opp_score'] = ((df.loc[pos_mask, 'opp_raw'] - pos_min) /
                                                  (pos_max - pos_min)) * weight
            else:
                df.loc[pos_mask, 'opp_score'] = 0.5 * weight  # Default if all same

    # Log summary of metrics used
    if metrics_used:
        logger.info(f"Advanced metrics integrated into OPPORTUNITY score: {', '.join(metrics_used)}")
    else:
        logger.warning("No advanced metrics available - using original opportunity calculation")

    return df


def add_ab_testing_capability(df: pd.DataFrame, use_advanced_metrics: bool = True) -> pd.DataFrame:
    """
    Add A/B testing capability to compare lineups with/without advanced metrics.

    This function adds a feature flag mechanism to enable/disable advanced metrics
    for lineup generation comparison.

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
            'avg_salary': lineups_with['total_salary'].mean() if 'total_salary' in lineups_with.columns else 0,
            'avg_smart_value': lineups_with['total_smart_value'].mean() if 'total_smart_value' in lineups_with.columns else 0,
            'std_projection': lineups_with['total_projection'].std() if 'total_projection' in lineups_with.columns else 0,
            'max_projection': lineups_with['total_projection'].max() if 'total_projection' in lineups_with.columns else 0,
            'min_projection': lineups_with['total_projection'].min() if 'total_projection' in lineups_with.columns else 0,
        },
        'without_advanced': {
            'count': len(lineups_without),
            'avg_projection': lineups_without['total_projection'].mean() if 'total_projection' in lineups_without.columns else 0,
            'avg_salary': lineups_without['total_salary'].mean() if 'total_salary' in lineups_without.columns else 0,
            'avg_smart_value': lineups_without['total_smart_value'].mean() if 'total_smart_value' in lineups_without.columns else 0,
            'std_projection': lineups_without['total_projection'].std() if 'total_projection' in lineups_without.columns else 0,
            'max_projection': lineups_without['total_projection'].max() if 'total_projection' in lineups_without.columns else 0,
            'min_projection': lineups_without['total_projection'].min() if 'total_projection' in lineups_without.columns else 0,
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


# Integration helper to patch the existing smart_value_calculator
def patch_smart_value_calculator():
    """
    Patch the existing smart_value_calculator module to use enhanced opportunity score.

    This function can be called to upgrade the existing module with Phase 2 enhancements.
    """
    try:
        import smart_value_calculator as svc

        # Replace the calculate_opportunity_score with enhanced version
        svc.calculate_opportunity_score = calculate_opportunity_score_enhanced

        logger.info("✅ Smart Value Calculator patched with Phase 2 enhancements")
        return True

    except ImportError:
        logger.error("Failed to import smart_value_calculator for patching")
        return False


if __name__ == '__main__':
    # Test the enhanced opportunity score
    print("Phase 2: Enhanced Opportunity Score Calculator")
    print("=" * 60)

    # Create sample data
    test_df = pd.DataFrame({
        'name': ['Player A', 'Player B', 'Player C', 'Player D'],
        'position': ['WR', 'WR', 'RB', 'QB'],
        'salary': [7000, 6000, 8000, 7500],
        'projection': [15.5, 12.3, 18.2, 22.1],
        'season_tgt': [25, 18, 5, 0],
        'season_snap': [85, 72, 68, 95],
        'season_fpg': [14.2, 11.5, 16.8, 21.3],
        'season_cons': [2.1, 3.5, 1.8, 1.2],
        # Advanced metrics (simulated)
        'adv_tprr': [0.28, 0.22, None, None],
        'adv_yprr': [2.1, 1.8, None, None],
        'adv_rte_pct': [92, 78, None, None],
        'adv_success_rate': [None, None, 48.5, None]
    })

    # Test with advanced metrics
    print("\nTesting WITH advanced metrics:")
    result_with = calculate_opportunity_score_enhanced(test_df.copy(), weight=0.30)
    print(result_with[['name', 'position', 'opp_target_quality', 'opp_efficiency',
                       'opp_snap_quality', 'opp_floor', 'opp_score']])

    # Test without advanced metrics (A/B test)
    print("\nTesting WITHOUT advanced metrics:")
    test_df_without = add_ab_testing_capability(test_df.copy(), use_advanced_metrics=False)
    result_without = calculate_opportunity_score_enhanced(test_df_without, weight=0.30)
    print(result_without[['name', 'position', 'opp_target_quality', 'opp_efficiency',
                          'opp_snap_quality', 'opp_floor', 'opp_score']])

    print("\n✅ Phase 2 Enhanced Opportunity Score implementation complete!")