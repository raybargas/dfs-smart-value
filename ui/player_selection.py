"""
Player Selection UI Component

This module implements the Streamlit UI for player selection controls,
allowing users to lock, exclude, or leave players as normal for optimization.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any
import sys
from pathlib import Path
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode

# Add parent directory to path for imports
parent_path = Path(__file__).parent.parent
sys.path.insert(0, str(parent_path))

from src.models import PlayerSelection
from src.regression_analyzer import check_regression_risk
from src.opponent_lookup import add_opponents_to_dataframe
from src.season_stats_analyzer import analyze_season_stats, format_trend_display, format_consistency_display, format_momentum_display, format_variance_display
from src.smart_value_calculator import calculate_smart_value, get_available_profiles
from src.database_models import create_session, InjuryReport
from fuzzywuzzy import fuzz

# Import Phase 2C components for Narrative Intelligence
try:
    from src.player_context_builder import PlayerContextBuilder
    NARRATIVE_INTELLIGENCE_AVAILABLE = True
except ImportError as e:
    NARRATIVE_INTELLIGENCE_AVAILABLE = False
    print(f"Warning: PlayerContextBuilder not available. Narrative Intelligence features disabled. Error: {e}")


def calculate_dfs_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate actionable DFS metrics from player data.
    
    Calculates:
    - Value: Projection / (Salary / 1000) = points per $1K
    - Position Rank: Value rank within position group
    - Leverage: Value / Ownership% (tournament play indicator)
    
    Args:
        df: DataFrame with player data (must have: projection, salary, ownership, position)
    
    Returns:
        DataFrame with added columns: value, pos_rank, leverage
    """
    df = df.copy()
    
    # Ensure opponent column exists (fill with empty string if missing)
    if 'opponent' not in df.columns:
        df['opponent'] = ''
    
    # Calculate Value (points per $1K)
    df['value'] = df['projection'] / (df['salary'] / 1000)
    
    # Calculate Position Rank (rank by value within position)
    df['pos_rank'] = df.groupby('position')['value'].rank(ascending=False, method='min').astype(int)
    
    # Calculate Leverage Score (handle edge cases)
    # Treat ownership < 1% as 1% to avoid extreme outliers
    safe_ownership = df['ownership'].apply(lambda x: max(x, 1.0) if pd.notna(x) and x > 0 else 1.0)
    df['leverage'] = df['value'] / safe_ownership
    
    # Determine leverage tier for display (using emoji for reliability)
    def get_leverage_tier(row):
        """Determine leverage indicator: 🔥 High, ⚡ Medium, • Low"""
        # Calculate position median value for comparison
        pos_median = df[df['position'] == row['position']]['value'].median()
        
        own = row['ownership'] if pd.notna(row['ownership']) else 100
        val = row['value']
        
        if own < 10 and val > pos_median:
            return '🔥'  # High leverage
        elif own < 20 and val > pos_median:
            return '⚡'  # Medium leverage
        else:
            return '•'  # Low leverage
    
    df['leverage_tier'] = df.apply(get_leverage_tier, axis=1)
    
    # Calculate 80/20 Regression Risk with detailed tooltips
    # Check each player's prior week performance
    regression_risks = []
    prior_week_points = []
    regression_tooltips = []
    
    # Also calculate leverage tooltips
    leverage_tooltips = []
    for idx, row in df.iterrows():
        # Regression analysis
        player_name = row['name']
        try:
            # Check PRIOR week data (Week 5 is prior to Week 6)
            is_at_risk, points, stats = check_regression_risk(player_name, week=5, threshold=20.0, db_path="dfs_optimizer.db")
            
            if is_at_risk and stats:
                regression_risks.append('✓')  # Checkmark indicates regression risk
                # Build detailed tooltip
                tooltip_parts = [f"⚠️ 80/20 REGRESSION RISK"]
                tooltip_parts.append(f"Week 5: {points:.1f} DK pts (20+ threshold)")
                if stats['pass_yards'] > 0:
                    tooltip_parts.append(f"Pass: {stats['pass_yards']} yds, {stats['pass_td']} TD")
                    if stats['pass_int'] > 0:
                        tooltip_parts[-1] += f", {stats['pass_int']} INT"
                if stats['rush_yards'] > 0:
                    tooltip_parts.append(f"Rush: {stats['rush_yards']} yds, {stats['rush_td']} TD")
                if stats['receptions'] > 0:
                    tooltip_parts.append(f"Rec: {stats['receptions']} rec, {stats['rec_yards']} yds, {stats['rec_td']} TD")
                tooltip_parts.append("80% of WRs scoring 20+ regress next week")
                regression_tooltips.append(" | ".join(tooltip_parts))
            else:
                regression_risks.append('')  # No checkmark = no risk or no data
                if points is not None and stats:
                    # Build tooltip for safe players
                    tooltip_parts = [f"Week 5: {points:.1f} DK pts"]
                    if stats['pass_yards'] > 0:
                        tooltip_parts.append(f"Pass: {stats['pass_yards']} yds, {stats['pass_td']} TD")
                    if stats['rush_yards'] > 0:
                        tooltip_parts.append(f"Rush: {stats['rush_yards']} yds, {stats['rush_td']} TD")
                    if stats['receptions'] > 0:
                        tooltip_parts.append(f"Rec: {stats['receptions']} rec, {stats['rec_yards']} yds, {stats['rec_td']} TD")
                    tooltip_parts.append("No regression risk (scored <20 pts)")
                    regression_tooltips.append(" | ".join(tooltip_parts))
                else:
                    regression_tooltips.append("No Week 5 data available")
            
            prior_week_points.append(points if points is not None else 0)
        except Exception as e:
            regression_risks.append('')
            regression_tooltips.append(f"Error: {str(e)[:50]}")
            prior_week_points.append(0)
        
        # Leverage tooltip (numeric score)
        pos_median = df[df['position'] == row['position']]['value'].median()
        own = row['ownership'] if pd.notna(row['ownership']) else 100
        val = row['value']
        lvg_score = row['leverage']
        
        # Determine leverage tier based on numeric score
        if lvg_score >= 0.50:
            tier = "🔥 ELITE"
            description = "Exceptional GPP opportunity - high value + very low ownership"
        elif lvg_score >= 0.30:
            tier = "⚡ STRONG"
            description = "Good GPP leverage - solid value + manageable ownership"
        elif lvg_score >= 0.15:
            tier = "✓ DECENT"
            description = "Moderate leverage - playable in tournaments"
        else:
            tier = "• LOW"
            description = "Either chalk or poor value - better for cash games"
        
        lvg_tooltip = f"{tier} LEVERAGE: {lvg_score:.2f} | Own: {own:.1f}% | Value: {val:.2f} pts/$1K (pos median: {pos_median:.2f}) | {description}"
        
        leverage_tooltips.append(lvg_tooltip)
    
    df['regression_risk'] = regression_risks
    df['prior_week_points'] = prior_week_points
    df['regression_tooltip'] = regression_tooltips
    df['leverage_tooltip'] = leverage_tooltips
    
    return df


def get_injury_data(week: int = 6) -> Dict[str, Dict[str, Any]]:
    """
    Fetch injury data from database for the given week.
    
    Args:
        week: NFL week number
        
    Returns:
        Dictionary mapping player names to injury info:
        {
            'Player Name': {
                'status': 'Q',
                'practice': 'Limited',
                'body_part': 'Hamstring',
                'description': '...'
            }
        }
    """
    try:
        session = create_session()
        
        # Query injury reports for the week
        injuries = session.query(InjuryReport).filter(
            InjuryReport.week == week
        ).all()
        
        injury_dict = {}
        for inj in injuries:
            # Skip if healthy (no injury status or explicitly "healthy")
            if not inj.injury_status or inj.injury_status.lower() in ['healthy', 'active', 'none']:
                continue
                
            injury_dict[inj.player_name] = {
                'status': inj.injury_status,
                'practice': inj.practice_status,
                'body_part': inj.body_part,
                'description': inj.description
            }
        
        session.close()
        return injury_dict
        
    except Exception as e:
        print(f"Error fetching injury data: {e}")
        return {}


def add_injury_flags_to_dataframe(df: pd.DataFrame, week: int = 6) -> pd.DataFrame:
    """
    Add injury flags to player names and create injury tooltips.
    
    Args:
        df: Player DataFrame with 'name' column
        week: NFL week number for injury data
        
    Returns:
        DataFrame with 'injury_flag', 'injury_tooltip', and modified 'name' columns
    """
    injury_data = get_injury_data(week)
    
    injury_flags = []
    injury_tooltips = []
    
    for idx, row in df.iterrows():
        player_name = row['name']
        
        # Try exact match first
        injury_info = injury_data.get(player_name)
        
        # If no exact match, try fuzzy matching
        if not injury_info:
            best_match = None
            best_score = 0
            for inj_name in injury_data.keys():
                score = fuzz.ratio(player_name.lower(), inj_name.lower())
                if score > best_score and score >= 85:  # 85% similarity threshold
                    best_score = score
                    best_match = inj_name
            
            if best_match:
                injury_info = injury_data[best_match]
        
        # Add injury flag and tooltip if found
        if injury_info:
            status = injury_info['status']
            practice = injury_info.get('practice', 'Unknown')
            body_part = injury_info.get('body_part', 'Unknown')
            
            # Create flag display (Q, D, O, IR, etc.)
            flag = f" [{status}]"
            injury_flags.append(flag)
            
            # Create detailed tooltip
            tooltip_parts = [f"⚕️ INJURY: {status}"]
            if body_part and body_part != 'Unknown':
                tooltip_parts.append(f"Body Part: {body_part}")
            if practice and practice != 'Unknown':
                tooltip_parts.append(f"Practice: {practice}")
            
            injury_tooltips.append(" | ".join(tooltip_parts))
        else:
            injury_flags.append("")
            injury_tooltips.append("")
    
    df['injury_flag'] = injury_flags
    df['injury_tooltip'] = injury_tooltips
    
    return df

