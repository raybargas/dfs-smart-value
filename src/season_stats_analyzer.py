"""
Season Stats Analyzer - Comprehensive 5-Week Analysis
Extracts actionable DFS insights from cumulative season data (Weeks 1-5)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from fuzzywuzzy import fuzz
import os


def normalize_name(name: str) -> str:
    """Normalize player name for matching."""
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
    norm_search = normalize_name(player_name)
    
    # Collect all matching rows with their scores
    matches = []
    
    for idx, row in stats_df.iterrows():
        norm_candidate = normalize_name(row['Name'])
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


def get_weekly_fp_data(player_name: str, snaps_df: pd.DataFrame) -> list:
    """
    Extract weekly FP data for a player from all their rows (W=1 to W=5).
    
    Args:
        player_name: Player name to match
        snaps_df: Full Snaps DataFrame with all weeks
    
    Returns:
        List of weekly FP values [W1_FP, W2_FP, W3_FP, W4_FP, W5_FP]
    """
    norm_search = normalize_name(player_name)
    
    # Find all rows for this player
    player_rows = []
    for idx, row in snaps_df.iterrows():
        norm_candidate = normalize_name(row['Name'])
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
            'snap_w5': 0.0
        }
    
    # Trend: W1 → W5 snap % change (role growth)
    w1_snap = weekly_snaps[0]
    w5_snap = weekly_snaps[4]
    trend = w5_snap - w1_snap
    
    # Consistency: Standard deviation of snap % (role stability)
    consistency = np.std(weekly_snaps) if len(weekly_snaps) > 1 else 0.0
    
    # Momentum: Production-based (FP) instead of snap-based
    # This captures "hot hands" like career games
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


def analyze_season_stats(
    player_df: pd.DataFrame,
    excel_path: str = "2025 Stats thru week 5.xlsx"
) -> pd.DataFrame:
    """
    Enrich player DataFrame with comprehensive 5-week season stats.
    
    Adds columns:
    - season_trend: Snap % change W1→W5
    - season_cons: Snap % consistency (STD)
    - season_mom: Momentum (Recent vs Early snaps)
    - season_snap: Average snap % over 5 weeks
    - season_fpg: Fantasy points per game
    - season_var: XFP variance (Actual - Expected)
    - season_tgt: Target share % (WR/TE only)
    - season_eztgt: Red zone targets (WR/TE only)
    
    Args:
        player_df: DataFrame with player roster (must have 'name' column)
        excel_path: Path to season stats Excel file
    
    Returns:
        Enriched DataFrame with season stats columns
    """
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
                
                # Calculate season ceiling (best game)
                weekly_fp = snap_metrics['weekly_fp']
                max_fp = max(weekly_fp) if weekly_fp else 0.0
                player_df.at[idx, 'season_ceiling'] = round(float(max_fp), 1)
                
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

