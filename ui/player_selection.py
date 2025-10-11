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
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

# Add parent directory to path for imports
parent_path = Path(__file__).parent.parent
sys.path.insert(0, str(parent_path))

from src.models import PlayerSelection
from src.regression_analyzer import check_regression_risk
from src.opponent_lookup import add_opponents_to_dataframe
from src.season_stats_analyzer import analyze_season_stats, format_trend_display, format_consistency_display, format_momentum_display, format_variance_display
from src.smart_value_calculator import calculate_smart_value, get_available_profiles

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
            is_at_risk, points, stats = check_regression_risk(player_name, week=5, threshold=20.0, db_path="dfs_optimizer.db")
            
            if is_at_risk and stats:
                regression_risks.append('⚠️')
                # Build detailed tooltip
                tooltip_parts = [f"Week 5: {points:.1f} DK pts"]
                if stats['pass_yards'] > 0:
                    tooltip_parts.append(f"Pass: {stats['pass_yards']} yds, {stats['pass_td']} TD")
                    if stats['pass_int'] > 0:
                        tooltip_parts[-1] += f", {stats['pass_int']} INT"
                if stats['rush_yards'] > 0:
                    tooltip_parts.append(f"Rush: {stats['rush_yards']} yds, {stats['rush_td']} TD")
                if stats['receptions'] > 0:
                    tooltip_parts.append(f"Rec: {stats['receptions']} rec, {stats['rec_yards']} yds, {stats['rec_td']} TD")
                tooltip_parts.append("⚠️ 80% likely to regress")
                regression_tooltips.append(" | ".join(tooltip_parts))
            elif points is not None and stats:
                regression_risks.append('✓')
                # Build tooltip for safe players
                tooltip_parts = [f"Week 5: {points:.1f} DK pts"]
                if stats['pass_yards'] > 0:
                    tooltip_parts.append(f"Pass: {stats['pass_yards']} yds, {stats['pass_td']} TD")
                if stats['rush_yards'] > 0:
                    tooltip_parts.append(f"Rush: {stats['rush_yards']} yds, {stats['rush_td']} TD")
                if stats['receptions'] > 0:
                    tooltip_parts.append(f"Rec: {stats['receptions']} rec, {stats['rec_yards']} yds, {stats['rec_td']} TD")
                tooltip_parts.append("✓ Safe - No regression risk")
                regression_tooltips.append(" | ".join(tooltip_parts))
            else:
                regression_risks.append('')
                regression_tooltips.append("No Week 5 data available")
            
            prior_week_points.append(points if points is not None else 0)
        except Exception as e:
            regression_risks.append('')
            regression_tooltips.append(f"Error: {str(e)[:50]}")
            prior_week_points.append(0)
        
        # Leverage tooltip
        pos_median = df[df['position'] == row['position']]['value'].median()
        own = row['ownership'] if pd.notna(row['ownership']) else 100
        val = row['value']
        lvg_tier = row['leverage_tier']
        
        if lvg_tier == '🔥':
            lvg_tooltip = f"🔥 HIGH LEVERAGE | Own: {own:.1f}% (Low) | Value: {val:.2f} vs {pos_median:.2f} median | Great GPP play - low owned + above average value"
        elif lvg_tier == '⚡':
            lvg_tooltip = f"⚡ MEDIUM LEVERAGE | Own: {own:.1f}% (Moderate) | Value: {val:.2f} vs {pos_median:.2f} median | Decent GPP option"
        else:
            lvg_tooltip = f"• LOW LEVERAGE | Own: {own:.1f}% | Value: {val:.2f} vs {pos_median:.2f} median | Either chalk or poor value"
        
        leverage_tooltips.append(lvg_tooltip)
    
    df['regression_risk'] = regression_risks
    df['prior_week_points'] = prior_week_points
    df['regression_tooltip'] = regression_tooltips
    df['leverage_tooltip'] = leverage_tooltips
    
    return df

