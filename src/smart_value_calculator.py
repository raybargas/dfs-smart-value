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
        
        # Apply boost: base_raw * (1 + boost)
        # Example (Phase 1): Boutte with 2.52x ratio → 0.38 boost → 38% increase
        # Example (Phase 4.6): Gainwell with 1.89x ratio BUT 9.8 proj → 0.0 boost → BLOCKED
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
    Calculate RISK score component (variance/luck, consistency) with configurable sub-weights.
    
    Uses:
    - XFP Variance (luck indicator) - bonus for unlucky players, penalty for lucky
    - Consistency (snap % volatility) - bonus for stable roles
    
    NOTE: Regression Risk (80/20 rule) moved to separate 'regression' component
    
    Args:
        df: Player DataFrame
        weight: Weight for this component (default 0.05)
        sub_weights: Optional dict with keys 'risk_variance', 'risk_consistency'
                    Defaults to {0.60, 0.40} if not provided
    
    Returns:
        DataFrame with 'risk_score' column
    """
    # Default sub-weights if not provided (regression removed)
    if sub_weights is None:
        sub_weights = {
            'risk_variance': 0.60,
            'risk_consistency': 0.40
        }
    
    # Extract sub-weights
    var_weight = sub_weights.get('risk_variance', 0.60)
    cons_weight = sub_weights.get('risk_consistency', 0.40)
    df['risk_score'] = 0.0
    
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
        
        # Build Vegas lookup: team -> {game_total, itt, spread, win_prob}
        # PHASE 3: Added spread + win probability for game script analysis
        # Create reverse lookup: full name -> abbreviation
        full_to_abbrev = {v: k for k, v in TEAM_ABBREV_TO_FULL.items()}
        
        vegas_map = {}
        for line in vegas_lines:
            home_spread = line.home_spread if line.home_spread else 0.0
            away_spread = line.away_spread if line.away_spread else 0.0
            
            # Calculate win probability from spread
            # Formula: win_prob = 0.5 + (spread / 14)
            # Example: -7 spread (7-point favorite) = 0.5 + (-7/14) = 0.0 (wait, that's wrong)
            # Correct: -7 spread means HOME is favored, so home_win_prob = 0.5 + (7/14) = 0.75
            home_win_prob = 0.5 + (abs(home_spread) / 14) if home_spread < 0 else 0.5 - (home_spread / 14)
            away_win_prob = 1.0 - home_win_prob
            
            home_data = {
                'game_total': line.total if line.total else 45.0,
                'itt': line.home_itt if line.home_itt else 22.5,
                'spread': home_spread,
                'win_prob': home_win_prob
            }
            away_data = {
                'game_total': line.total if line.total else 45.0,
                'itt': line.away_itt if line.away_itt else 22.5,
                'spread': away_spread,
                'win_prob': away_win_prob
            }
            
            # Store using BOTH full name and abbreviation
            vegas_map[line.home_team] = home_data
            vegas_map[line.away_team] = away_data
            
            # Also store by abbreviation if full name is recognized
            home_abbrev = full_to_abbrev.get(line.home_team)
            away_abbrev = full_to_abbrev.get(line.away_team)
            if home_abbrev:
                vegas_map[home_abbrev] = home_data
            if away_abbrev:
                vegas_map[away_abbrev] = away_data
        
        # Map Vegas data to players (now works with both abbreviations and full names)
        df['game_total'] = df['team'].map(lambda t: vegas_map.get(t, {}).get('game_total', 45.0))
        df['team_itt'] = df['team'].map(lambda t: vegas_map.get(t, {}).get('itt', 22.5))
        df['team_spread'] = df['team'].map(lambda t: vegas_map.get(t, {}).get('spread', 0.0))
        df['team_win_prob'] = df['team'].map(lambda t: vegas_map.get(t, {}).get('win_prob', 0.5))
        
        # PHASE 3: GAME SCRIPT-AWARE MATCHUP SCORE
        # Position-specific game script logic based on Week 6 analysis
        # Rico Dowdle (RB, 35.5% own, favored) = 36.9 pts (positive script)
        # Puka Nacua (WR, 30.8% own, neutral) = 4.8 pts (no script advantage)
        
        # Normalize game total (range typically 38-56)
        game_total_norm = (df['game_total'] - 38) / (56 - 38)
        game_total_norm = game_total_norm.clip(0, 1)
        
        # Normalize ITT by position (different scoring expectations)
        itt_norm = min_max_scale_by_position(df, 'team_itt')
        
        # PHASE 3: Calculate position-specific game script scores
        def calculate_game_script_bonus(row):
            """
            PHASE 3: Position-specific game script intelligence.
            
            RBs: Want positive script (leading/favored) → more carries, clock management
            WRs/TEs: Want high volume (high total) OR negative script (trailing) → more passes
            QBs: Want pure volume (high total) → more plays, more fantasy pts
            DST: Want positive script (leading) → more sacks, turnovers
            """
            position = row.get('position', '').upper()
            win_prob = row['team_win_prob']
            total = row['game_total']
            
            # Normalize volume (game total 40-55 range)
            volume_score = (total - 40) / 15
            volume_score = max(0, min(1, volume_score))
            
            if position == 'RB':
                # RBs want positive game script (leading/favored = more carries)
                # 60% win prob weight, 40% volume
                script_score = (win_prob * 0.6) + (volume_score * 0.4)
                
            elif position in ['WR', 'TE']:
                # WRs/TEs want high volume OR negative script (trailing = passing)
                # Prefer volume over script (70/30 split)
                negative_script = 1.0 - win_prob  # Trailing teams pass more
                script_score = (volume_score * 0.7) + (negative_script * 0.3)
                
            elif position == 'QB':
                # QBs want pure volume (high total = more plays)
                script_score = volume_score
                
            elif position == 'DST':
                # DST wants positive script (leading = opponent passing, more sacks)
                script_score = win_prob
                
            else:
                # Default: neutral
                script_score = 0.5
            
            return script_score
        
        # Apply game script bonus (0-1 scale)
        df['game_script_bonus'] = df.apply(calculate_game_script_bonus, axis=1)
        
        # Combined matchup score with game script intelligence
        # 40% game total (ceiling environment)
        # 30% ITT (team scoring expectation)
        # 30% game script bonus (position-specific advantage)
        matchup_raw = (game_total_norm * 0.4) + (itt_norm * 0.3) + (df['game_script_bonus'] * 0.3)
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
    
    # PHASE 2: CONTEXT-AWARE OWNERSHIP DISCOUNT
    # Philosophy: "Differentiate good chalk from trap chalk"
    # Week 6 showed: Rico Dowdle (35.5% own, 36.9 pts) = justified chalk
    #                Puka Nacua (30.8% own, 4.8 pts) = trap chalk
    # 
    # NEW: Chalk (25%+) gets analyzed for value ratio + matchup quality
    #      If elite value (>3.5 pts/$1K) + elite matchup (>0.75) = "forced chalk" (reward)
    #      Otherwise = "trap chalk" (penalize)
    #
    # Ownership Tiers:
    #   < 8%:  2.5x - Ultra-contrarian (risky dart throws, slight penalty)
    #   8-15%: 3.0x - OPTIMAL leverage zone (best risk/reward)
    #   15-25%: 2.0x - Popular but still good leverage
    #   25%+:  CONTEXT-DEPENDENT - analyze value + matchup
    df['ownership_pct'] = df['ownership'].clip(lower=1.0)  # Min 1% to avoid divide by zero
    
    # Calculate value ratio (pts per $1K) for chalk analysis
    df['value_ratio'] = df['projection'] / (df['salary'] / 1000)
    
    # Calculate matchup quality score (0-1 scale) for chalk analysis
    if 'game_total' in df.columns:
        matchup_quality = (df['game_total'] - 38) / (56 - 38)
        matchup_quality = matchup_quality.clip(0, 1)
    else:
        matchup_quality = 0.5  # Neutral if no data
    
    def contextual_ownership_discount(row):
        """
        PHASE 2: Context-aware ownership discount with chalk intelligence.
        
        Week 6 Analysis:
        - Rico Dowdle: 35.5% own, 3.12 pts/$1K, good game → 36.9 pts (justified chalk)
        - Puka Nacua: 30.8% own, 2.80 pts/$1K, avg game → 4.8 pts (trap chalk)
        """
        own = row['ownership_pct']
        value_ratio = row['value_ratio']
        matchup = matchup_quality.loc[row.name] if hasattr(matchup_quality, 'loc') else 0.5
        
        # Base sweet spot logic (unchanged for <25% ownership)
        if 8.0 <= own <= 15.0:
            return 3.0  # Optimal leverage zone
        elif own < 8.0:
            return 2.5  # Ultra-contrarian
        elif own <= 25.0:
            return 2.0  # Popular but acceptable
        
        # PHASE 2: Chalk analysis (25%+ ownership)
        # Check if player DESERVES chalk (high value + elite matchup)
        if own > 25.0:
            # "Forced chalk" detection: elite value + elite matchup
            if value_ratio > 3.5 and matchup > 0.75:
                return 1.5  # REWARD justified chalk (don't fade elite plays)
            # Good value but not elite matchup (or vice versa)
            elif value_ratio > 3.0 or matchup > 0.7:
                return 1.0  # Neutral (neither reward nor punish)
            # Trap chalk: high ownership but no justification
            else:
                return 0.8  # PENALIZE trap chalk (fade opportunity)
        
        return 1.0  # Default neutral
    
    df['own_discount'] = df.apply(contextual_ownership_discount, axis=1)
    
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


def calculate_regression_score(df: pd.DataFrame, weight: float) -> pd.DataFrame:
    """
    Calculate REGRESSION score component (80/20 rule penalty).
    
    Applies penalty to players who scored 20+ fantasy points the previous week.
    Based on the 80/20 rule: "80% of players who scored 20+ regress next week"
    
    Args:
        df: Player DataFrame with 'regression_risk' column
        weight: Weight for this component (default 0.05)
    
    Returns:
        DataFrame with 'regression_score' column
    """
    df['regression_score'] = 0.0
    
    # Apply regression penalty (if available)
    if 'regression_risk' in df.columns:
        # -0.5 for regression warning, 0 otherwise
        # Check for both '⚠️' (tooltip format) and '✓' (UI format)
        regression_adjustment = df['regression_risk'].apply(
            lambda x: -0.5 if isinstance(x, str) and ('⚠️' in x or '✓' in x) else 0
        )
        df['regression_score'] = regression_adjustment * weight
    
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
    
    Formula: Smart Value = BASE + OPPORTUNITY + TRENDS + RISK + MATCHUP + LEVERAGE + REGRESSION - CHALK_PENALTY
    
    NEW (Week 6 Analysis):
    - LEVERAGE: Rewards ceiling potential + low ownership (De'Von Achane effect)
    - CHALK_PENALTY: Punishes high ownership in bad matchups (Puka Nacua trap)
    - REGRESSION: 80/20 rule penalty (separate from risk component)
    
    Args:
        df: Player DataFrame with required columns (projection, salary, position, etc.)
        profile: Weight profile to use ('balanced', 'cash', 'gpp', 'custom')
        custom_weights: Optional dict of custom weights. If provided, overrides profile.
                       Should contain: 'base', 'opportunity', 'trends', 'risk', 'matchup', 'leverage', 'regression'
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
        - regression_score: 80/20 regression component
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
        df['regression_score'] = 0.0
        
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
            pos_df = calculate_regression_score(pos_df, pos_weights.get('regression', 0.05))
            
            # Update the main dataframe for this position
            for col in ['base_score', 'opp_score', 'trends_score', 'risk_score', 'matchup_score', 'leverage_score', 'regression_score']:
                df.loc[pos_mask, col] = pos_df[col]
    else:
        # Calculate uniformly across all positions
        df = calculate_base_score(df, weights['base'])
        df = calculate_opportunity_score(df, weights['opportunity'], sub_weights)
        df = calculate_trends_score(df, weights['trends'], sub_weights)
        df = calculate_risk_score(df, weights['risk'], sub_weights)
        df = calculate_matchup_score(df, weights['matchup'], week)
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
        df['regression_score'] +  # NEW: 80/20 regression component
        df['chalk_penalty']  # Negative values reduce score
    )
    
    # PHASE 4.5: Calculate BOTH Position-Specific AND Global Smart Value
    # 
    # Smart Value serves two different purposes:
    # 1. POSITION Smart Value: For filtering/comparison within position (current system)
    # 2. GLOBAL Smart Value: For cross-position ranking/narrative (new system)
    
    # Scale to 0-100 for intuitive interpretation
    # Use POSITION-SPECIFIC min-max scaling so each position has its own 0-100 range
    # This prevents QBs from being compressed by RB/WR dominance
    # Rationale: You're comparing QBs to QBs, RBs to RBs (different roster slots)
    
    if 'position' in df.columns:
        # Store position-specific min/max for tooltip calculation
        df['_pos_min'] = df.groupby('position')['smart_value_raw'].transform('min')
        df['_pos_max'] = df.groupby('position')['smart_value_raw'].transform('max')
        
        # Calculate position-specific 0-100 scores
        
        # FIX: Use transform() instead of apply() + reset_index() to preserve index alignment
        def scale_position_transform(group):
            group_min = group.min()
            group_max = group.max()
            
            if group_max > group_min:
                return ((group - group_min) / (group_max - group_min)) * 100
            else:
                # If all scores in position are the same, set to 50
                return pd.Series([50.0] * len(group), index=group.index)
        
        # Use transform() which preserves the original DataFrame index
        df['smart_value'] = df.groupby('position', group_keys=False)['smart_value_raw'].transform(scale_position_transform)
    else:
        # Fallback: global scaling if no position column
        df['_pos_min'] = df['smart_value_raw'].min()
        df['_pos_max'] = df['smart_value_raw'].max()
        
        if df['_pos_max'].iloc[0] > df['_pos_min'].iloc[0]:
            df['smart_value'] = ((df['smart_value_raw'] - df['_pos_min']) / (df['_pos_max'] - df['_pos_min'])) * 100
        else:
            df['smart_value'] = 50.0
    
    # PHASE 4.5: Calculate GLOBAL Smart Value (cross-position comparison)
    # This normalizes across ALL positions for narrative/ranking purposes
    # Use cases: Elite Plays, cross-position comparisons, tournament strategy
    
    global_min = df['smart_value_raw'].min()
    global_max = df['smart_value_raw'].max()
    
    if global_max > global_min:
        df['smart_value_global'] = ((df['smart_value_raw'] - global_min) / (global_max - global_min)) * 100
    else:
        df['smart_value_global'] = 50.0
    
    # Round both scores for cleaner display
    df['smart_value'] = df['smart_value'].round(1)
    df['smart_value_global'] = df['smart_value_global'].round(1)
    
    # Validate Position SV consistency (simplified check)
    def validate_position_sv_consistency(df):
        """
        Verify that Position SV rankings match Global SV rankings within each position.
        """
        for position in df['position'].unique():
            pos_df = df[df['position'] == position].sort_values('smart_value_global', ascending=False)
            
            if len(pos_df) < 2:
                continue
                
            # Check if Position SV is also descending
            pos_sv_values = pos_df['smart_value'].tolist()
            
            # Check for ranking mismatches
            for i in range(len(pos_sv_values) - 1):
                if pos_sv_values[i] < pos_sv_values[i+1]:
                    return False, f"Position {position}: Ranking mismatch detected"
        
        return True, "Position SV rankings are consistent"
    
    # Run validation
    is_consistent, message = validate_position_sv_consistency(df)
    if not is_consistent:
        print(f"🚨 CRITICAL BUG: {message}")
    
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
            f"Position Smart Value: {row['smart_value']:.1f}/100\n"
            f"Global Smart Value: {row['smart_value_global']:.1f}/100\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 Position SV: Best {row.get('position', 'player')} in pool\n"
            f"💡 Global SV: Best overall (cross-position)\n"
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

