"""
Season Stats Analyzer - Comprehensive 5-Week Analysis with Advanced Metrics
Extracts actionable DFS insights from cumulative season data (Weeks 1-5)

ENHANCED: Now supports 4-file advanced stats system with graceful fallback
Part of DFS Advanced Stats Migration (Phase 2: Tier 1 Metrics)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
from fuzzywuzzy import fuzz
import os
import time
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Import Phase 1 infrastructure components
try:
    # Use advanced_stats_db for database operations (supports separate tables from migration 008)
    from .advanced_stats_db import (
        save_advanced_stats_to_database, load_advanced_stats_from_database
    )
    # Use advanced_stats_loader for file operations
    from .advanced_stats_loader import (
        FileLoader, load_season_stats_files, create_player_mapper
    )
    from .player_name_mapper import PlayerNameMapper, normalize_name
    from .metric_definitions import MetricRegistry
    ADVANCED_STATS_AVAILABLE = True
except ImportError:
    logger.warning("Advanced stats modules not available. Using legacy mode.")
    ADVANCED_STATS_AVAILABLE = False
    # Define dummy types for type hints when imports fail
    PlayerNameMapper = None
    MetricRegistry = None


# ========================================
# LEGACY FUNCTIONS (Preserved for Compatibility)
# ========================================

def normalize_name_legacy(name: str) -> str:
    """Legacy normalize function for backward compatibility."""
    if pd.isna(name):
        return ""
    # Remove suffixes, extra spaces, convert to lowercase
    name = str(name).lower().strip()
    name = name.replace(' jr.', '').replace(' sr.', '').replace(' iii', '').replace(' ii', '')
    name = name.replace('.', '').replace("'", '')
    return name


def fuzzy_match_player(player_name: str, stats_df: pd.DataFrame, threshold: int = 85) -> Optional[pd.Series]:
    """
    Fuzzy match player name against stats DataFrame.
    For datasets with multiple rows per player (one per week), returns the row with the highest W value.

    Args:
        player_name: Player name to match
        stats_df: DataFrame with 'Name' column
        threshold: Minimum fuzzy match score (0-100)

    Returns:
        Matched row with highest W value (most complete data), or None if no match found
    """
    # Use new normalize_name if available, otherwise legacy
    if ADVANCED_STATS_AVAILABLE:
        norm_search = normalize_name(player_name)
    else:
        norm_search = normalize_name_legacy(player_name)

    # Collect all matching rows with their scores
    matches = []

    for idx, row in stats_df.iterrows():
        if ADVANCED_STATS_AVAILABLE:
            norm_candidate = normalize_name(row['Name'])
        else:
            norm_candidate = normalize_name_legacy(row['Name'])
        score = fuzz.ratio(norm_search, norm_candidate)

        if score >= threshold:
            matches.append((score, row))

    if not matches:
        return None

    # Get the highest score
    best_score = max(match[0] for match in matches)

    # Filter to only rows with the best score
    best_matches = [match[1] for match in matches if match[0] == best_score]

    if len(best_matches) == 1:
        return best_matches[0]

    # Multiple rows with same name - select the one with highest W value (most recent/complete data)
    if 'W' in stats_df.columns:
        max_week_row = max(best_matches, key=lambda x: x.get('W', 0) if pd.notna(x.get('W', 0)) else 0)
        return max_week_row

    # If no W column, just return the first match
    return best_matches[0]


# ========================================
# ENHANCED FUNCTIONS (Phase 2: Advanced Stats)
# ========================================

def _create_mapping_dataframe(player_mapper: PlayerNameMapper, file_key: str) -> pd.DataFrame:
    """
    Create a DataFrame suitable for merging from PlayerNameMapper.

    This converts the mapping objects into a merge-ready DataFrame for bulk operations.

    Args:
        player_mapper: Pre-computed name mappings
        file_key: One of 'pass', 'rush', 'receiving', 'snaps'

    Returns:
        DataFrame with columns: original_name, matched_name, match_score, normalized_name
    """
    return player_mapper.create_mapping_dataframe(file_key)


def _prepare_stats_for_merge(file_df: pd.DataFrame, metrics: List) -> pd.DataFrame:
    """
    Prepare stats DataFrame for merging by extracting only needed columns.

    Args:
        file_df: Raw stats DataFrame
        metrics: List of MetricDefinition objects to extract

    Returns:
        DataFrame with Name and metric columns only
    """
    # Get unique column names needed
    columns_needed = ['Name']
    for metric in metrics:
        if metric.source_column not in columns_needed:
            columns_needed.append(metric.source_column)

    # Filter to only columns that exist
    columns_available = [col for col in columns_needed if col in file_df.columns]

    if len(columns_available) < 2:  # Need at least Name + 1 metric
        logger.warning(f"Not enough columns available for merge. Needed: {columns_needed}, Available: {columns_available}")
        return pd.DataFrame()

    # Create subset with aggregation (in case of multiple weeks)
    # For metrics, we'll take the mean across weeks
    if 'W' in file_df.columns:
        # Group by Name and take mean of metrics
        agg_dict = {col: 'mean' for col in columns_available if col != 'Name'}
        if agg_dict:
            stats_subset = file_df[columns_available + ['W']].groupby('Name').agg(agg_dict).reset_index()
        else:
            stats_subset = file_df[['Name']].drop_duplicates()
    else:
        stats_subset = file_df[columns_available].copy()

    return stats_subset


def _log_enrichment_stats(player_df: pd.DataFrame, metrics_to_extract: Dict):
    """
    Log statistics about the enrichment process.

    Args:
        player_df: Enriched player DataFrame
        metrics_to_extract: Dictionary of metrics that were attempted
    """
    enrichment_report = []

    for metric_id, metric_def in metrics_to_extract.items():
        if metric_id in player_df.columns:
            non_null_count = player_df[metric_id].notna().sum()
            total_count = len(player_df)
            success_rate = (non_null_count / total_count * 100) if total_count > 0 else 0

            # Calculate average value by position
            position_avgs = {}
            for position in metric_def.positions:
                pos_mask = player_df['position'] == position
                if pos_mask.any():
                    pos_avg = player_df.loc[pos_mask, metric_id].mean()
                    if not pd.isna(pos_avg):
                        position_avgs[position] = round(pos_avg, 2)

            enrichment_report.append({
                'metric': metric_def.display_name,
                'extracted': non_null_count,
                'total': total_count,
                'rate': f"{success_rate:.1f}%",
                'avg_by_position': position_avgs
            })

    # Log summary
    logger.info("Advanced Metric Enrichment Summary:")
    for report_item in enrichment_report:
        logger.info(f"  {report_item['metric']}: {report_item['extracted']}/{report_item['total']} ({report_item['rate']})")
        if report_item['avg_by_position']:
            logger.info(f"    Averages: {report_item['avg_by_position']}")

    # Warning if low extraction rates
    low_extraction = [r for r in enrichment_report if float(r['rate'].rstrip('%')) < 90]
    if low_extraction:
        logger.warning(f"Low extraction rates (<90%) for: {[r['metric'] for r in low_extraction]}")


def enrich_with_advanced_stats(
    player_df: pd.DataFrame,
    season_files: Dict[str, Optional[pd.DataFrame]],
    player_mapper: PlayerNameMapper,
    tiers: List[int] = None
) -> pd.DataFrame:
    """
    Enrich player DataFrame with advanced metrics using JOIN-BASED approach.

    CRITICAL: Uses bulk DataFrame merge operations, NOT iterrows loops.

    Args:
        player_df: Main player DataFrame
        season_files: Loaded season stat files {'pass': df, 'rush': df, ...}
        player_mapper: Pre-computed name mappings
        tiers: Which metric tiers to include (default: [1, 2])

    Returns:
        Enriched player DataFrame with new 'adv_*' columns

    Performance: <3 seconds for 500 players with 10 metrics
    """
    if tiers is None:
        tiers = [1, 2]

    start_time = time.time()
    logger.info(f"Enriching {len(player_df)} players with Tier {tiers} advanced metrics...")

    # Step 1: Get relevant metrics for these tiers
    registry = MetricRegistry()
    metrics_to_extract = {}
    for tier in tiers:
        metrics_to_extract.update(registry.get_metrics_by_tier(tier))

    logger.info(f"Extracting {len(metrics_to_extract)} metrics: {list(metrics_to_extract.keys())}")

    # Step 2: Create a copy to avoid modifying original
    enriched_df = player_df.copy()

    # Step 3: For each file, prepare merged stats DataFrame
    for file_key, file_df in season_files.items():
        if file_df is None or file_df.empty:
            logger.debug(f"Skipping {file_key} file (not loaded or empty)")
            continue

        # Get metrics from this file
        file_metrics = [m for m in metrics_to_extract.values() if m.source_file == file_key]
        if not file_metrics:
            logger.debug(f"No metrics to extract from {file_key}")
            continue

        logger.info(f"Extracting {len(file_metrics)} metrics from {file_key}: {[m.display_name for m in file_metrics]}")

        # Create mapping DataFrame for this file
        mapping_df = _create_mapping_dataframe(player_mapper, file_key)

        if mapping_df.empty:
            logger.warning(f"No mappings available for {file_key}")
            continue

        # Prepare stats for merge
        stats_for_merge = _prepare_stats_for_merge(file_df, file_metrics)

        if stats_for_merge.empty:
            logger.warning(f"No stats available for merge from {file_key}")
            continue

        # Merge stats with mapping
        merged_stats = mapping_df.merge(
            stats_for_merge,
            left_on='matched_name',
            right_on='Name',
            how='left'
        )

        # Rename columns to metric IDs
        for metric in file_metrics:
            if metric.source_column in merged_stats.columns:
                # Create the advanced metric column name
                merged_stats[metric.metric_id] = merged_stats[metric.source_column]

        # Select only the columns we need for final merge
        merge_cols = ['original_name'] + [m.metric_id for m in file_metrics if m.metric_id in merged_stats.columns]
        merged_stats_final = merged_stats[merge_cols].copy()

        # Merge into enriched_df (BULK OPERATION)
        enriched_df = enriched_df.merge(
            merged_stats_final,
            left_on='name',
            right_on='original_name',
            how='left',
            suffixes=('', '_new')
        )

        # Clean up duplicate columns
        enriched_df = enriched_df.drop(columns=['original_name'], errors='ignore')

    # Step 4: Fill NaN values with appropriate defaults
    for metric_id, metric_def in metrics_to_extract.items():
        if metric_id in enriched_df.columns:
            # Use 0 as default for most metrics (indicates no data)
            enriched_df[metric_id] = enriched_df[metric_id].fillna(0)

    # Step 5: Log enrichment statistics
    _log_enrichment_stats(enriched_df, metrics_to_extract)

    elapsed = time.time() - start_time
    logger.info(f"✅ Advanced stats enrichment complete in {elapsed:.2f} seconds")

    # Performance warning
    if elapsed > 3.0:
        logger.warning(f"Performance target missed: {elapsed:.2f}s > 3.0s target")

    return enriched_df


def _enrich_with_base_metrics(
    player_df: pd.DataFrame,
    season_files: Dict[str, Optional[pd.DataFrame]],
    player_mapper: PlayerNameMapper
) -> pd.DataFrame:
    """
    Extract original 9 base metrics from the new 4-file system.

    Maps the original metrics to their sources in the new files:
    - season_trend, season_cons, season_mom, season_snap: from Snaps file
    - season_fpg, season_ceiling: from Snaps file
    - season_var, season_tgt, season_eztgt: from Receiving file (WR/TE only)

    Args:
        player_df: Player DataFrame to enrich
        season_files: Loaded 4-file system
        player_mapper: Pre-computed name mappings

    Returns:
        Player DataFrame with original 9 metrics
    """
    logger.info("Extracting base metrics from new 4-file system...")

    # Initialize columns
    base_columns = {
        'season_trend': 0.0,
        'season_cons': 0.0,
        'season_mom': 0.0,
        'season_snap': 0.0,
        'season_fpg': 0.0,
        'season_ceiling': 0.0,
        'season_var': 0.0,
        'season_tgt': 0.0,
        'season_eztgt': 0
    }

    for col, default in base_columns.items():
        if col not in player_df.columns:
            player_df[col] = default

    # Extract from Snaps file
    snaps_df = season_files.get('snaps')
    if snaps_df is not None and not snaps_df.empty:
        # Get mapping for snaps file
        mapping_df = player_mapper.create_mapping_dataframe('snaps')

        if not mapping_df.empty:
            # Aggregate snaps data by player (mean across weeks)
            if 'W' in snaps_df.columns:
                # Calculate weekly metrics
                for idx, player_row in player_df.iterrows():
                    player_name = player_row.get('name', '')
                    if not player_name:
                        continue

                    # Find mapped name
                    mapping = player_mapper.mappings.get(player_name)
                    if mapping and mapping.matched_name_snaps:
                        # Get all weeks for this player
                        player_weeks = snaps_df[snaps_df['Name'] == mapping.matched_name_snaps]

                        if not player_weeks.empty:
                            # Calculate trend, consistency, momentum from weekly data
                            weekly_snaps = []
                            weekly_fp = []

                            for week in range(1, 6):
                                week_data = player_weeks[player_weeks['W'] == week]
                                if not week_data.empty:
                                    snap_pct = week_data.iloc[0].get('Snap %', 0)
                                    fp = week_data.iloc[0].get('FP', 0)
                                    weekly_snaps.append(float(snap_pct) if pd.notna(snap_pct) else 0)
                                    weekly_fp.append(float(fp) if pd.notna(fp) else 0)
                                else:
                                    weekly_snaps.append(0)
                                    weekly_fp.append(0)

                            # Calculate metrics
                            if weekly_snaps:
                                # Trend: W1 → W5 change
                                player_df.at[idx, 'season_trend'] = weekly_snaps[4] - weekly_snaps[0] if len(weekly_snaps) >= 5 else 0

                                # Consistency: STD of snap %
                                player_df.at[idx, 'season_cons'] = np.std(weekly_snaps) if len(weekly_snaps) > 1 else 0

                                # Momentum: Recent vs Early FP
                                if weekly_fp and len(weekly_fp) >= 5:
                                    early_avg = np.mean(weekly_fp[:2])
                                    recent_avg = np.mean(weekly_fp[2:5])
                                    player_df.at[idx, 'season_mom'] = recent_avg - early_avg

                                # Average snap %
                                player_df.at[idx, 'season_snap'] = np.mean(weekly_snaps)

                                # Ceiling (best game)
                                player_df.at[idx, 'season_ceiling'] = max(weekly_fp) if weekly_fp else 0

                            # FP/G (from aggregated data)
                            fpg = player_weeks['FP/G'].mean() if 'FP/G' in player_weeks.columns else 0
                            player_df.at[idx, 'season_fpg'] = float(fpg) if pd.notna(fpg) else 0

    # Extract from Receiving file (WR/TE only)
    receiving_df = season_files.get('receiving')
    if receiving_df is not None and not receiving_df.empty:
        # Get mapping for receiving file
        mapping_df = player_mapper.create_mapping_dataframe('receiving')

        if not mapping_df.empty:
            # Process WR/TE players
            wr_te_mask = player_df['position'].isin(['WR', 'TE'])

            for idx, player_row in player_df[wr_te_mask].iterrows():
                player_name = player_row.get('name', '')
                if not player_name:
                    continue

                # Find mapped name
                mapping = player_mapper.mappings.get(player_name)
                if mapping and mapping.matched_name_receiving:
                    # Get player data (aggregate if multiple weeks)
                    player_data = receiving_df[receiving_df['Name'] == mapping.matched_name_receiving]

                    if not player_data.empty:
                        # Use mean if multiple weeks
                        if 'TGT %' in player_data.columns:
                            tgt_pct = player_data['TGT %'].mean()
                            player_df.at[idx, 'season_tgt'] = float(tgt_pct) if pd.notna(tgt_pct) else 0

                        if 'EZTGT' in player_data.columns:
                            ez_tgt = player_data['EZTGT'].sum()  # Sum across weeks
                            player_df.at[idx, 'season_eztgt'] = int(ez_tgt) if pd.notna(ez_tgt) else 0

                        # Calculate XFP variance if available
                        if 'FP' in player_data.columns and 'RecXFP' in player_data.columns:
                            actual_fp = player_data['FP'].mean()
                            expected_fp = player_data['RecXFP'].mean()
                            if pd.notna(actual_fp) and pd.notna(expected_fp):
                                player_df.at[idx, 'season_var'] = float(actual_fp) - float(expected_fp)

    logger.info(f"Base metrics extracted for {len(player_df)} players")
    return player_df


def analyze_season_stats_legacy(
    player_df: pd.DataFrame,
    excel_path: str = "2025 Stats thru week 5.xlsx"
) -> pd.DataFrame:
    """
    Legacy function for analyzing season stats from single file.

    Preserved for backward compatibility when new 4-file system is not available.
    """
    # [Original function body preserved exactly as before]
    # Check if file exists
    if not os.path.exists(excel_path):
        print(f"⚠️  Season stats file not found: {excel_path}")
        # Return df with empty columns
        empty_cols = {
            'season_trend': 0.0,
            'season_cons': 0.0,
            'season_mom': 0.0,
            'season_snap': 0.0,
            'season_fpg': 0.0,
            'season_ceiling': 0.0,
            'season_var': 0.0,
            'season_tgt': 0.0,
            'season_eztgt': 0,
            'season_cons_tooltip': 'No season data available',
            'season_mom_tooltip': 'No season data available',
            'season_weekly_snaps': ''
        }
        for col, default in empty_cols.items():
            player_df[col] = default
        return player_df

    print(f"📊 Loading season stats from: {excel_path}")

    try:
        # Load all sheets
        xls = pd.ExcelFile(excel_path)
        snaps_df = pd.read_excel(xls, 'Snaps')
        rec_df = pd.read_excel(xls, 'Rec')

        print(f"   Loaded {len(snaps_df)} snap records, {len(rec_df)} receiving records")

        # Initialize new columns
        player_df['season_trend'] = 0.0
        player_df['season_cons'] = 0.0
        player_df['season_mom'] = 0.0
        player_df['season_snap'] = 0.0
        player_df['season_fpg'] = 0.0
        player_df['season_ceiling'] = 0.0  # Best game of the season
        player_df['season_var'] = 0.0
        player_df['season_tgt'] = 0.0
        player_df['season_eztgt'] = 0
        player_df['season_cons_tooltip'] = ''
        player_df['season_mom_tooltip'] = ''
        player_df['season_weekly_snaps'] = ''  # Store as string for display

        matched_count = 0

        # Process each player
        for idx, player_row in player_df.iterrows():
            player_name = player_row.get('name', '')

            if not player_name or pd.isna(player_name):
                continue

            # Match to Snaps data
            snap_match = fuzzy_match_player(player_name, snaps_df, threshold=85)
            if snap_match is not None:
                # Get weekly FP data for production-based momentum
                weekly_fp = get_weekly_fp_data(player_name, snaps_df)

                # Calculate snap metrics with production momentum
                snap_metrics = calculate_snap_metrics(snap_match, weekly_fp)
                player_df.at[idx, 'season_trend'] = snap_metrics['trend']
                player_df.at[idx, 'season_cons'] = snap_metrics['consistency']
                player_df.at[idx, 'season_mom'] = snap_metrics['momentum']
                player_df.at[idx, 'season_snap'] = snap_metrics['avg_snap']

                # Build consistency tooltip
                weekly_snaps = snap_metrics['weekly_snaps']
                cons_val = snap_metrics['consistency']
                cons_tooltip = f"Snap% by week: W1={weekly_snaps[0]:.1f}% | W2={weekly_snaps[1]:.1f}% | W3={weekly_snaps[2]:.1f}% | W4={weekly_snaps[3]:.1f}% | W5={weekly_snaps[4]:.1f}% | "
                cons_tooltip += f"STD={cons_val:.1f} | "
                if cons_val < 5:
                    cons_tooltip += "✅ CONSISTENT - Stable role, reliable floor (great for cash games)"
                elif cons_val < 10:
                    cons_tooltip += "⚠️ MODERATE - Some variance in role (usable in both cash and GPP)"
                else:
                    cons_tooltip += "❌ VOLATILE - Boom/bust role (GPP only, avoid cash games)"
                player_df.at[idx, 'season_cons_tooltip'] = cons_tooltip

                # Build momentum tooltip (production-based)
                weekly_fp = snap_metrics['weekly_fp']
                early_fp_avg = snap_metrics['early_fp_avg']
                recent_fp_avg = snap_metrics['recent_fp_avg']
                mom_val = snap_metrics['momentum']

                # Show weekly FP data
                mom_tooltip = f"FP by week: W1={weekly_fp[0]:.1f} | W2={weekly_fp[1]:.1f} | W3={weekly_fp[2]:.1f} | W4={weekly_fp[3]:.1f} | W5={weekly_fp[4]:.1f} | "
                mom_tooltip += f"Early avg (W1-W2): {early_fp_avg:.1f} FP | Recent avg (W3-W5): {recent_fp_avg:.1f} FP | Diff={mom_val:+.1f} FP | "

                if mom_val > 5:
                    mom_tooltip += "🔥 HEATING UP - Production increasing! Ride the hot hand, target before ownership catches up"
                elif mom_val < -5:
                    mom_tooltip += "🧊 COOLING DOWN - Production declining, fade or reduce exposure"
                else:
                    mom_tooltip += "➡️ STEADY - Consistent production throughout season"
                player_df.at[idx, 'season_mom_tooltip'] = mom_tooltip

                # Get FP/G from snaps sheet
                fp_g = snap_match.get('FP/G', 0.0)
                player_df.at[idx, 'season_fpg'] = round(float(fp_g), 1) if pd.notna(fp_g) else 0.0

                # Calculate CEILING (best single game performance)
                weekly_fp = snap_metrics['weekly_fp']

                if weekly_fp and len(weekly_fp) > 0:
                    # Ceiling = best single game (no consistency adjustment)
                    raw_ceiling = max(weekly_fp)
                    player_df.at[idx, 'season_ceiling'] = round(float(raw_ceiling), 1)
                else:
                    player_df.at[idx, 'season_ceiling'] = 0.0

                matched_count += 1

            # Match to Receiving data (for WR/TE only)
            player_pos = player_row.get('position', '').upper()
            if player_pos in ['WR', 'TE']:
                rec_match = fuzzy_match_player(player_name, rec_df, threshold=85)
                if rec_match is not None:
                    # Target share %
                    tgt_pct = rec_match.get('TGT %', 0.0)
                    player_df.at[idx, 'season_tgt'] = round(float(tgt_pct), 1) if pd.notna(tgt_pct) else 0.0

                    # Red zone targets
                    ez_tgt = rec_match.get('EZTGT', 0)
                    player_df.at[idx, 'season_eztgt'] = int(ez_tgt) if pd.notna(ez_tgt) else 0

                    # XFP Variance (Actual FP - Expected FP)
                    actual_fp = rec_match.get('FP', 0.0)
                    expected_fp = rec_match.get('RecXFP', 0.0)
                    if pd.notna(actual_fp) and pd.notna(expected_fp):
                        variance = float(actual_fp) - float(expected_fp)
                        player_df.at[idx, 'season_var'] = round(variance, 1)

        print(f"✅ Enriched {matched_count}/{len(player_df)} players with season stats")

        return player_df

    except Exception as e:
        print(f"❌ Error analyzing season stats: {str(e)}")
        import traceback
        traceback.print_exc()

        # Return df with empty columns on error
        empty_cols = {
            'season_trend': 0.0,
            'season_cons': 0.0,
            'season_mom': 0.0,
            'season_snap': 0.0,
            'season_fpg': 0.0,
            'season_var': 0.0,
            'season_tgt': 0.0,
            'season_eztgt': 0,
            'season_cons_tooltip': 'No season data available',
            'season_mom_tooltip': 'No season data available',
            'season_weekly_snaps': ''
        }
        for col, default in empty_cols.items():
            if col not in player_df.columns:
                player_df[col] = default

        return player_df


def analyze_season_stats(
    player_df: pd.DataFrame,
    season_stats_dir: str = "DFS/seasonStats/",
    legacy_file: str = "DFS/2025 Stats thru week 5.xlsx",
    use_advanced_stats: bool = True,
    week: int = None
) -> pd.DataFrame:
    """
    Main entry point - prioritizes database, then files, then legacy fallback.

    Args:
        player_df: Player DataFrame to enrich
        season_stats_dir: Directory with new 4-file system (fallback)
        legacy_file: Path to legacy single file (last resort fallback)
        use_advanced_stats: Whether to extract advanced metrics (Tier 1 & 2)
        week: Week number for database/file loading (e.g., 8). If None, uses generic names.

    Returns:
        Enriched player DataFrame with original 9 metrics + advanced metrics

    Performance: <5 seconds total for 500 players
    """
    if not ADVANCED_STATS_AVAILABLE:
        logger.info("Advanced stats modules not available. Using legacy mode.")
        print("⚠️  ADVANCED_STATS_AVAILABLE = False - Using legacy mode")
        return analyze_season_stats_legacy(player_df, legacy_file)

    season_files = None
    
    # PRIORITY 1: Try loading from database (preferred for production)
    if week is not None:
        try:
            logger.info(f"🗄️  Attempting to load advanced stats from database (week={week})")
            print(f"\n{'='*80}")
            print(f"🗄️  ANALYZE_SEASON_STATS CALLED")
            print(f"{'='*80}")
            print(f"   Week: {week}")
            print(f"   Players in DataFrame: {len(player_df)}")
            print(f"   Loading from database...")
            
            season_files = load_advanced_stats_from_database(week=week)
            
            # Check if we got any data
            files_loaded = sum(1 for df in season_files.values() if df is not None and len(df) > 0)
            if files_loaded > 0:
                logger.info(f"✅ Loaded {files_loaded} stat types from database for week {week}")
                print(f"✅ Loaded {files_loaded} stat types from database")
                
                # Print detailed stats for each file type
                for file_type, df in season_files.items():
                    if df is not None and len(df) > 0:
                        print(f"   {file_type}: {len(df)} records")
                        if len(df) > 0:
                            print(f"      Sample players: {df['Name'].head(3).tolist()}")
            else:
                logger.info("📂 No data in database, trying files...")
                print("📂 No data in database, trying files...")
                season_files = None
        except Exception as e:
            logger.warning(f"⚠️  Database load failed: {e}. Trying files...")
            print(f"⚠️  Database load failed: {e}")
            import traceback
            print(traceback.format_exc())
            season_files = None
    
    # PRIORITY 2: Try loading from files (fallback)
    if season_files is None and os.path.exists(season_stats_dir) and os.listdir(season_stats_dir):
        logger.info(f"📂 Loading from files in {season_stats_dir} (week={week})")
        season_files = load_season_stats_files(season_stats_dir, week=week)
        
        # Check if we got any files
        files_loaded = sum(1 for df in season_files.values() if df is not None)
        if files_loaded == 0:
            logger.warning("No files loaded from directory.")
            season_files = None
    
    # If we have data (from database or files), process it
    if season_files is not None:
        files_loaded = sum(1 for df in season_files.values() if df is not None and len(df) > 0)
        if files_loaded > 0:
            print(f"\n📊 Processing {files_loaded} stat types...")
            
            # Create player mapper (ONE-TIME fuzzy matching)
            print(f"   Creating player mapper...")
            player_mapper = create_player_mapper(player_df, season_files)
            print(f"   ✅ Mapped {len(player_mapper)} players")
            
            # Show sample mappings
            if len(player_mapper) > 0:
                sample_mappings = list(player_mapper.items())[:3]
                print(f"   Sample mappings:")
                for orig_name, matches in sample_mappings:
                    print(f"      '{orig_name}' → {list(matches.keys())}")

            # Extract original 9 metrics
            print(f"   Enriching with base metrics...")
            player_df_before = len(player_df.columns)
            player_df = _enrich_with_base_metrics(player_df, season_files, player_mapper)
            player_df_after = len(player_df.columns)
            print(f"   ✅ Base metrics added ({player_df_after - player_df_before} new columns)")

            # Extract advanced metrics (Tier 1 + 2) if requested
            if use_advanced_stats:
                print(f"   Enriching with advanced stats (Tiers 1 & 2)...")
                player_df_before = len(player_df.columns)
                player_df = enrich_with_advanced_stats(player_df, season_files, player_mapper, tiers=[1, 2])
                player_df_after = len(player_df.columns)
                print(f"   ✅ Advanced stats added ({player_df_after - player_df_before} new columns)")
                
                # Show sample of enriched data
                adv_cols = [col for col in player_df.columns if 'adv_' in col]
                if adv_cols:
                    print(f"\n   📊 Advanced columns added: {len(adv_cols)}")
                    print(f"   Sample columns: {adv_cols[:5]}")
                    # Show a sample player with advanced stats
                    sample_players = player_df[player_df[adv_cols[0]].notna()].head(3)
                    if len(sample_players) > 0:
                        print(f"   ✅ Players with data: {len(sample_players)}/{len(player_df)}")
                        for idx, row in sample_players.iterrows():
                            player_name = row['name']
                            pos = row.get('position', 'N/A')
                            sample_val = row[adv_cols[0]]
                            print(f"      {player_name} ({pos}): {adv_cols[0]}={sample_val}")
                        
                        # CRITICAL: Show Streamlit message so user can see this in UI
                        try:
                            import streamlit as st
                            st.success(f"✅ Added {len(adv_cols)} advanced stats columns to DataFrame")
                            st.info(f"📊 Sample columns: {', '.join(adv_cols[:5])}")
                            st.info(f"✅ {len(sample_players)}/{len(player_df)} players have advanced stats data")
                        except:
                            pass  # Streamlit not available (testing mode)
                    else:
                        print(f"   ⚠️  WARNING: No players have advanced stats data!")
                        print(f"      This suggests player name matching failed")
                        try:
                            import streamlit as st
                            st.warning("⚠️ Advanced stats columns added but no players have data - check player name matching")
                        except:
                            pass
                else:
                    print(f"   ⚠️  WARNING: No advanced columns were added!")
                    try:
                        import streamlit as st
                        st.error("❌ No advanced stats columns were added to DataFrame")
                    except:
                        pass
            
            print(f"{'='*80}\n")
            return player_df
    
    # PRIORITY 3: Last resort - legacy file (if it exists)
    if os.path.exists(legacy_file):
        logger.warning(f"⚠️  No database or file data found. Using legacy file: {legacy_file}")
        player_df = analyze_season_stats_legacy(player_df, legacy_file)
    else:
        logger.warning("⚠️  No season stats data available (database, files, or legacy)")
        # Return player_df unchanged - app will work without advanced stats

    return player_df


# ========================================
# LEGACY HELPER FUNCTIONS (Preserved)
# ========================================

def get_weekly_fp_data(player_name: str, snaps_df: pd.DataFrame) -> list:
    """
    Extract weekly FP data for a player from all their rows (W=1 to W=5).

    Args:
        player_name: Player name to match
        snaps_df: Full Snaps DataFrame with all weeks

    Returns:
        List of weekly FP values [W1_FP, W2_FP, W3_FP, W4_FP, W5_FP]
    """
    if ADVANCED_STATS_AVAILABLE:
        norm_search = normalize_name(player_name)
    else:
        norm_search = normalize_name_legacy(player_name)

    # Find all rows for this player
    player_rows = []
    for idx, row in snaps_df.iterrows():
        if ADVANCED_STATS_AVAILABLE:
            norm_candidate = normalize_name(row['Name'])
        else:
            norm_candidate = normalize_name_legacy(row['Name'])
        if norm_search == norm_candidate:
            player_rows.append(row)

    if not player_rows:
        return [0.0, 0.0, 0.0, 0.0, 0.0]

    # Sort by W column to ensure correct order
    player_rows_sorted = sorted(player_rows, key=lambda x: x.get('W', 0) if pd.notna(x.get('W', 0)) else 0)

    # Extract FP from each week's row
    weekly_fp = []
    for row in player_rows_sorted[:5]:  # Take first 5 weeks
        fp = row.get('FP', 0.0)
        weekly_fp.append(float(fp) if pd.notna(fp) else 0.0)

    # Pad with zeros if less than 5 weeks
    while len(weekly_fp) < 5:
        weekly_fp.append(0.0)

    return weekly_fp


def calculate_snap_metrics(snap_row: pd.Series, weekly_fp: list = None) -> Dict:
    """
    Calculate trend, consistency, and momentum from weekly snap and FP data.

    Args:
        snap_row: Row from Snaps sheet with W1-W5 snap %s
        weekly_fp: List of weekly fantasy points [W1, W2, W3, W4, W5]

    Returns:
        Dict with trend, consistency, momentum, avg_snap
    """
    # Extract weekly snap percentages (handle NaN)
    weekly_snaps = []
    for col in ['Snap %.1', 'Snap %.2', 'Snap %.3', 'Snap %.4', 'Snap %.5']:
        val = snap_row.get(col, np.nan)
        if pd.notna(val):
            weekly_snaps.append(float(val))
        else:
            weekly_snaps.append(0.0)  # Treat NaN as 0% snaps (didn't play)

    if not weekly_snaps or all(s == 0 for s in weekly_snaps):
        return {
            'trend': 0.0,
            'consistency': 0.0,
            'momentum': 0.0,
            'avg_snap': 0.0,
            'snap_w5': 0.0,
            'weekly_snaps': [0.0] * 5,
            'weekly_fp': [0.0] * 5,
            'early_fp_avg': 0.0,
            'recent_fp_avg': 0.0
        }

    # Trend: W1 → W5 snap % change (role growth)
    w1_snap = weekly_snaps[0]
    w5_snap = weekly_snaps[4]
    trend = w5_snap - w1_snap

    # Consistency: Standard deviation of snap % (role stability)
    consistency = np.std(weekly_snaps) if len(weekly_snaps) > 1 else 0.0

    # Momentum: Production-based (FP) instead of snap-based
    early_fp_avg = 0.0
    recent_fp_avg = 0.0
    if weekly_fp and len(weekly_fp) >= 5:
        # Recent 3 weeks (W3-W5) FP vs Early 2 weeks (W1-W2) FP
        early_fp_avg = np.mean(weekly_fp[:2]) if len(weekly_fp) >= 2 else 0.0
        recent_fp_avg = np.mean(weekly_fp[2:5]) if len(weekly_fp) >= 3 else 0.0
        momentum = recent_fp_avg - early_fp_avg  # Production momentum in FP
    else:
        # Fallback to snap-based momentum if FP data not available
        early_avg = np.mean(weekly_snaps[:2]) if len(weekly_snaps) >= 2 else 0.0
        recent_avg = np.mean(weekly_snaps[2:5]) if len(weekly_snaps) >= 3 else 0.0
        momentum = recent_avg - early_avg

    # Average snap % across all 5 weeks
    avg_snap = np.mean(weekly_snaps)

    return {
        'trend': round(trend, 1),
        'consistency': round(consistency, 1),
        'momentum': round(momentum, 1),
        'avg_snap': round(avg_snap, 1),
        'snap_w5': round(w5_snap, 1),
        'weekly_snaps': weekly_snaps,  # Store raw weekly data for tooltips
        'weekly_fp': weekly_fp if weekly_fp else [0.0] * 5,  # Store weekly FP for tooltips
        'early_fp_avg': round(early_fp_avg, 1) if weekly_fp else 0.0,
        'recent_fp_avg': round(recent_fp_avg, 1) if weekly_fp else 0.0
    }


def format_trend_display(trend: float) -> str:
    """Format trend for inline display with indicator."""
    if trend > 15:
        return f"⬆️{trend:+.0f}%"
    elif trend < -15:
        return f"⬇️{trend:+.0f}%"
    else:
        return f"➡️{trend:+.0f}%"


def format_consistency_display(consistency: float) -> str:
    """Format consistency for inline display."""
    if consistency < 5:
        return f"✅{consistency:.1f}"
    elif consistency < 10:
        return f"⚠️{consistency:.1f}"
    else:
        return f"❌{consistency:.1f}"


def format_momentum_display(momentum: float) -> str:
    """Format momentum for inline display (production-based, measured in FP)."""
    if momentum > 5:
        return f"🔥{momentum:+.1f}"
    elif momentum < -5:
        return f"🧊{momentum:+.1f}"
    else:
        return f"➡️{momentum:+.1f}"


def format_variance_display(variance: float) -> str:
    """Format XFP variance for inline display."""
    if variance < -5:
        return f"🎯{variance:+.1f}"  # BUY LOW (unlucky, red for good)
    elif variance > 10:
        return f"💎{variance:+.1f}"  # FADE (lucky, green for caution)
    else:
        return f"{variance:+.1f}"