def render_player_selection():
    """
    Render the player selection UI component with enhanced Excel-like table.
    
    Provides interactive table for player states, search/filter,
    bulk actions, validation warnings, and counts.
    """
    # ========== SMART VALUE CONFIGURATION SIDEBAR ==========
    # Use custom CSS to make sidebar wider
    st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        min-width: 450px;
        max-width: 450px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("---")
        st.markdown("### ⚙️ Smart Value Configuration")
        
        with st.expander("📊 Adjust Weights & Factors", expanded=False):
            st.markdown("""
            **Control every factor** that contributes to the Smart Value score.
            Main category weights must sum to 1.0 (100%).
            """)
            
            # Initialize session state for custom weights if not exists
            if 'smart_value_custom_weights' not in st.session_state:
                st.session_state['smart_value_custom_weights'] = {
                    'base': 0.40,
                    'opportunity': 0.30,
                    'trends': 0.15,
                    'risk': 0.10,
                    'matchup': 0.05
                }
            
            st.markdown("#### 🎯 Main Category Weights")
            st.caption("Adjust how much each factor influences the final score")
            
            # Base Value
            col1, col2 = st.columns([3, 1])
            with col1:
                base_weight = st.slider(
                    "Base Value",
                    min_value=0.0, max_value=1.0, 
                    value=st.session_state['smart_value_custom_weights']['base'],
                    step=0.05,
                    key='base_weight_slider',
                    help="Projection per $1K spent. Pure salary efficiency."
                )
            with col2:
                st.metric("", f"{base_weight*100:.0f}%", label_visibility="collapsed")
            
            # Opportunity
            col1, col2 = st.columns([3, 1])
            with col1:
                opp_weight = st.slider(
                    "Opportunity",
                    min_value=0.0, max_value=1.0,
                    value=st.session_state['smart_value_custom_weights']['opportunity'],
                    step=0.05,
                    key='opp_weight_slider',
                    help="Volume metrics: Snap %, Target Share, RZ Targets"
                )
            with col2:
                st.metric("", f"{opp_weight*100:.0f}%", label_visibility="collapsed")
            
            # Trends
            col1, col2 = st.columns([3, 1])
            with col1:
                trends_weight = st.slider(
                    "Trends",
                    min_value=0.0, max_value=1.0,
                    value=st.session_state['smart_value_custom_weights']['trends'],
                    step=0.05,
                    key='trends_weight_slider',
                    help="Momentum, role growth, recent production trajectory"
                )
            with col2:
                st.metric("", f"{trends_weight*100:.0f}%", label_visibility="collapsed")
            
            # Risk
            col1, col2 = st.columns([3, 1])
            with col1:
                risk_weight = st.slider(
                    "Risk",
                    min_value=0.0, max_value=1.0,
                    value=st.session_state['smart_value_custom_weights']['risk'],
                    step=0.05,
                    key='risk_weight_slider',
                    help="Regression risk (80/20), XFP variance, consistency"
                )
            with col2:
                st.metric("", f"{risk_weight*100:.0f}%", label_visibility="collapsed")
            
            # Matchup
            col1, col2 = st.columns([3, 1])
            with col1:
                matchup_weight = st.slider(
                    "Matchup",
                    min_value=0.0, max_value=1.0,
                    value=st.session_state['smart_value_custom_weights']['matchup'],
                    step=0.05,
                    key='matchup_weight_slider',
                    help="Game environment, Vegas totals, pace/script factors"
                )
            with col2:
                st.metric("", f"{matchup_weight*100:.0f}%", label_visibility="collapsed")
            
            # Calculate total and show status
            total = base_weight + opp_weight + trends_weight + risk_weight + matchup_weight
            
            # Auto-normalize weights if they don't sum to 100%
            needs_normalization = abs(total - 1.0) > 0.001
            
            if needs_normalization:
                st.warning(f"⚠️ Weights sum to **{total*100:.1f}%**. Will auto-normalize to 100% when applied.")
                # Show what normalized weights will be
                with st.expander("Preview normalized weights", expanded=False):
                    st.caption(f"Original → Normalized:")
                    st.caption(f"• Base: {base_weight*100:.1f}% → {(base_weight/total)*100:.1f}%")
                    st.caption(f"• Opportunity: {opp_weight*100:.1f}% → {(opp_weight/total)*100:.1f}%")
                    st.caption(f"• Trends: {trends_weight*100:.1f}% → {(trends_weight/total)*100:.1f}%")
                    st.caption(f"• Risk: {risk_weight*100:.1f}% → {(risk_weight/total)*100:.1f}%")
                    st.caption(f"• Matchup: {matchup_weight*100:.1f}% → {(matchup_weight/total)*100:.1f}%")
            else:
                st.success(f"✅ Weights sum to **{total*100:.0f}%**")
            
            # Build new weights dict (normalized)
            if needs_normalization and total > 0:
                # Normalize to sum to 1.0
                new_weights = {
                    'base': base_weight / total,
                    'opportunity': opp_weight / total,
                    'trends': trends_weight / total,
                    'risk': risk_weight / total,
                    'matchup': matchup_weight / total
                }
            else:
                new_weights = {
                    'base': base_weight,
                    'opportunity': opp_weight,
                    'trends': trends_weight,
                    'risk': risk_weight,
                    'matchup': matchup_weight
                }
            
            # Apply & Recalculate button
            st.markdown("---")
            if st.button("🔄 Apply & Recalculate", use_container_width=True, type="primary"):
                st.session_state['smart_value_custom_weights'] = new_weights
                # Clear cached smart value data to force recalculation
                if 'smart_value_calculated' in st.session_state:
                    del st.session_state['smart_value_calculated']
                if 'smart_value_data' in st.session_state:
                    del st.session_state['smart_value_data']
                st.success("✅ Configuration applied!")
                st.rerun()
            
            # Reset to default button
            if st.button("↩️ Reset to Balanced", use_container_width=True):
                st.session_state['smart_value_custom_weights'] = {
                    'base': 0.40,
                    'opportunity': 0.30,
                    'trends': 0.15,
                    'risk': 0.10,
                    'matchup': 0.05
                }
                # Clear cached data
                if 'smart_value_calculated' in st.session_state:
                    del st.session_state['smart_value_calculated']
                if 'smart_value_data' in st.session_state:
                    del st.session_state['smart_value_data']
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
                st.caption("How Risk adjustments are balanced")
                
                risk_reg = st.slider(
                    "Regression (80/20)",
                    0.0, 1.0, st.session_state['smart_value_sub_weights']['risk_regression'],
                    0.05, key='risk_reg_slider',
                    help="Weight for 80/20 regression risk penalty"
                )
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
                risk_total = risk_reg + risk_var + risk_cons
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
                    'risk_regression': risk_reg / risk_total if risk_total > 0 else 0.50,
                    'risk_variance': risk_var / risk_total if risk_total > 0 else 0.30,
                    'risk_consistency': risk_cons / risk_total if risk_total > 0 else 0.20
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
    
    # Header with enhanced styling and Material Icons
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="color: #f9fafb; font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem;">
            <span class="material-icons md-36" style="vertical-align: text-bottom; color: #10b981;">sports_football</span> 
            Player Pool Selection
        </h1>
        <p style="color: #9ca3af; font-size: 1.1rem; margin: 0;">
            <span class="material-icons md-18" style="vertical-align: middle; color: #10b981;">check_circle</span> Check "Pool" to include | 
            <span class="material-icons md-18" style="vertical-align: middle; color: #f59e0b;">lock</span> Check "Lock" to guarantee in ALL lineups
        </p>
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
    if 'season_stats_enriched' not in st.session_state:
        with st.spinner("📈 Analyzing 5-week season trends..."):
            df = analyze_season_stats(df, excel_path="2025 Stats thru week 5.xlsx")
            st.session_state['season_stats_data'] = df
            st.session_state['season_stats_enriched'] = True
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
            
            df = calculate_smart_value(df, profile='balanced', custom_weights=custom_weights, position_weights=position_weights, sub_weights=sub_weights)
            st.session_state['smart_value_data'] = df
            st.session_state['smart_value_calculated'] = True
    else:
        # Use cached smart value data
        df = st.session_state['smart_value_data'].copy()
        # Re-apply opponent lookup for cached data
        if 'opponent_lookup' in st.session_state and st.session_state['opponent_lookup']:
            opponent_map = st.session_state['opponent_lookup']
            df = add_opponents_to_dataframe(df, opponent_map)
    
    # Verify required columns exist before storing
    required_cols = ['position', 'name', 'salary', 'projection', 'team']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.error(f"⚠️ Missing required columns: {missing_cols}. Please reload your data.")
        return
    
    # Store enriched data (with opponents + DFS metrics + season stats + smart value) for optimizer
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
    
    is_valid, error_msg = check_roster_requirements()
    
    # Smart Value Threshold Selector + Quick Actions
    col1, col2, col3 = st.columns([2, 1.5, 1.5])
    with col1:
        # Smart Value threshold slider
        st.markdown("**🎯 Smart Value Threshold**")
        smart_threshold = st.slider(
            "",
            min_value=0,
            max_value=100,
            value=0,
            step=5,
            help="Auto-select all players with Smart Value at or above this threshold",
            key="smart_value_threshold",
            label_visibility="collapsed"
        )
        
        # Apply threshold if changed from 0
        if smart_threshold > 0:
            if st.button(f"✓ Select Players ≥ {smart_threshold}", use_container_width=True, key="apply_threshold"):
                # Initialize selections if not exists
                if 'selections' not in st.session_state:
                    st.session_state['selections'] = {}
                
                # Select players at or above threshold
                for idx in df.index:
                    player_smart_value = df.loc[idx, 'smart_value'] if 'smart_value' in df.columns else 0
                    if player_smart_value >= smart_threshold:
                        st.session_state['selections'][idx] = PlayerSelection.EXCLUDED.value  # Excluded means selected in pool
                    else:
                        st.session_state['selections'][idx] = PlayerSelection.NORMAL.value
                st.rerun()
    with col2:
        st.markdown("**Quick Actions**")
        if st.button("✕ Deselect All", use_container_width=True, key="deselect_all"):
            st.session_state['selections'] = {idx: PlayerSelection.NORMAL.value for idx in df.index}
            st.rerun()
    with col3:
        # Quick navigation to optimization config - disabled if requirements not met
        if is_valid:
            if st.button("Next: Optimization Config ➡️", use_container_width=True, type="primary", key="quick_next"):
                st.session_state['page'] = 'optimization'
                st.rerun()
        else:
            # Disabled button with tooltip
            st.button(
                "Next: Optimization Config ➡️", 
                use_container_width=True, 
                type="primary", 
                key="quick_next_disabled",
                disabled=True,
                help=f"⚠️ {error_msg}\n\n✅ Minimum requirements:\n• 1 QB\n• 2 RB\n• 3 WR\n• 1 TE\n• 1 DST"
            )
    
    # Count locked players
    locked_count = sum(1 for s in selections.values() if s == PlayerSelection.LOCKED.value)
    in_pool_count = sum(1 for s in selections.values() if s != PlayerSelection.NORMAL.value)
    
    # Prepare data for AgGrid with Pool and Lock checkboxes
    st.markdown(f"""
    <div style="background-color: #1a1a1a; border-radius: 4px; padding: 0.5rem; margin: 1rem 0; border: 1px solid #333; box-shadow: 0 2px 8px rgba(0,0,0,0.3);">
        <div style="background: #2a2a2a; color: #e0e0e0; padding: 0.4rem; border-radius: 4px 4px 0 0; font-weight: 600; font-size: 0.8rem; text-align: center; border-bottom: 1px solid #444;">
            Players ({len(df)}) | In Pool: {in_pool_count} | 🔒 Locked: {locked_count}
        </div>
    """, unsafe_allow_html=True)
    
    # Prepare data for AgGrid
    display_data = []
    for idx, row in df.iterrows():
        current_selection = selections.get(idx, PlayerSelection.NORMAL.value)
        is_in_pool = current_selection != PlayerSelection.NORMAL.value
        is_locked = current_selection == PlayerSelection.LOCKED.value
        
        # Prepare player data with DFS metrics + Season stats
        player_data = {
            '_index': idx,  # Hidden column to track original index
            'Pool': is_in_pool,
            'Lock': is_locked,
            'Player': row['name'],
            'Pos': row['position'],
            'Salary': row['salary'],
            'Proj': row['projection'],
            'Own%': row['ownership'] if 'ownership' in row and pd.notna(row['ownership']) else 0,
            'Value': row['value'] if 'value' in row else 0,
            'Smart Value': row['smart_value'] if 'smart_value' in row else row.get('value', 0),
            'Smart_Value_Tooltip': row.get('smart_value_tooltip', 'Smart Value calculation pending'),
            'Rank': f"{row['position']}{int(row['pos_rank'])}" if 'pos_rank' in row else "-",
            'Lvg': row['leverage_tier'] if 'leverage_tier' in row else '•',
            'Lvg_Tooltip': row['leverage_tooltip'] if 'leverage_tooltip' in row else '',
            'Reg': row['regression_risk'] if 'regression_risk' in row else '',
            'Reg_Tooltip': row['regression_tooltip'] if 'regression_tooltip' in row else '',
            'Team': row['team'],
            'Opp': row['opponent'] if 'opponent' in row and pd.notna(row['opponent']) else "-",
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
    
    # Configure columns
    gb.configure_column("_index", hide=True)  # Hide the index tracking column
    
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
                        pinned='left')
    
    gb.configure_column("Pos", 
                        header_name="Pos",
                        filter="agSetColumnFilter",  # Multi-select filter
                        filterParams=filter_config,
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
    
    gb.configure_column("Smart Value", 
                        header_name="Smart Value",
                        type=["numericColumn"],
                        valueFormatter="value ? value.toFixed(0) : ''",  # Show as whole number (0-100 scale)
                        filter="agNumberColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=120,
                        cellStyle={
                            'fontWeight': 'bold',
                            'textAlign': 'center',
                            'backgroundColor': '#1a472a',  # Dark green background
                            'color': '#4ade80'  # Light green text
                        },
                        tooltipField="Smart_Value_Tooltip",
                        headerTooltip="SMART VALUE SCORE 🧠 - Advanced multi-factor score combining: Base Value (40%), Opportunity metrics (30%), 5-week Trends (15%), Risk factors (10%), Matchup quality (5%). This goes BEYOND simple projection/salary to find truly undervalued plays by incorporating volume, momentum, regression risk, and game environment. Higher = Better overall DFS value. HOVER OVER ANY CELL to see detailed breakdown! Sort by this column to find the smartest plays that the market might be missing.")
    
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
                        filter="agSetColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=70,
                        cellStyle={'textAlign': 'center', 'fontSize': '1.2rem'},
                        tooltipField="Lvg_Tooltip",
                        headerTooltip="LEVERAGE INDICATOR - Tournament play identifier based on ownership + value. 🔥 HIGH (own <10% + above-position-median value) = Great contrarian play with value - these are your GPP gems. ⚡ MEDIUM (own <20% + above-median value) = Solid leverage opportunity. • LOW (high own OR below-median value) = Chalk or poor value. Strategy: Stack 🔥 players in tournaments for differentiation when they boom. Avoid over-using in cash games where safety matters more.")
    
    gb.configure_column("Reg", 
                        header_name="Reg",
                        filter="agSetColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=65,
                        cellStyle={'textAlign': 'center', 'fontSize': '1.2rem'},
                        tooltipField="Reg_Tooltip",
                        headerTooltip="80/20 REGRESSION RISK - The 80/20 rule states that 80% of players who scored 20+ DraftKings fantasy points last week will regress (score less) this week. ⚠️ WARNING = Player scored 20+ last week, high regression risk - use caution, lower exposure in lineups, fade in cash games. ✓ SAFE = Player found in last week's data but scored <20 points, no regression concern. BLANK = No prior week data available. Strategy: Fade ⚠️ players in cash games where consistency matters. In GPPs, they can be contrarian if ownership is inflated due to recency bias.")
    
    # Hide tooltip columns (they're just data sources for tooltips)
    gb.configure_column("Lvg_Tooltip", hide=True)
    gb.configure_column("Reg_Tooltip", hide=True)
    gb.configure_column("Cons_Tooltip", hide=True)
    gb.configure_column("Mom_Tooltip", hide=True)
    gb.configure_column("Smart_Value_Tooltip", hide=True)
    
    gb.configure_column("Team", 
                        header_name="Team",
                        filter="agSetColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=90)
    
    gb.configure_column("Opp", 
                        header_name="Opp",
                        filter="agTextColumnFilter",
                        filterParams=filter_config,
                        menuTabs=menu_tabs,
                        width=90,
                        headerTooltip="OPPONENT - The team this player is facing this week. '@' symbol = away game (e.g., '@BUF' = playing at Buffalo). No '@' = home game. Use this to identify favorable/unfavorable matchups, stack game environments, and avoid tough defensive matchups.")
    
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
        suppressRowClickSelection=True
    )
    
    # Set default sort by Value (descending)
    gb.configure_default_column(sortable=True)
    
    # Build grid options
    grid_options = gb.build()
    
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
    
    # Continue button (using Streamlit's native button with primary styling)
    st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
    
    # Apply same validation as top navigation button
    if is_valid:
        if st.button("▶️ Continue to Optimization", type="primary", use_container_width=True, key="continue_btn"):
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
            key="continue_btn_disabled",
            disabled=True,
            help=f"⚠️ {error_msg}\n\n✅ Minimum requirements:\n• 1 QB\n• 2 RB\n• 3 WR\n• 1 TE\n• 1 DST"
        )