def render_player_selection():
    """
    Render the player selection UI component with enhanced Excel-like table.
    
    Provides interactive table for player states, search/filter,
    bulk actions, validation warnings, and counts.
    """
    # Check if we should show loading screen
    if st.session_state.get('show_loading_screen', False):
        loading_message = st.session_state.get('loading_message', '📈 Analyzing historical trends...')
        
        # Create a centered loading screen
        st.markdown("""
        <div style="
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 60vh;
            text-align: center;
        ">
            <div style="font-size: 2rem; margin-bottom: 1rem;">📈</div>
            <div style="font-size: 1.5rem; font-weight: 600; margin-bottom: 0.5rem;">Analyzing Historical Trends</div>
            <div style="color: #707070; font-size: 1rem;">Processing player data and calculating smart values...</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Clear the loading screen flag and rerun to show actual content
        st.session_state['show_loading_screen'] = False
        st.rerun()
    # ========== SMART VALUE CONFIGURATION SIDEBAR ==========
    # Use custom CSS to make sidebar wider on desktop, responsive on mobile
    st.markdown("""
    <style>
    /* Desktop: wider sidebar */
    @media (min-width: 768px) {
        [data-testid="stSidebar"] {
            min-width: 450px;
            max-width: 450px;
        }
    }
    
    /* Mobile: allow sidebar to be fully hidden and responsive */
    @media (max-width: 767px) {
        [data-testid="stSidebar"] {
            min-width: auto;
            max-width: 100%;
        }
        
        /* Ensure sidebar can be fully closed on mobile */
        [data-testid="stSidebar"][aria-expanded="false"] {
            display: none;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Smart Value Configuration - moved to main area for responsive layout
    st.markdown("---")
    with st.expander("⚙️ Smart Value Configuration - Adjust Weights & Factors", expanded=False):
            st.markdown("""
            **Control every factor** that contributes to the Smart Value score.
            Main category weights must sum to 1.0 (100%).
            """)
            
            # Initialize session state for custom weights if not exists
            # FORCE RESET FLAG: Delete this section after first run to prevent overwriting user prefs
            if 'weights_migrated_v2' not in st.session_state:
                st.session_state['smart_value_custom_weights'] = {
                    'base': 0.15,  # UPDATED: Value matters more (was 0.10)
                    'opportunity': 0.25,  # Reduced to make room for regression
                    'trends': 0.10,
                    'risk': 0.05,
                    'matchup': 0.25,  # Reduced to make room for regression
                    'leverage': 0.20,  # Increased leverage weight
                    'regression': 0.05  # NEW: 80/20 regression component
                }
                # Delete old widget keys to force slider reset
                widget_keys = ['base_weight_slider', 'opp_weight_slider', 'trends_weight_slider', 
                              'risk_weight_slider', 'matchup_weight_slider', 'leverage_weight_slider', 'regression_weight_slider']
                for key in widget_keys:
                    if key in st.session_state:
                        del st.session_state[key]
                
                st.session_state['weights_migrated_v2'] = True
                st.rerun()
            
            if 'smart_value_custom_weights' not in st.session_state:
                st.session_state['smart_value_custom_weights'] = {
                    'base': 0.15,  # UPDATED: Value matters more (was 0.10)
                    'opportunity': 0.30,
                    'trends': 0.10,
                    'risk': 0.05,
                    'matchup': 0.30,  # INCREASED: Game environment = most predictive
                    'leverage': 0.10  # UPDATED: Reduced contrarian bias + Sweet Spot multiplier (was 0.15)
                }
            
            st.markdown("#### 🎯 Main Category Weights")
            st.caption("Adjust how much each factor influences the final score")
            
            # Base Value
            col1, col2 = st.columns([3, 1])
            with col1:
                base_weight = st.slider(
                    "Base Value",
                    min_value=0, max_value=100, 
                    value=int(st.session_state['smart_value_custom_weights']['base'] * 100),
                    step=1,
                    key='base_weight_slider',
                    help="Projection per $1K spent. Pure salary efficiency.\n\nBreakdown:\n• Value ratio (pts/$1K)\n• Ceiling boost multiplier\n• Value penalty for poor ratios"
                )
            with col2:
                st.metric("", f"{base_weight}%", label_visibility="collapsed")
            
            # Opportunity
            col1, col2 = st.columns([3, 1])
            with col1:
                # Get sub-weights for tooltip
                sub_weights = st.session_state.get('smart_value_sub_weights', {})
                opp_tgt_pct = sub_weights.get('opp_target_share', 0.60) * 100
                opp_snap_pct = sub_weights.get('opp_snap_pct', 0.30) * 100
                opp_rz_pct = sub_weights.get('opp_rz_targets', 0.10) * 100
                
                opp_weight = st.slider(
                    "Opportunity",
                    min_value=0, max_value=100,
                    value=int(st.session_state['smart_value_custom_weights']['opportunity'] * 100),
                    step=1,
                    key='opp_weight_slider',
                    help=f"Volume metrics: Snap %, Target Share, RZ Targets\n\nBreakdown:\n• Target Share: {opp_tgt_pct:.0f}%\n• Snap %: {opp_snap_pct:.0f}%\n• RZ Targets: {opp_rz_pct:.0f}%"
                )
            with col2:
                st.metric("", f"{opp_weight}%", label_visibility="collapsed")
            
            # Trends
            col1, col2 = st.columns([3, 1])
            with col1:
                # Get sub-weights for tooltip
                sub_weights = st.session_state.get('smart_value_sub_weights', {})
                trends_mom_pct = sub_weights.get('trends_momentum', 0.50) * 100
                trends_trend_pct = sub_weights.get('trends_trend', 0.30) * 100
                trends_fpg_pct = sub_weights.get('trends_fpg', 0.20) * 100
                
                trends_weight = st.slider(
                    "Trends",
                    min_value=0, max_value=100,
                    value=int(st.session_state['smart_value_custom_weights']['trends'] * 100),
                    step=1,
                    key='trends_weight_slider',
                    help=f"Momentum, role growth, recent production trajectory\n\nBreakdown:\n• Momentum (FP change): {trends_mom_pct:.0f}%\n• Trend (Snap % change): {trends_trend_pct:.0f}%\n• FP/G (Recent production): {trends_fpg_pct:.0f}%"
                )
            with col2:
                st.metric("", f"{trends_weight}%", label_visibility="collapsed")
            
            # Risk
            col1, col2 = st.columns([3, 1])
            with col1:
                # Get sub-weights for tooltip
                sub_weights = st.session_state.get('smart_value_sub_weights', {})
                risk_var_pct = sub_weights.get('risk_variance', 0.60) * 100
                risk_cons_pct = sub_weights.get('risk_consistency', 0.40) * 100
                
                risk_weight = st.slider(
                    "Risk",
                    min_value=0, max_value=100,
                    value=int(st.session_state['smart_value_custom_weights']['risk'] * 100),
                    step=1,
                    key='risk_weight_slider',
                    help=f"XFP variance, consistency (regression moved to separate component)\n\nBreakdown:\n• Variance: {risk_var_pct:.0f}%\n• Consistency: {risk_cons_pct:.0f}%"
                )
            with col2:
                st.metric("", f"{risk_weight}%", label_visibility="collapsed")
            
            # Matchup
            col1, col2 = st.columns([3, 1])
            with col1:
                matchup_weight = st.slider(
                    "Matchup",
                    min_value=0, max_value=100,
                    value=int(st.session_state['smart_value_custom_weights']['matchup'] * 100),
                    step=1,
                    key='matchup_weight_slider',
                    help="Game environment, Vegas totals, pace/script factors\n\nBreakdown:\n• Game total (Vegas)\n• Implied team total\n• Pace/script factors"
                )
            with col2:
                st.metric("", f"{matchup_weight}%", label_visibility="collapsed")
            
            # Leverage (NEW from Week 6 analysis)
            col1, col2 = st.columns([3, 1])
            with col1:
                leverage_weight = st.slider(
                    "💎 Leverage (NEW!)",
                    min_value=0, max_value=100,
                    value=int(st.session_state['smart_value_custom_weights'].get('leverage', 0.15) * 100),
                    step=1,
                    key='leverage_weight_slider',
                    help="🔥 Ceiling potential + low ownership = tournament gold! Based on Week 6 winners.\n\nBreakdown:\n• Ceiling potential (season high)\n• Ownership penalty (lower = better)\n• Value vs position median"
                )
            with col2:
                st.metric("", f"{leverage_weight}%", label_visibility="collapsed")
            
            # Regression (80/20 rule)
            col1, col2 = st.columns([3, 1])
            with col1:
                regression_weight = st.slider(
                    "⚠️ 80/20 Regression",
                    min_value=0, max_value=100,
                    value=int(st.session_state['smart_value_custom_weights'].get('regression', 0.05) * 100),
                    step=1,
                    key='regression_weight_slider',
                    help="🎯 Penalty for players who scored 20+ points last week (80% regression rate)\n\nBreakdown:\n• Prior week performance check\n• 20+ point threshold detection\n• Fixed penalty (-0.5) per occurrence"
                )
            with col2:
                st.metric("", f"{regression_weight}%", label_visibility="collapsed")
            
            # Calculate total and show status
            total = base_weight + opp_weight + trends_weight + risk_weight + matchup_weight + leverage_weight + regression_weight
            
            # Auto-normalize weights if they don't sum to 100%
            needs_normalization = abs(total - 100) > 0.1
            
            if needs_normalization:
                st.warning(f"⚠️ Weights sum to **{total:.1f}%**. Will auto-normalize to 100% when applied.")
                # Show what normalized weights will be
                with st.expander("Preview normalized weights", expanded=False):
                    st.caption(f"Original → Normalized:")
                st.caption(f"• Base: {base_weight:.1f}% → {(base_weight/total)*100:.1f}%")
                st.caption(f"• Opportunity: {opp_weight:.1f}% → {(opp_weight/total)*100:.1f}%")
                st.caption(f"• Trends: {trends_weight:.1f}% → {(trends_weight/total)*100:.1f}%")
                st.caption(f"• Risk: {risk_weight:.1f}% → {(risk_weight/total)*100:.1f}%")
                st.caption(f"• Matchup: {matchup_weight:.1f}% → {(matchup_weight/total)*100:.1f}%")
                st.caption(f"• 💎 Leverage: {leverage_weight:.1f}% → {(leverage_weight/total)*100:.1f}%")
                st.caption(f"• ⚠️ Regression: {regression_weight:.1f}% → {(regression_weight/total)*100:.1f}%")
            else:
                st.success(f"✅ Weights sum to **{total:.0f}%**")
            
            # Build new weights dict (normalized)
            if needs_normalization and total > 0:
                # Normalize to sum to 1.0 (convert percentages back to decimals)
                new_weights = {
                    'base': (base_weight / total),
                    'opportunity': (opp_weight / total),
                    'trends': (trends_weight / total),
                    'risk': (risk_weight / total),
                    'matchup': (matchup_weight / total),
                    'leverage': (leverage_weight / total),
                    'regression': (regression_weight / total)
                }
            else:
                new_weights = {
                    'base': base_weight / 100,
                    'opportunity': opp_weight / 100,
                    'trends': trends_weight / 100,
                    'risk': risk_weight / 100,
                    'matchup': matchup_weight / 100,
                    'leverage': leverage_weight / 100,
                    'regression': regression_weight / 100
                }
            
            # Apply & Recalculate button
            st.markdown("---")
            if st.button("🔄 Apply & Recalculate", use_container_width=True, type="primary"):
                st.session_state['smart_value_custom_weights'] = new_weights
                # Clear cached smart value data to force recalculation (including enriched_player_data)
                if 'smart_value_calculated' in st.session_state:
                    del st.session_state['smart_value_calculated']
                if 'smart_value_data' in st.session_state:
                    del st.session_state['smart_value_data']
                if 'enriched_player_data' in st.session_state:
                    del st.session_state['enriched_player_data']
                if 'dfs_metrics_calculated' in st.session_state:
                    del st.session_state['dfs_metrics_calculated']
                if 'dfs_metrics_data' in st.session_state:
                    del st.session_state['dfs_metrics_data']
                st.success("✅ Configuration applied!")
                st.rerun()
            
            # Reset to default button
            if st.button("↩️ Reset to Balanced (Updated)", use_container_width=True):
                st.session_state['smart_value_custom_weights'] = {
                    'base': 0.15,  # UPDATED: Value matters more
                    'opportunity': 0.30,
                    'trends': 0.10,
                    'risk': 0.05,
                    'matchup': 0.30,  # INCREASED: Game environment = most predictive
                    'leverage': 0.10  # UPDATED: Less contrarian bias + Sweet Spot multiplier
                }
                # Clear cached data (including enriched_player_data that optimization config uses)
                if 'smart_value_calculated' in st.session_state:
                    del st.session_state['smart_value_calculated']
                if 'smart_value_data' in st.session_state:
                    del st.session_state['smart_value_data']
                if 'enriched_player_data' in st.session_state:
                    del st.session_state['enriched_player_data']
                if 'dfs_metrics_calculated' in st.session_state:
                    del st.session_state['dfs_metrics_calculated']
                if 'dfs_metrics_data' in st.session_state:
                    del st.session_state['dfs_metrics_data']
                
                # CRITICAL: Delete widget keys so sliders reset to new values
                widget_keys = ['base_weight_slider', 'opp_weight_slider', 'trends_weight_slider', 
                              'risk_weight_slider', 'matchup_weight_slider', 'leverage_weight_slider', 'regression_weight_slider']
                for key in widget_keys:
                    if key in st.session_state:
                        del st.session_state[key]
                
                st.rerun()
            
            # Advanced sub-weight configuration
            st.markdown("---")
            st.markdown("#### 🔬 Advanced: Sub-Factor Weights")
            with st.expander("⚙️ Fine-tune sub-factors", expanded=False):
                st.caption("These control how each category combines its inputs")
                
                # Initialize sub-weights in session state
                if 'smart_value_sub_weights' not in st.session_state:
                    st.session_state['smart_value_sub_weights'] = {
                        # Opportunity sub-weights (WR/TE)
                        'opp_target_share': 0.60,
                        'opp_snap_pct': 0.30,
                        'opp_rz_targets': 0.10,
                        # Trends sub-weights
                        'trends_momentum': 0.50,
                        'trends_trend': 0.30,
                        'trends_fpg': 0.20,
                        # Risk sub-weights
                        'risk_regression': 0.50,
                        'risk_variance': 0.30,
                        'risk_consistency': 0.20
                    }
                
                st.markdown("**Opportunity** (WR/TE breakdown)")
                st.caption("How Opportunity score is built for WR/TE positions")
                
                opp_tgt = st.slider(
                    "Target Share",
                    0.0, 1.0, st.session_state['smart_value_sub_weights']['opp_target_share'],
                    0.05, key='opp_tgt_slider',
                    help="Weight for target share in Opportunity score"
                )
                opp_snap = st.slider(
                    "Snap %",
                    0.0, 1.0, st.session_state['smart_value_sub_weights']['opp_snap_pct'],
                    0.05, key='opp_snap_slider',
                    help="Weight for snap % in Opportunity score"
                )
                opp_rz = st.slider(
                    "RZ Targets",
                    0.0, 1.0, st.session_state['smart_value_sub_weights']['opp_rz_targets'],
                    0.05, key='opp_rz_slider',
                    help="Weight for red zone targets in Opportunity score"
                )
                opp_total = opp_tgt + opp_snap + opp_rz
                if abs(opp_total - 1.0) > 0.001:
                    st.warning(f"Opportunity sub-weights: {opp_total*100:.0f}% (should be 100%)")
                
                st.markdown("---")
                st.markdown("**Trends** breakdown")
                st.caption("How Trends score combines momentum, trend, and production")
                
                trends_mom = st.slider(
                    "Momentum (FP change)",
                    0.0, 1.0, st.session_state['smart_value_sub_weights']['trends_momentum'],
                    0.05, key='trends_mom_slider',
                    help="Weight for production momentum (recent vs early)"
                )
                trends_trend = st.slider(
                    "Trend (Snap % change)",
                    0.0, 1.0, st.session_state['smart_value_sub_weights']['trends_trend'],
                    0.05, key='trends_trend_slider',
                    help="Weight for role expansion (snap % W1→W5)"
                )
                trends_fpg = st.slider(
                    "FP/G (Recent production)",
                    0.0, 1.0, st.session_state['smart_value_sub_weights']['trends_fpg'],
                    0.05, key='trends_fpg_slider',
                    help="Weight for recent fantasy points per game"
                )
                trends_total = trends_mom + trends_trend + trends_fpg
                if abs(trends_total - 1.0) > 0.001:
                    st.warning(f"Trends sub-weights: {trends_total*100:.0f}% (should be 100%)")
                
                st.markdown("---")
                st.markdown("**Risk** breakdown")
                st.caption("How Risk adjustments are balanced (regression moved to separate component)")
                
                risk_var = st.slider(
                    "Variance (Luck)",
                    0.0, 1.0, st.session_state['smart_value_sub_weights']['risk_variance'],
                    0.05, key='risk_var_slider',
                    help="Weight for XFP variance (unlucky = bonus)"
                )
                risk_cons = st.slider(
                    "Consistency (Role stability)",
                    0.0, 1.0, st.session_state['smart_value_sub_weights']['risk_consistency'],
                    0.05, key='risk_cons_slider',
                    help="Weight for snap % consistency bonus"
                )
                risk_total = risk_var + risk_cons
                if abs(risk_total - 1.0) > 0.001:
                    st.warning(f"Risk sub-weights: {risk_total*100:.0f}% (should be 100%)")
                
                # Normalize and store sub-weights
                st.session_state['smart_value_sub_weights'] = {
                    'opp_target_share': opp_tgt / opp_total if opp_total > 0 else 0.60,
                    'opp_snap_pct': opp_snap / opp_total if opp_total > 0 else 0.30,
                    'opp_rz_targets': opp_rz / opp_total if opp_total > 0 else 0.10,
                    'trends_momentum': trends_mom / trends_total if trends_total > 0 else 0.50,
                    'trends_trend': trends_trend / trends_total if trends_total > 0 else 0.30,
                    'trends_fpg': trends_fpg / trends_total if trends_total > 0 else 0.20,
                    'risk_variance': risk_var / risk_total if risk_total > 0 else 0.60,
                    'risk_consistency': risk_cons / risk_total if risk_total > 0 else 0.40
                }
                
                st.success("✅ **Sub-weights are ACTIVE!** These control how each main category combines its inputs. Click 'Apply & Recalculate' below to use your custom sub-weights.")
            
            # Position-Specific Weight Overrides
            st.markdown("---")
            st.markdown("#### 🎯 Position-Specific Overrides")
            st.caption("Customize weights for specific positions (e.g., RBs value volume more)")
            
            # Initialize position weights in session state
            if 'position_specific_weights' not in st.session_state:
                st.session_state['position_specific_weights'] = {}
            
            # Position selector
            positions = ['QB', 'RB', 'WR', 'TE', 'DST']
            
            for pos in positions:
                with st.expander(f"⚙️ {pos} Custom Weights", expanded=False):
                    st.caption(f"Override weights specifically for {pos} position")
                    
                    # Initialize this position's weights if not exists
                    if pos not in st.session_state['position_specific_weights']:
                        st.session_state['position_specific_weights'][pos] = {}
                    
                    # Enable/disable override for this position
                    use_override = st.checkbox(
                        f"Use custom weights for {pos}",
                        value=bool(st.session_state['position_specific_weights'].get(pos)),
                        key=f'use_override_{pos}'
                    )
                    
                    if use_override:
                        st.markdown(f"**{pos}-Specific Weights:**")
                        
                        # Position-specific sliders
                        pos_base = st.slider(
                            f"Base ({pos})",
                            0.0, 1.0,
                            st.session_state['position_specific_weights'][pos].get('base', new_weights['base']),
                            0.05,
                            key=f'pos_base_{pos}',
                            help=f"Base value weight for {pos} players"
                        )
                        
                        pos_opp = st.slider(
                            f"Opportunity ({pos})",
                            0.0, 1.0,
                            st.session_state['position_specific_weights'][pos].get('opportunity', new_weights['opportunity']),
                            0.05,
                            key=f'pos_opp_{pos}',
                            help=f"Opportunity weight for {pos} - {'Snap % focus' if pos == 'RB' else 'Targets + Snaps' if pos in ['WR', 'TE'] else 'Usage proxy'}"
                        )
                        
                        pos_trends = st.slider(
                            f"Trends ({pos})",
                            0.0, 1.0,
                            st.session_state['position_specific_weights'][pos].get('trends', new_weights['trends']),
                            0.05,
                            key=f'pos_trends_{pos}',
                            help=f"Trends weight for {pos}"
                        )
                        
                        pos_risk = st.slider(
                            f"Risk ({pos})",
                            0.0, 1.0,
                            st.session_state['position_specific_weights'][pos].get('risk', new_weights['risk']),
                            0.05,
                            key=f'pos_risk_{pos}',
                            help=f"Risk adjustment weight for {pos}"
                        )
                        
                        pos_matchup = st.slider(
                            f"Matchup ({pos})",
                            0.0, 1.0,
                            st.session_state['position_specific_weights'][pos].get('matchup', new_weights['matchup']),
                            0.05,
                            key=f'pos_matchup_{pos}',
                            help=f"Matchup quality weight for {pos}"
                        )
                        
                        # Calculate and show total for this position
                        pos_total = pos_base + pos_opp + pos_trends + pos_risk + pos_matchup
                        
                        if abs(pos_total - 1.0) > 0.001:
                            st.warning(f"⚠️ {pos} weights: {pos_total*100:.1f}% (will auto-normalize)")
                        else:
                            st.success(f"✅ {pos} weights: {pos_total*100:.0f}%")
                        
                        # Store the position-specific weights
                        if pos_total > 0:
                            st.session_state['position_specific_weights'][pos] = {
                                'base': pos_base / pos_total if abs(pos_total - 1.0) > 0.001 else pos_base,
                                'opportunity': pos_opp / pos_total if abs(pos_total - 1.0) > 0.001 else pos_opp,
                                'trends': pos_trends / pos_total if abs(pos_total - 1.0) > 0.001 else pos_trends,
                                'risk': pos_risk / pos_total if abs(pos_total - 1.0) > 0.001 else pos_risk,
                                'matchup': pos_matchup / pos_total if abs(pos_total - 1.0) > 0.001 else pos_matchup
                            }
                    else:
                        # Remove override for this position
                        if pos in st.session_state['position_specific_weights']:
                            st.session_state['position_specific_weights'][pos] = {}
            
            # Show current formula breakdown
            st.markdown("---")
            st.markdown("##### 📐 Current Formula")
            
            # Show global formula
            st.markdown("**Global (Default):**")
            st.code(f"""
Smart Value = 
  Base     ({new_weights['base']*100:.0f}%) × [Proj/$1K]
+ Opp      ({new_weights['opportunity']*100:.0f}%) × [Volume]
+ Trends   ({new_weights['trends']*100:.0f}%) × [Momentum]
+ Risk     ({new_weights['risk']*100:.0f}%) × [Adjustments]
+ Matchup  ({new_weights['matchup']*100:.0f}%) × [Environment]
            """.strip(), language="text")
            
            # Show position-specific formulas if any
            active_overrides = {pos: weights for pos, weights in st.session_state.get('position_specific_weights', {}).items() if weights}
            if active_overrides:
                st.markdown("**Position Overrides:**")
                for pos, pos_weights in active_overrides.items():
                    st.markdown(f"*{pos}:*")
                    st.code(f"""
  Base: {pos_weights['base']*100:.0f}% | Opp: {pos_weights['opportunity']*100:.0f}% | Trends: {pos_weights['trends']*100:.0f}% | Risk: {pos_weights['risk']*100:.0f}% | Matchup: {pos_weights['matchup']*100:.0f}%
                    """.strip(), language="text")
    
    # Material Icons setup (simple and clean)
    st.markdown("""
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <style>
    .material-icons {
        font-family: 'Material Icons';
        font-weight: normal;
        font-style: normal;
        font-size: 20px;
        display: inline-block;
        line-height: 1;
        text-transform: none;
        letter-spacing: normal;
        word-wrap: normal;
        white-space: nowrap;
        direction: ltr;
        vertical-align: middle;
    }
    .material-icons.md-18 { font-size: 18px; }
    .material-icons.md-24 { font-size: 24px; }
    .material-icons.md-36 { font-size: 36px; }
    .material-icons.md-48 { font-size: 48px; }
    </style>
    """, unsafe_allow_html=True)
    
    # Apply compact styles
    from src.styles import get_base_styles, get_card_styles
    st.markdown(get_base_styles(), unsafe_allow_html=True)
    st.markdown(get_card_styles(), unsafe_allow_html=True)
    
    # ULTRA-COMPACT Header: Single line with inline instructions
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.5rem 0; margin-bottom: 0.75rem;">
        <div style="display: flex; align-items: baseline; gap: 1rem;">
            <h2 style="margin: 0; font-size: 1.5rem; font-weight: 700; display: inline;">
                🏈 <span class="gradient-text">Player Pool Selection</span>
            </h2>
            <span style="color: #707070; font-size: 0.875rem;">Pool = include | Lock = must-start</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Check if player data exists
    if 'player_data' not in st.session_state or st.session_state['player_data'] is None:
        st.warning("⚠️ No player data found. Please go back to upload data first.")
        if st.button("← Back to Data Upload"):
            st.session_state['page'] = 'data_ingestion'
            st.rerun()
        return
    
    df = st.session_state['player_data'].copy()
    
    # Add opponent data from Vegas lines lookup
    if 'opponent_lookup' in st.session_state and st.session_state['opponent_lookup']:
        opponent_map = st.session_state['opponent_lookup']
        df = add_opponents_to_dataframe(df, opponent_map)
    
    # MIGRATION: Force recalculation of DFS metrics to populate REG column
    # This ensures regression risk data is calculated with the correct Week 5 query
    # CRITICAL: Must also clear season_stats and smart_value caches because they overwrite df
    if 'dfs_metrics_migrated_reg_fix' not in st.session_state:
        if 'dfs_metrics_calculated' in st.session_state:
            del st.session_state['dfs_metrics_calculated']
        if 'dfs_metrics_data' in st.session_state:
            del st.session_state['dfs_metrics_data']
        if 'season_stats_enriched' in st.session_state:
            del st.session_state['season_stats_enriched']
        if 'season_stats_data' in st.session_state:
            del st.session_state['season_stats_data']
        if 'smart_value_calculated' in st.session_state:
            del st.session_state['smart_value_calculated']
        if 'smart_value_data' in st.session_state:
            del st.session_state['smart_value_data']
        st.session_state['dfs_metrics_migrated_reg_fix'] = True
    
    # Calculate DFS metrics (Value, Position Rank, Leverage)
    if 'dfs_metrics_calculated' not in st.session_state:
        with st.spinner("📊 Calculating DFS metrics..."):
            df = calculate_dfs_metrics(df)
            st.session_state['dfs_metrics_data'] = df
            st.session_state['dfs_metrics_calculated'] = True
    else:
        # Use cached metrics data
        df = st.session_state['dfs_metrics_data'].copy()
        # Re-apply opponent lookup even for cached data
        if 'opponent_lookup' in st.session_state and st.session_state['opponent_lookup']:
            opponent_map = st.session_state['opponent_lookup']
            df = add_opponents_to_dataframe(df, opponent_map)
    
    # Enrich with 5-week season stats (Trend, Consistency, Momentum, Variance)
    # FORCE RECALCULATION: Check if we need to migrate to new ceiling calculation
    force_recalc = 'ceiling_migrated_v2' not in st.session_state
    
    if 'season_stats_enriched' not in st.session_state or force_recalc:
        with st.spinner("📈 Analyzing historical trends..."):
            df = analyze_season_stats(df, excel_path="2025 Stats thru week 5.xlsx")
            st.session_state['season_stats_data'] = df
            st.session_state['season_stats_enriched'] = True
            st.session_state['ceiling_migrated_v2'] = True
            
            # Clear Smart Value cache to force recalc with new ceilings
            if 'smart_value_calculated' in st.session_state:
                del st.session_state['smart_value_calculated']
            if 'smart_value_data' in st.session_state:
                del st.session_state['smart_value_data']
    else:
        # Use cached season stats data
        df = st.session_state['season_stats_data'].copy()
        # Re-apply opponent lookup
        if 'opponent_lookup' in st.session_state and st.session_state['opponent_lookup']:
            opponent_map = st.session_state['opponent_lookup']
            df = add_opponents_to_dataframe(df, opponent_map)
    
    # Calculate Smart Value Score (multi-factor value calculation)
    if 'smart_value_calculated' not in st.session_state:
        with st.spinner("🧠 Calculating Smart Value Scores..."):
            # Use custom weights from session state if available
            custom_weights = st.session_state.get('smart_value_custom_weights', None)
            position_weights = st.session_state.get('position_specific_weights', None)
            sub_weights = st.session_state.get('smart_value_sub_weights', None)
            
            # Filter out empty position overrides
            if position_weights:
                position_weights = {pos: weights for pos, weights in position_weights.items() if weights}
            
            # Get current week for Vegas lines lookup
            current_week = st.session_state.get('current_week', 6)
            df = calculate_smart_value(df, profile='balanced', custom_weights=custom_weights, position_weights=position_weights, sub_weights=sub_weights, week=current_week)
            st.session_state['smart_value_data'] = df
            st.session_state['smart_value_calculated'] = True
    else:
        # Use cached smart value data
        df = st.session_state['smart_value_data'].copy()
        # Re-apply opponent lookup for cached data
        if 'opponent_lookup' in st.session_state and st.session_state['opponent_lookup']:
            opponent_map = st.session_state['opponent_lookup']
            df = add_opponents_to_dataframe(df, opponent_map)
    
    # Add injury flags to player names
    current_week = st.session_state.get('current_week', 6)
    df = add_injury_flags_to_dataframe(df, week=current_week)
    
    # Verify required columns exist before storing
    required_cols = ['position', 'name', 'salary', 'projection', 'team']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.error(f"⚠️ Missing required columns: {missing_cols}. Please reload your data.")
        return
    
    # Store enriched data (with opponents + DFS metrics + season stats + smart value + injury flags) for optimizer
    st.session_state['enriched_player_data'] = df.copy()
    
    # Initialize selections if not exists
    if 'selections' not in st.session_state:
        st.session_state['selections'] = {idx: PlayerSelection.NORMAL.value for idx in df.index}
    
    selections = st.session_state['selections']
    
    # Validate minimum roster requirements for DFS lineup
    def check_roster_requirements():
        """
        Check if selected players meet minimum DFS roster requirements.
        Returns: (is_valid, error_message)
        """
        # Get selected player indices (EXCLUDED or LOCKED)
        selected_indices = [idx for idx, state in selections.items() 
                          if state in [PlayerSelection.EXCLUDED.value, PlayerSelection.LOCKED.value]]
        
        if not selected_indices:
            return False, "No players selected. Please add players to your pool."
        
        # Count positions for selected players
        selected_players = df.loc[selected_indices]
        position_counts = selected_players['position'].value_counts().to_dict()
        
        # DFS roster minimum requirements (DraftKings format)
        requirements = {
            'QB': 1,
            'RB': 2,
            'WR': 3,
            'TE': 1,
            'DST': 1
        }
        
        missing = []
        for pos, min_count in requirements.items():
            current_count = position_counts.get(pos, 0)
            if current_count < min_count:
                missing.append(f"{pos} ({current_count}/{min_count})")
        
        if missing:
            return False, f"Missing positions: {', '.join(missing)}"
        
        return True, ""
    
    # ULTRA-COMPACT Controls: Single row with Smart Value slider, Deselect, and Continue
    # Note: Continue button rendered AFTER validation below
    col1, col2, col3, col4 = st.columns([2.5, 1, 1, 1.5])
    
    with col1:
        st.caption("🎯 Position Smart Value Threshold")
        
        # Use form to prevent slider from triggering reruns
        with st.form(key="threshold_form", clear_on_submit=False):
            smart_threshold = st.slider(
                "",
                min_value=0,
                max_value=100,
                value=st.session_state.get('last_threshold', 0),
                step=5,
                help="Filters by Position SV (best within position). Move slider to set threshold, then click button to apply",
                label_visibility="collapsed"
            )
            
            # Submit button - always enabled (threshold check happens on submit)
            submitted = st.form_submit_button(
                "✓ Select Players",
                use_container_width=True
            )
        
        # Handle form submission - submitted and smart_threshold ARE accessible after form
        if submitted:
            if smart_threshold > 0:
                # Store threshold for next run
                st.session_state['last_threshold'] = smart_threshold
                
                # Select players at or above threshold
                for idx in df.index:
                    player_smart_value = df.loc[idx, 'smart_value'] if 'smart_value' in df.columns else 0
                    if player_smart_value >= smart_threshold:
                        st.session_state['selections'][idx] = PlayerSelection.EXCLUDED.value  # Excluded means selected in pool
                    else:
                        st.session_state['selections'][idx] = PlayerSelection.NORMAL.value
                
                # Store to player_selections as well for navigation
                st.session_state['player_selections'] = st.session_state['selections'].copy()
                
                # Show success message
                selected_count = sum(1 for s in st.session_state['selections'].values() if s != PlayerSelection.NORMAL.value)
                st.success(f"✅ Selected {selected_count} players with Position SV ≥ {smart_threshold}")
                
                # CRITICAL: Rerun to update AgGrid with new selections
                st.rerun()
            else:
                st.warning("⚠️ Please move the slider above 0 to select players")
    
    with col2:
        st.markdown('<div style="padding-top: 1.5rem;">', unsafe_allow_html=True)
        if st.button("✕ Clear", use_container_width=True, key="deselect_all", help="Deselect all players"):
            st.session_state['selections'] = {idx: PlayerSelection.NORMAL.value for idx in df.index}
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div style="padding-top: 1.5rem;">', unsafe_allow_html=True)
        # Position filter shortcut (optional - can expand later)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Col4 (Continue button) rendered AFTER validation - see below line 954
    
    # Re-read selections from session state (in case form/buttons updated it)
    selections = st.session_state['selections']
    
    # Validate roster requirements AFTER selections are updated
    is_valid, error_msg = check_roster_requirements()
    
    # NOW render Continue button with CORRECT validation
    with col4:
        st.markdown('<div style="padding-top: 1.5rem;">', unsafe_allow_html=True)
        # Quick navigation to optimization config - disabled if requirements not met
        if is_valid:
            if st.button("▶️ Continue", use_container_width=True, type="primary", key="quick_next"):
                # Store selections for next page
                st.session_state['player_selections'] = selections
                st.session_state['page'] = 'optimization'
                st.rerun()
        else:
            # Disabled button with tooltip
            st.button(
                "▶️ Continue", 
                use_container_width=True, 
                type="primary", 
                key="quick_next_disabled",
                disabled=True,
                help=f"⚠️ {error_msg}\n\n✅ Minimum requirements:\n• 1 QB\n• 2 RB\n• 3 WR\n• 1 TE\n• 1 DST"
            )
            # Show visible error message
            st.caption(f"⚠️ {error_msg}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Count locked players
    locked_count = sum(1 for s in selections.values() if s == PlayerSelection.LOCKED.value)
    in_pool_count = sum(1 for s in selections.values() if s != PlayerSelection.NORMAL.value)
    
    # Debug: Show position counts
    selected_indices = [idx for idx, state in selections.items() 
                       if state in [PlayerSelection.EXCLUDED.value, PlayerSelection.LOCKED.value]]
    if selected_indices:
        selected_df = df.loc[selected_indices]
        pos_counts = selected_df['position'].value_counts().to_dict()
        pos_summary = " | ".join([f"{pos}: {count}" for pos, count in sorted(pos_counts.items())])
    else:
        pos_summary = "None selected"
    
    # ULTRA-COMPACT player stats bar - inline, minimal padding
    st.markdown(f"""
    <div style="background: #2C2C2C; color: #D3D3D3; padding: 0.3rem 0.75rem; border-radius: 6px; margin: 0.5rem 0 0.75rem 0; font-size: 0.875rem; text-align: center; border: 1px solid #444;">
        <strong>{len(df)}</strong> players · <strong style="color: #FF6B35;">{in_pool_count}</strong> in pool · 🔒 <strong>{locked_count}</strong> locked<br>
        <span style="font-size: 0.75rem; color: #999;">Selected: {pos_summary}</span>
        </div>
    """, unsafe_allow_html=True)
    
    # Prepare data for AgGrid
    display_data = []
    for idx, row in df.iterrows():
        current_selection = selections.get(idx, PlayerSelection.NORMAL.value)
        is_in_pool = current_selection != PlayerSelection.NORMAL.value
        is_locked = current_selection == PlayerSelection.LOCKED.value
        
        # Check for warning flags
        is_wr_regression = False
        is_ceiling_concern = False
        flag_tooltip = []
        
        # Flag 1: 80/20 WR Regression Risk (WRs only who scored 20+ last week)
        if row['position'] == 'WR' and row.get('regression_risk') == '✓':
            is_wr_regression = True
            flag_tooltip.append("⚠️ WR REGRESSION RISK: Scored 20+ last week, 80% chance of regression")
        
        # Flag 2: 3.5X Salary Rule (RB/WR/TE only - not QBs)
        # Rule: Each player needs to score 3.5 × (salary/1000) to be worth their cost
        # Flag when their season ceiling (best game) is below this threshold
        if row['position'] in ['RB', 'WR', 'TE']:
            salary = row['salary']
            required_points = (salary / 1000) * 3.5  # Points needed to be worth the cost
            season_ceiling = row.get('season_ceiling', 0)  # Best game this season
            
            if season_ceiling > 0 and season_ceiling < required_points:
                is_ceiling_concern = True
                flag_tooltip.append(f"💰 3.5X RISK: Needs {required_points:.1f} pts to justify ${salary:,} salary, but season ceiling is only {season_ceiling:.1f} pts (never shown ability to hit this threshold - excludes 98% from optimal lineups)")
        
        # Combine flags
        has_warning = is_wr_regression or is_ceiling_concern
        warning_tooltip = " | ".join(flag_tooltip) if flag_tooltip else ""
        
        # Add injury tooltip (flag removed from name display)
        injury_tooltip = row.get('injury_tooltip', '')
        
        # Combine injury tooltip with warning tooltip
        combined_tooltip = warning_tooltip
        if injury_tooltip:
            if combined_tooltip:
                combined_tooltip = f"{injury_tooltip} | {combined_tooltip}"
            else:
                combined_tooltip = injury_tooltip
        
        # Check for regression risk (80/20 rule)
        has_regression_risk = bool(row.get('regression_risk', ''))  # Convert checkmark to boolean
        regression_tooltip = row.get('regression_tooltip', '')
        
        # Build player name tooltip (injury + warnings + regression)
        player_tooltip = row['name']
        tooltip_parts = []
        if injury_tooltip:
            tooltip_parts.append(injury_tooltip)
        if regression_tooltip:
            tooltip_parts.append(regression_tooltip)
        if warning_tooltip:
            tooltip_parts.append(warning_tooltip)
        
        if tooltip_parts:
            player_tooltip = " | ".join(tooltip_parts)
        
        # Prepare player data with DFS metrics + Season stats + Warning flags + Injury flags
        player_data = {
            '_index': idx,  # Hidden column to track original index
            '_warning_flag': has_warning,  # Hidden flag for row styling
            '_warning_tooltip': combined_tooltip,  # Combined tooltip (injury + warnings)
            '_regression_risk': has_regression_risk,  # Hidden boolean for cell styling
            'Pool': is_in_pool,
            'Lock': is_locked,
            'Player': row['name'],
            'Player_Tooltip': player_tooltip,  # Combined tooltip for player name
            'Pos': row['position'],
            'Salary': row['salary'],
            'Proj': row['projection'],
            'Own%': row['ownership'] if 'ownership' in row and pd.notna(row['ownership']) else 0,
            'Value': row['value'] if 'value' in row else 0,
            'Global SV': row['smart_value_global'] if 'smart_value_global' in row else row.get('smart_value', 0),
            'Pos SV': row['smart_value'] if 'smart_value' in row else row.get('value', 0),
            'Smart_Value_Tooltip': row.get('smart_value_tooltip', 'Smart Value calculation pending'),
            'Rank': f"{row['position']}{int(row['pos_rank'])}" if 'pos_rank' in row else "-",
            'Lvg': row['leverage'] if 'leverage' in row else 0,
            'Lvg_Tooltip': row['leverage_tooltip'] if 'leverage_tooltip' in row else '',
            'Team': row['team'],
            'Opp': row['opponent'] if 'opponent' in row and pd.notna(row['opponent']) else "-",
            # Vegas data
            'Game Total': row.get('game_total', 0),
            'ITT': row.get('team_itt', 0),
            # Season stats (5-week data)
            'Trend': format_trend_display(row.get('season_trend', 0)),
            'Cons': format_consistency_display(row.get('season_cons', 0)),
            'Cons_Tooltip': row.get('season_cons_tooltip', 'No data available'),
            'Mom': format_momentum_display(row.get('season_mom', 0)),
            'Mom_Tooltip': row.get('season_mom_tooltip', 'No data available'),
            'Snap': row.get('season_snap', 0),
            'FP/G': row.get('season_fpg', 0),
            'Var': format_variance_display(row.get('season_var', 0)),
            'Tgt%': row.get('season_tgt', 0) if row['position'] in ['WR', 'TE'] else None,
            'RZ Tgt': row.get('season_eztgt', 0) if row['position'] in ['WR', 'TE'] else None
        }
        
        display_data.append(player_data)
    
    grid_df = pd.DataFrame(display_data)
    
    # Configure AgGrid
    gb = GridOptionsBuilder.from_dataframe(grid_df)
    
    # Custom cell renderer for Player column to color names red if regression risk
    player_cell_renderer = JsCode("""
    class PlayerCellRenderer {
        init(params) {
            this.eGui = document.createElement('div');
            this.eGui.innerText = params.value;
            // Check if player has regression risk (80/20 rule)
            if (params.data._regression_risk) {
                this.eGui.style.color = 'red';
                this.eGui.style.fontWeight = '600';
            }
        }
        getGui() {
            return this.eGui;
        }
    }
    """)
    
    # Configure columns
    gb.configure_column("_index", hide=True)  # Hide the index tracking column
    gb.configure_column("_warning_flag", hide=True)  # Hide warning flag (used for row styling)
    gb.configure_column("_warning_tooltip", hide=True)  # Hide warning tooltip
    gb.configure_column("_regression_risk", hide=True)  # Hide regression risk boolean
    gb.configure_column("Player_Tooltip", hide=True)  # Hide player tooltip (used by cellRenderer)
    
    gb.configure_column("Pool", 
                        header_name="Pool",
                        editable=True,
                        width=80,
                        pinned='left',
                        suppressHeaderMenuButton=True,
                        headerTooltip="PLAYER POOL - Check this box to include the player in your available pool for lineup generation. Unchecked players will be completely excluded from consideration. Use this to filter out players you don't want in any lineup.")
    
    gb.configure_column("Lock", 
                        header_name="Lock",
                        editable=True,
                        width=90,
                        pinned='left',
                        suppressHeaderMenuButton=True,
                        headerTooltip="LOCK PLAYER - Check this to GUARANTEE this player appears in EVERY generated lineup. Use for must-have plays, captain/MVP picks in showdown, or core plays you're building stacks around. Locking too many players reduces lineup diversity. Note: Checking Lock automatically adds the player to your Pool.")
    
    # Filter configuration with larger panel and filter-first menu tabs
    filter_config = {
        "buttons": ["reset", "apply"],
        "closeOnApply": True
    }
    
    # Menu tabs configuration - filter first, then column options
    menu_tabs = ['filterMenuTab', 'generalMenuTab']
    
    gb.configure_column("Player", 
                        header_name="Player",
                        filter="agTextColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=200,
                        pinned='left',
                        cellRenderer=player_cell_renderer,
                        tooltipField='Player_Tooltip',
                        headerTooltip="PLAYER NAME - Red text indicates 80/20 REGRESSION RISK (scored 20+ fantasy points last week). Hover for details on injury status, regression risk, and warnings.")
    
    gb.configure_column("Pos", 
                        header_name="Pos",
                        filter="agTextColumnFilter",  # Text filter (works in Community edition)
                        filterParams={
                            "buttons": ["reset", "apply"],
                            "closeOnApply": True,
                            "debounceMs": 200,
                            "filterOptions": ["contains", "equals", "startsWith", "endsWith"],
                            "defaultOption": "equals"
                        },
                        menuTabs=menu_tabs,
                        width=80,
                        pinned='left')
    
    gb.configure_column("Salary", 
                        header_name="Salary",
                        type=["numericColumn"],
                        valueFormatter="value ? '$' + value.toLocaleString() : ''",
                        filter="agNumberColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=120,
                        pinned='left',
                        headerTooltip="PLAYER SALARY - DraftKings salary cap cost. You have $50,000 total to build a lineup. Higher salaries don't always mean better value - use the Value column to find efficiency. Mix high-salary studs with mid-tier values and punt plays to optimize your lineup.")
    
    gb.configure_column("Proj", 
                        header_name="Proj",
                        type=["numericColumn"],
                        valueFormatter="value ? value.toFixed(1) : ''",
                        filter="agNumberColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=90,
                        pinned='left',
                        headerTooltip="PROJECTED POINTS - Expected fantasy points for this player. Higher projections = higher ceiling, but watch the salary! A 25-point projection at $9K might be worse value than 20 points at $6K. Always cross-reference with the Value column to find salary inefficiencies.")
    
    # DFS Metrics columns with detailed tooltips
    # Hide "Value" column - replaced by Smart Value
    gb.configure_column("Value", hide=True)
    
    # PHASE 4.5: Smart Value (Global) - Primary ranking metric
    gb.configure_column("Global SV", 
                        header_name="Smart Value",  # Renamed from "Global SV" for simplicity
                        type=["numericColumn"],
                        valueFormatter="value ? value.toFixed(0) : ''",  # Show as whole number (0-100 scale)
                        filter="agNumberColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=120,
                        cellStyle={
                            'fontWeight': 'bold',
                            'textAlign': 'center',
                            'backgroundColor': '#1a3d5c',  # Dark blue background
                            'color': '#60a5fa'  # Light blue text
                        },
                        tooltipField="Smart_Value_Tooltip",
                        headerTooltip="SMART VALUE SCORE 🧠 - Ranks players ACROSS ALL POSITIONS for cross-position comparison. Combines value, opportunity, leverage, matchup, and game script intelligence. A QB with 90 Smart Value is comparable to an RB with 90 Smart Value in actual tournament impact. Higher = Better overall DFS value. Sort by this column to find true tournament-winning plays. NOTE: Position-specific Smart Value (used for filters) is calculated separately but hidden from this view.")
    
    # Hide Position SV - only needed for backend filtering, not user display
    gb.configure_column("Pos SV", hide=True)
    
    # Hide "Rank" column - no longer needed with Smart Value
    gb.configure_column("Rank", hide=True)
    
    gb.configure_column("Own%", 
                        header_name="Own%",
                        type=["numericColumn"],
                        valueFormatter="value ? value.toFixed(1) + '%' : ''",
                        filter="agNumberColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=90,
                        pinned='left',
                        headerTooltip="PROJECTED OWNERSHIP - The percentage of lineups expected to roster this player. High ownership (>20%) = 'chalk' play everyone is on. Low ownership (<10%) = contrarian/leverage opportunity. In cash games, chalk is often safe. In tournaments (GPPs), you need differentiation through lower-owned players to climb the leaderboard when they hit.")
    
    gb.configure_column("Lvg", 
                        header_name="Lvg",
                        type=["numericColumn"],
                        valueFormatter="value ? value.toFixed(2) : ''",
                        filter="agNumberColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=80,
                        cellStyle={'textAlign': 'center', 'fontWeight': '500'},
                        tooltipField="Lvg_Tooltip",
                        headerTooltip="LEVERAGE SCORE - Calculated as Value ÷ Ownership% (e.g., 3.0 pts/$1K ÷ 10% own = 0.30 leverage). Higher scores = better tournament opportunity. FORMULA: A 0.50+ leverage score means excellent GPP upside (low-owned + good value). 0.30-0.50 = solid leverage. <0.30 = chalk or poor value. Strategy: Target high leverage (0.40+) for GPP differentiation. Sort by this column to find the best contrarian plays with value.")
    
    # Hide tooltip columns (they're just data sources for tooltips)
    gb.configure_column("Lvg_Tooltip", hide=True)
    gb.configure_column("Cons_Tooltip", hide=True)
    gb.configure_column("Mom_Tooltip", hide=True)
    gb.configure_column("Smart_Value_Tooltip", hide=True)
    
    gb.configure_column("Team", 
                        header_name="Team",
                        filter="agTextColumnFilter",
                        filterParams={
                            "buttons": ["reset", "apply"],
                            "closeOnApply": True,
                            "debounceMs": 200,
                            "filterOptions": ["contains", "equals", "startsWith"],
                            "defaultOption": "contains"
                        },
                        menuTabs=menu_tabs,
                        width=90)
    
    gb.configure_column("Opp", 
                        header_name="Opp",
                        filter="agTextColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=90,
                        headerTooltip="OPPONENT - The team this player is facing this week. '@' symbol = away game (e.g., '@BUF' = playing at Buffalo). No '@' = home game. Use this to identify favorable/unfavorable matchups, stack game environments, and avoid tough defensive matchups.")
    
    # === VEGAS DATA COLUMNS ===
    gb.configure_column("Game Total", 
                        header_name="Total",
                        type=["numericColumn"],
                        valueFormatter="value ? value.toFixed(1) : '-'",
                        filter="agNumberColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=85,
                        headerTooltip="VEGAS GAME TOTAL - Combined projected points for both teams (e.g., 50.5 = high-scoring game). 50+ = Shootout (target these for ceiling). 45-50 = Above average. 40-45 = Average. <40 = Low-scoring (avoid for GPP). Strategy: Game total is the #1 predictor of fantasy scoring. Stack players from high-total games for max ceiling.")
    
    gb.configure_column("ITT", 
                        header_name="ITT",
                        type=["numericColumn"],
                        valueFormatter="value ? value.toFixed(1) : '-'",
                        filter="agNumberColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=75,
                        headerTooltip="IMPLIED TEAM TOTAL - Vegas projected points for THIS team only (e.g., 27.5 = expected to score 27.5 pts). 28+ = Elite offensive environment. 24-28 = Good. 20-24 = Average. <20 = Avoid. Strategy: ITT identifies which SIDE of a high total to target. A 50-point total could be 28-22 (target the 28 side) or 25-25 (both sides viable).")
    
    # === SEASON STATS COLUMNS (5-Week Analysis) ===
    gb.configure_column("Trend", 
                        header_name="Trend",
                        filter="agTextColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=95,
                        cellStyle={'textAlign': 'center', 'fontSize': '0.9rem'},
                        headerTooltip="USAGE TREND (W1→W5) - Snap % change from Week 1 to Week 5. ⬆️ +15%+ = Role expanding (ascending player, BUY). ⬇️ -15%+ = Role shrinking (descending, FADE). ➡️ = Stable role. Strategy: Target ⬆️ players before ownership catches up. Example: ⬆️+25% means player went from 50% to 75% snaps - clear role expansion.")
    
    gb.configure_column("Cons", 
                        header_name="Cons",
                        filter="agTextColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=90,
                        cellStyle={'textAlign': 'center', 'fontSize': '0.9rem'},
                        tooltipField="Cons_Tooltip",
                        headerTooltip="CONSISTENCY - Snap % volatility (Standard Deviation across 5 weeks). ✅ <5.0 = Stable, reliable role (CASH PLAY - safe floor). ⚠️ 5-10 = Moderate volatility. ❌ >10 = Highly volatile role (GPP ONLY - boom/bust). Strategy: Use ✅ players in cash games for predictable floors. Use ❌ players in tournaments for ceiling upside. HOVER OVER CELL to see week-by-week snap % breakdown.")
    
    gb.configure_column("Mom", 
                        header_name="Mom",
                        filter="agTextColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=90,
                        cellStyle={'textAlign': 'center', 'fontSize': '0.9rem'},
                        tooltipField="Mom_Tooltip",
                        headerTooltip="MOMENTUM - Production trajectory comparing Recent 3 weeks (W3-W5) vs Early 2 weeks (W1-W2) fantasy points. 🔥 +5 FP+ = HEATING UP! Production increasing, ride the hot hand (e.g., career games). 🧊 -5 FP+ = COOLING DOWN - Production declining, fade or reduce exposure. ➡️ = STEADY production. Strategy: Target 🔥 players coming off big games before ownership catches up. Ignore 🧊 players with inflated ownership due to old production. HOVER OVER CELL to see weekly FP breakdown and early vs recent averages.")
    
    gb.configure_column("Snap", 
                        header_name="Snap",
                        type=["numericColumn"],
                        valueFormatter="value ? value.toFixed(1) + '%' : ''",
                        filter="agNumberColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=85,
                        headerTooltip="AVG SNAP % - 5-week average snap %. >70% = Workhorse/featured player (high opportunity). 50-70% = Timeshare/rotation (moderate). <50% = Limited role (volatile). Strategy: Higher snaps = more chances to score. Combine with efficiency metrics to find high-floor plays.")
    
    gb.configure_column("FP/G", 
                        header_name="FP/G",
                        type=["numericColumn"],
                        valueFormatter="value ? value.toFixed(1) : ''",
                        filter="agNumberColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=85,
                        headerTooltip="SEASON AVG POINTS - Fantasy points per game average over 5 weeks (Weeks 1-5). Shows true production level, not single-game variance. Higher = proven scorer. Cross-reference with Value to find salary inefficiencies. Example: 25.0 FP/G = elite production tier.")
    
    gb.configure_column("Var", 
                        header_name="Var",
                        filter="agTextColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=90,
                        cellStyle={'textAlign': 'center', 'fontSize': '0.9rem', 'fontWeight': 'bold'},
                        headerTooltip="LUCK INDICATOR (XFP Variance) - 5-week Actual FP minus Expected FP. 🎯 Negative (red) = UNLUCKY, BUY LOW (positive regression coming - they've been producing but not scoring). 💎 Positive (green) = LUCKY, FADE (negative regression likely - scoring more than production suggests). Neutral = fair results. Strategy: Target 🎯 players in tournaments as contrarian value plays. Example: 🎯-15.0 = 15 pts below expectation, due for positive correction.")
    
    gb.configure_column("Tgt%", 
                        header_name="Tgt%",
                        type=["numericColumn"],
                        valueFormatter="value ? value.toFixed(1) + '%' : ''",
                        filter="agNumberColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=85,
                        headerTooltip="TARGET SHARE - 5-week avg % of team targets (WR/TE only). >25% = Elite volume (WR1/TE1). 15-25% = Strong volume (WR2). <15% = Limited volume. Strategy: Volume is king in PPR formats. High target share = high floor. Stack with good matchups for ceiling.")
    
    gb.configure_column("RZ Tgt", 
                        header_name="RZ Tgt",
                        type=["numericColumn"],
                        filter="agNumberColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=80,
                        cellStyle={'textAlign': 'center'},
                        headerTooltip="RED ZONE TARGETS - Total end zone targets over 5 weeks (WR/TE only). 5+ = Elite TD upside. 3-4 = Strong. 1-2 = Moderate. 0 = TD dependent on big plays. Strategy: Red zone volume is the #1 predictor of TDs. Stack RZ targets in tournaments for ceiling games.")
    
    # Grid options with default sort by Value (descending)
    gb.configure_grid_options(
        domLayout='normal',
        enableRangeSelection=True,
        suppressRowClickSelection=True,
        enableFilter=True,  # Enable filtering
        floatingFilter=False  # Show filter icon in headers (not floating filters)
    )
    
    # Set default sort by Value (descending)
    gb.configure_default_column(sortable=True)
    
    # Build grid options
    grid_options = gb.build()
    
    # Add row styling for warning flags (light orange/pink for flagged players)
    grid_options['getRowStyle'] = JsCode("""
    function(params) {
        if (params.data._warning_flag === true) {
            return {
                'backgroundColor': 'rgba(255, 165, 0, 0.15)',  // Light orange/pink
                'borderLeft': '3px solid #FFA500'  // Solid orange left border
            };
        }
        return null;
    }
    """)
    
    # Add default sort to Value column
    grid_options['columnDefs'] = [
        {**col, 'sort': 'desc'} if col.get('field') == 'Value' else col
        for col in grid_options['columnDefs']
    ]
    
    # Custom CSS for dark theme and enhanced filter panels
    custom_css = {
        ".ag-theme-streamlit": {
            "--ag-background-color": "#1a1a1a",
            "--ag-odd-row-background-color": "#222",
            "--ag-header-background-color": "#2a2a2a",
            "--ag-foreground-color": "#e0e0e0",
            "--ag-border-color": "#333",
            "--ag-row-hover-color": "#2a2a2a",
            "--ag-header-foreground-color": "#e0e0e0",
        },
        # Make filter panels larger and better spaced
        ".ag-menu": {
            "min-width": "350px !important",
            "width": "auto !important"
        },
        ".ag-filter": {
            "padding": "15px !important",
            "min-width": "320px !important"
        },
        ".ag-filter-body-wrapper": {
            "padding": "10px !important"
        },
        ".ag-set-filter-list": {
            "min-height": "250px !important",
            "max-height": "400px !important"
        },
        ".ag-filter-condition": {
            "margin-bottom": "12px !important"
        },
        ".ag-input-field-input": {
            "padding": "8px !important",
            "font-size": "14px !important"
        },
        ".ag-standard-button": {
            "padding": "8px 16px !important",
            "margin": "8px 4px !important"
        },
        # Tab spacing
        ".ag-tabs-header": {
            "padding": "8px !important"
        },
        ".ag-tab": {
            "padding": "10px 16px !important",
            "margin-right": "4px !important"
        }
    }
    
    # Display AgGrid
    grid_response = AgGrid(
        grid_df,
        gridOptions=grid_options,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        update_mode=GridUpdateMode.MODEL_CHANGED,
        fit_columns_on_grid_load=False,
        theme='streamlit',
        height=500,
        width='100%',
        allow_unsafe_jscode=True,
        custom_css=custom_css,
        key='player_grid'
    )
    
    # Update selections based on grid response
    if grid_response and 'data' in grid_response:
        updated_df = grid_response['data']
        needs_rerun = False
        
        # Update selections for all rows
        # Logic: Checking Lock auto-checks Pool (and forces a rerun to show it)
        for _, row in updated_df.iterrows():
            idx = row['_index']
            is_in_pool = row['Pool']
            is_locked = row['Lock']
            
            # If Lock is checked but Pool isn't, we need to auto-check Pool
            if is_locked and not is_in_pool:
                is_in_pool = True
                needs_rerun = True  # Trigger rerun to update UI
            
            # Update selection state
            if is_locked:
                # Locked players are automatically in pool
                selections[idx] = PlayerSelection.LOCKED.value
            elif is_in_pool:
                # In pool but not locked - use EXCLUDED as "eligible" marker
                selections[idx] = PlayerSelection.EXCLUDED.value
            else:
                # Not in pool at all
                selections[idx] = PlayerSelection.NORMAL.value
        
        # Rerun if we auto-checked any Pool checkboxes
        if needs_rerun:
            st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Add quick insights section
    with st.expander("💡 Understanding Your DFS Metrics", expanded=False):
        st.markdown("""
        **Value Score**: Points per $1,000 of salary. Higher is better.
        - >3.0: Excellent value
        - 2.5-3.0: Good value  
        - <2.5: Below average value
        
        **Position Rank**: Shows your player's value rank within their position (e.g., "QB3" = 3rd best value among QBs)
        
        **Leverage (Lvg)**: Tournament play indicator based on ownership and value:
        - 🔥 **High**: Low ownership (<10%) + above-median value = great contrarian play
        - ⚡ **Medium**: Low ownership (<20%) + above-median value = potential leverage
        - • **Low**: High ownership or below-median value
        
        **80/20 Regression Risk (Reg)**: Players at high risk of regression based on prior week performance:
        - ⚠️ **Warning**: Player scored 20+ DK points last week - 80% chance of regression (lower score this week)
        - ✓ **Safe**: Player found in prior week data but scored <20 points
        - **Blank**: No prior week data available
        
        **Strategy Tips**:
        - Sort by Value to find the best bang for your buck
        - Look for 🔥 leverage plays in tournaments for differentiation
        - **Fade ⚠️ regression candidates in cash games** - they're statistically likely to underperform
        - In GPPs, regression candidates can be contrarian if ownership is high due to recency bias
        - Balance high-value chalk plays with low-ownership gems
        """)
    
    # ULTRA-COMPACT Bottom Navigation - single row
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 4])
    
    with col1:
        if st.button("⬅️ Back", use_container_width=True, key="back_btn", help="Back to Narrative Intelligence"):
            st.session_state['page'] = 'narrative_intelligence'
            st.rerun()
    
    with col2:
        # Apply same validation as top navigation button
        if is_valid:
            if st.button("▶️ Continue to Optimization", type="primary", use_container_width=True, key="continue_btn2"):
                # Store selections for next page
                st.session_state['player_selections'] = selections
                st.session_state['page'] = 'optimization'
                st.rerun()
        else:
            # Disabled button with tooltip
            st.button(
                "▶️ Continue to Optimization", 
                type="primary", 
                use_container_width=True, 
                key="continue_btn_disabled2",
                disabled=True,
                help=f"⚠️ {error_msg}\n\n✅ Minimum requirements:\n• 1 QB\n• 2 RB\n• 3 WR\n• 1 TE\n• 1 DST"
            )