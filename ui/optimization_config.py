"""
Optimization Configuration UI Component

This module implements the Streamlit UI for configuring lineup optimization parameters,
including lineup count, uniqueness constraints, and optional ownership filters.
"""

import streamlit as st
import pandas as pd
import math
from pathlib import Path
import sys

# Add src directory to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from models import PlayerSelection


def render_optimization_config():
    """Main render function for Component 3: Optimization Configuration."""
    
    # 1. Validation: Check player pool exists
    if 'player_data' not in st.session_state or 'selections' not in st.session_state:
        st.error("No player pool found. Please complete player selection first.")
        if st.button("← Back to Player Selection"):
            st.session_state['page'] = 'player_selection'
            st.rerun()
        return
    
    # Apply compact styles
    from src.styles import get_base_styles, get_card_styles
    st.markdown(get_base_styles(), unsafe_allow_html=True)
    st.markdown(get_card_styles(), unsafe_allow_html=True)
    
    # ULTRA-COMPACT Header: Single line with inline subtitle
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.5rem 0; margin-bottom: 0.75rem;">
        <div style="display: flex; align-items: baseline; gap: 1rem;">
            <h2 style="margin: 0; font-size: 1.5rem; font-weight: 700; display: inline;">
                🎯 <span class="gradient-text">Optimization Config</span>
            </h2>
            <span style="color: #707070; font-size: 0.875rem;">Configure lineup generation</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 3. Player Pool Summary (Task 4.1)
    pool_df = get_player_pool()
    display_pool_summary(pool_df)
    
    # 3.5. Detailed Player Pool View (with Narrative Intelligence)
    display_player_pool_details(pool_df)
    
    # COMPACT Configuration Controls
    st.markdown("### ⚙️ Lineup Settings")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        # Task 2.1: Lineup Count Slider
        lineup_count = st.slider(
            "Number of Lineups",
            min_value=1,
            max_value=20,
            value=5,
            step=1,
            help="Generate 1-20 unique lineup variations. More lineups = more coverage but longer generation time.",
            key="lineup_count"
        )
    with col2:
        st.markdown('<div style="padding-top: 1.75rem;">', unsafe_allow_html=True)
        st.metric("", f"{lineup_count}", label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Store in session state (temporary config)
    if 'temp_config' not in st.session_state:
        st.session_state['temp_config'] = {}
    st.session_state['temp_config']['lineup_count'] = lineup_count
    
    # Task 2.2: Uniqueness Slider
    col1, col2 = st.columns([3, 1])
    with col1:
        uniqueness_pct = st.slider(
            "Lineup Uniqueness",
            min_value=40,
            max_value=70,
            value=55,
            step=5,
            format="%d%%",
            help="Minimum percentage of different players between lineups. Higher = more diverse but potentially lower-scoring lineups.",
            key="uniqueness_pct"
        )
    with col2:
        st.markdown('<div style="padding-top: 1.75rem;">', unsafe_allow_html=True)
        st.metric("", f"{uniqueness_pct}%", label_visibility="collapsed")
        st.markdown('</div>', unsafe_allow_html=True)
    
    unique_players_needed = math.ceil(9 * (uniqueness_pct / 100))
    max_shared = 9 - unique_players_needed
    
    st.caption(f"≥ {unique_players_needed} unique players per lineup (max {max_shared} shared)")
    
    st.session_state['temp_config']['uniqueness_pct'] = uniqueness_pct
    
    # Smart Value Quality Filter
    st.markdown("### 🧠 Smart Value Filter")
    
    # Check if Smart Value is available
    has_smart_value = 'smart_value' in pool_df.columns and pool_df['smart_value'].notna().any()
    
    if not has_smart_value:
        st.warning("⚠️ Smart Value scores not available. Go back to Player Selection to calculate Smart Value. Skipping filter.")
        min_smart_value = 0
        filter_strategy = 'simple'
        positional_floors = None
    else:
        st.markdown("""
        Smart Value combines opportunity, matchup, trends, and leverage into a 0-100 score.  
        Setting a minimum ensures you only build lineups from high-quality plays.
        
        **Optimizer maximizes projected points** among players meeting this threshold.
        """)
        
        # Mode selector
        filter_strategy = st.radio(
            "Filter Strategy",
            options=['simple', 'positional', 'portfolio'],
            format_func=lambda x: {
                'simple': '🎯 Simple (One threshold)',
                'positional': '📊 Positional (Per position)',
                'portfolio': '💼 Portfolio (Lineup average) ⭐'
            }[x],
            horizontal=True,
            help="""
            - Simple: One threshold for all positions
            - Positional: Custom threshold per position
            - Portfolio: Lineup average threshold (most flexible)
            """,
            key="filter_strategy"
        )
        
        if filter_strategy == 'simple':
            # Existing global slider
            col1, col2 = st.columns([3, 1])
            with col1:
                min_smart_value = st.slider(
                    "Minimum Smart Value",
                    min_value=0,
                    max_value=100,
                    value=40,  # Default: Block bottom 40%
                    step=5,
                    help="Only consider players with Smart Value ≥ this threshold",
                    key="min_smart_value"
                )
            with col2:
                st.markdown('<div style="padding-top: 1.75rem;">', unsafe_allow_html=True)
                st.metric("", f"{min_smart_value}")
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Quality tier indicator
            if min_smart_value >= 70:
                st.info("🎯 **Elite Plays Only** - Very strict filter")
            elif min_smart_value >= 50:
                st.success("✅ **Quality Plays** - Balanced filter")
            elif min_smart_value >= 30:
                st.warning("⚡ **Flexible** - Allows riskier plays")
            else:
                st.caption("🔓 **Wide Open** - Minimal filtering")
            
            positional_floors = None
            portfolio_avg = None
            
        elif filter_strategy == 'positional':
            st.caption("Set minimum Smart Value by position:")
            
            # Preset buttons
            col1, col2, col3 = st.columns(3)
            
            presets = {
                'conservative': {'QB': 60, 'RB': 55, 'WR': 50, 'TE': 50, 'DST': 40},
                'balanced': {'QB': 50, 'RB': 45, 'WR': 40, 'TE': 40, 'DST': 30},
                'aggressive': {'QB': 40, 'RB': 35, 'WR': 30, 'TE': 30, 'DST': 20}
            }
            
            with col1:
                if st.button("🛡️ Conservative", use_container_width=True):
                    st.session_state['positional_preset'] = 'conservative'
                    st.rerun()
            with col2:
                if st.button("⚖️ Balanced", use_container_width=True):
                    st.session_state['positional_preset'] = 'balanced'
                    st.rerun()
            with col3:
                if st.button("⚡ Aggressive", use_container_width=True):
                    st.session_state['positional_preset'] = 'aggressive'
                    st.rerun()
            
            # Get preset values if selected
            preset_name = st.session_state.get('positional_preset', 'balanced')
            preset_values = presets[preset_name]
            
            st.caption(f"Current preset: **{preset_name.title()}**")
            
            # Individual position sliders
            positional_floors = {}
            
            for pos in ['QB', 'RB', 'WR', 'TE', 'DST']:
                col1, col2 = st.columns([3, 1])
                with col1:
                    positional_floors[pos] = st.slider(
                        f"{pos} Minimum",
                        min_value=0,
                        max_value=100,
                        value=preset_values[pos],
                        step=5,
                        key=f"min_sv_{pos}"
                    )
                with col2:
                    st.markdown('<div style="padding-top: 1.75rem;">', unsafe_allow_html=True)
                    st.metric("", f"{positional_floors[pos]}")
                    st.markdown('</div>', unsafe_allow_html=True)
            
            min_smart_value = None  # Not used in positional mode
            portfolio_avg = None
            
        elif filter_strategy == 'portfolio':
            st.markdown("""
            **Portfolio Average Mode** allows individual "chalk" players with lower Smart Value 
            if balanced by high Smart Value plays elsewhere.
            
            Example: A 30 SV stud + eight 75 SV players = 70 average ✅
            """)
            
            col1, col2 = st.columns([3, 1])
            with col1:
                portfolio_avg = st.slider(
                    "Minimum Lineup Average Smart Value",
                    min_value=30,
                    max_value=90,
                    value=60,
                    step=5,
                    help="The 9-player lineup's average Smart Value must meet this threshold",
                    key="portfolio_avg_sv"
                )
            with col2:
                st.markdown('<div style="padding-top: 1.75rem;">', unsafe_allow_html=True)
                st.metric("", f"{portfolio_avg}")
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Quality indicator
            if portfolio_avg >= 70:
                st.info("🎯 **Elite Lineup** - High average quality required")
            elif portfolio_avg >= 55:
                st.success("✅ **Quality Lineup** - Balanced approach")
            else:
                st.warning("⚡ **Flexible** - Allows mixing chalk with value")
            
            min_smart_value = None
            positional_floors = None
    
    st.session_state['temp_config']['filter_strategy'] = filter_strategy
    st.session_state['temp_config']['min_smart_value'] = min_smart_value
    st.session_state['temp_config']['positional_floors'] = positional_floors
    st.session_state['temp_config']['portfolio_avg_smart_value'] = portfolio_avg if filter_strategy == 'portfolio' else None
    
    # Stacking Strategy (for GPP tournament play)
    st.markdown("### 🔗 Stacking Strategy")
    
    stacking_enabled = st.toggle(
        "Primary Stack (QB + WR/TE same team)",
        value=True,  # DEFAULT ON for tournament play
        help="Forces QB + at least 1 WR/TE from same team. Standard GPP construction for correlated upside.",
        key="stacking_enabled"
    )
    
    if stacking_enabled:
        st.success("""
        ✅ **Stack Mode Active**
        
        Each lineup will include QB + at least 1 WR/TE from the same team.
        
        🎯 **Tournament Strategy**: Correlated scoring increases upside and creates differentiated constructions.
        """)
    else:
        st.info("""
        ⚪ **Pure Optimization Mode**
        
        Optimizer will maximize value without team correlation requirements.
        
        ⚠️ May not stack even when strategically advantageous for tournaments.
        """)
    
    st.session_state['temp_config']['stacking_enabled'] = stacking_enabled
    
    # Task 2.3: Max Ownership Filter
    st.markdown("### 🔍 Optional Filters")
    
    # Check if ownership data exists
    has_ownership = 'ownership' in pool_df.columns
    
    max_ownership_enabled = st.checkbox(
        "Limit Max Ownership",
        value=False,
        help="Exclude players projected to be owned by more than X% of the field. Use for contrarian/GPP strategies.",
        key="max_ownership_enabled"
    )
    
    max_ownership_pct = None
    if max_ownership_enabled:
        if not has_ownership:
            st.warning("⚠️ Ownership data not available in uploaded file. Filter disabled.")
            max_ownership_enabled = False
        else:
            max_ownership_pct = st.number_input(
                "Max Ownership %",
                min_value=1,
                max_value=100,
                value=30,
                step=5,
                help="Players with ownership > this value will be excluded",
                key="max_ownership_input"
            )
            
            # Show filtered pool size
            filtered_pool = pool_df[pool_df['ownership'] <= max_ownership_pct]
            st.info(f"After ownership filter: **{len(filtered_pool)} players** remain (from {len(pool_df)} total)")
    
    st.session_state['temp_config']['max_ownership_enabled'] = max_ownership_enabled
    st.session_state['temp_config']['max_ownership_pct'] = max_ownership_pct
    
    # 5. Validation (before displaying constraints and buttons)
    validation_result = validate_configuration(
        pool_df, lineup_count, uniqueness_pct, max_ownership_enabled, max_ownership_pct
    )
    
    # 6. Constraints Summary Panel (Task 4.2)
    display_constraints_summary(
        pool_df, lineup_count, uniqueness_pct, 
        max_ownership_enabled, max_ownership_pct, validation_result
    )
    
    # ULTRA-COMPACT Navigation: Single row with Back and Generate
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    
    # Show validation error/warning at the top if exists
    if validation_result['status'] == 'invalid':
        st.error(validation_result['message'])
    elif validation_result['status'] == 'warning':
        st.warning(validation_result['message'])
    
    col1, col2 = st.columns([1, 4])
    
    with col1:
        if st.button("⬅️ Back", use_container_width=True, key="back_btn", help="Back to Player Selection"):
            # Configuration persists in temp_config
            st.session_state['page'] = 'player_selection'
            st.rerun()
    
    with col2:
        if validation_result['status'] == 'invalid':
            st.button("🚀 Generate Lineups", disabled=True, 
                      help="Fix validation errors to enable", use_container_width=True, type="primary")
        else:
            if st.button("🚀 Generate Lineups", type="primary", use_container_width=True):
                # Store config in session state
                st.session_state['optimization_config'] = {
                    'lineup_count': lineup_count,
                    'uniqueness_pct': uniqueness_pct / 100,  # Convert to decimal
                    'max_ownership_enabled': max_ownership_enabled,
                    'max_ownership_pct': max_ownership_pct / 100 if max_ownership_pct else None,
                    'filter_strategy': filter_strategy,  # 'simple', 'positional', or 'portfolio'
                    'min_smart_value': min_smart_value,  # For simple mode
                    'positional_floors': positional_floors,  # For positional mode
                    'portfolio_avg_smart_value': portfolio_avg if filter_strategy == 'portfolio' else None,  # For portfolio mode
                    'stacking_enabled': stacking_enabled,
                    'estimated_time': validation_result['estimated_time'],
                    'validation_status': validation_result['status'],
                    'validation_message': validation_result['message']
                }
                st.session_state['player_pool'] = pool_df
                st.session_state['page'] = 'lineup_generation'
                st.rerun()


def get_player_pool() -> pd.DataFrame:
    """Extract player pool from session state selections."""
    # Use enriched data if available, otherwise fall back to original data
    if 'enriched_player_data' in st.session_state and st.session_state['enriched_player_data'] is not None:
        df = st.session_state['enriched_player_data'].copy()
    else:
        df = st.session_state['player_data'].copy()
    
    # Defensive check: ensure required columns exist
    required_cols = ['position', 'name', 'salary', 'projection']
    if not all(col in df.columns for col in required_cols):
        st.error("⚠️ Player data is missing required columns. Please go back to Player Selection to refresh the data.")
        st.info(f"Available columns: {list(df.columns)}")
        st.info("💡 **Tip:** Click 'Player Pool Selection' in the sidebar to reload the enriched data.")
        st.stop()
    
    selections = st.session_state['selections']
    
    # Get indices of players in pool (EXCLUDED = eligible, LOCKED = must include)
    # Note: EXCLUDED is repurposed to mean "in pool, eligible"
    pool_indices = [idx for idx, state in selections.items() 
                    if state in [PlayerSelection.EXCLUDED.value, PlayerSelection.LOCKED.value]]
    
    if not pool_indices:
        return pd.DataFrame()  # Empty pool
    
    pool_df = df.loc[pool_indices].copy()
    
    # Ensure opponent column exists (fallback for cached data)
    if 'opponent' not in pool_df.columns:
        pool_df['opponent'] = "-"
    
    # Add selection state to the DataFrame so optimizer knows which are locked
    pool_df['selection_state'] = pool_df.index.map(selections)
    
    return pool_df


def validate_configuration(pool_df: pd.DataFrame, lineup_count: int, uniqueness_pct: int, 
                           max_ownership_enabled: bool, max_ownership_pct: int) -> dict:
    """
    Validate configuration and return status dict.
    
    Args:
        pool_df: Player pool DataFrame
        lineup_count: Number of lineups to generate
        uniqueness_pct: Uniqueness percentage (40-70)
        max_ownership_enabled: Whether ownership filter is enabled
        max_ownership_pct: Max ownership percentage (if enabled)
    
    Returns:
        Dict with keys: 'status' ('valid'/'warning'/'invalid'), 
                       'message' (str), 
                       'estimated_time' (float in seconds)
    """
    result = {
        'status': 'valid',  # 'valid', 'warning', 'invalid'
        'message': '',
        'estimated_time': 0.0
    }
    
    # Apply ownership filter if enabled
    filtered_pool = pool_df.copy()
    if max_ownership_enabled and max_ownership_pct:
        filtered_pool = filtered_pool[filtered_pool['ownership'] <= max_ownership_pct]
        if len(filtered_pool) < 20:  # Warning threshold
            result['status'] = 'warning'
            result['message'] = f"⚠️ Ownership filter leaves only {len(filtered_pool)} players. Consider relaxing filter."
    
    # Check position requirements
    position_counts = filtered_pool['position'].value_counts()
    
    required_positions = {
        'QB': 1,
        'RB': 2,
        'WR': 3,
        'TE': 1,
        'DST': 1
    }
    
    for pos, min_count in required_positions.items():
        if position_counts.get(pos, 0) < min_count:
            result['status'] = 'invalid'
            result['message'] = f"❌ Not enough {pos}s in pool (need at least {min_count}, have {position_counts.get(pos, 0)})"
            return result
    
    # Check uniqueness feasibility
    unique_players_needed = math.ceil(9 * (uniqueness_pct / 100))
    max_possible_lineups = len(filtered_pool) // unique_players_needed
    
    if lineup_count > max_possible_lineups:
        result['status'] = 'invalid'
        result['message'] = (
            f"❌ Player pool too small for {lineup_count} lineups with "
            f"{uniqueness_pct}% uniqueness. "
            f"Maximum possible: {max_possible_lineups} lineups. "
            f"Reduce lineup count or uniqueness constraint."
        )
        return result
    
    # Estimate generation time
    result['estimated_time'] = estimate_generation_time(
        lineup_count, uniqueness_pct, len(filtered_pool)
    )
    
    return result


def estimate_generation_time(lineup_count: int, uniqueness_pct: int, pool_size: int) -> float:
    """
    Estimate generation time in seconds.
    
    Args:
        lineup_count: Number of lineups to generate
        uniqueness_pct: Uniqueness percentage (40-70)
        pool_size: Size of player pool
    
    Returns:
        Estimated time in seconds (rounded to nearest 5)
    """
    base_time = 0.5 + (lineup_count * 0.5)
    complexity_multiplier = 1.0
    
    # Adjust for uniqueness (higher = more solver iterations)
    if uniqueness_pct >= 60:
        complexity_multiplier *= 1.3
    if uniqueness_pct >= 70:
        complexity_multiplier *= 1.5
    
    # Adjust for pool size (smaller pool = faster)
    if pool_size < 50:
        complexity_multiplier *= 0.8
    elif pool_size > 200:
        complexity_multiplier *= 1.2
    
    estimated_time = base_time * complexity_multiplier
    
    # Round to nearest 5 seconds for UX
    return max(5, round(estimated_time / 5) * 5)


def display_pool_summary(pool_df: pd.DataFrame):
    """Display player pool summary card."""
    # Verify required columns exist
    required_cols = ['position', 'salary', 'projection']
    missing_cols = [col for col in required_cols if col not in pool_df.columns]
    
    if missing_cols:
        st.error(f"⚠️ Missing required columns in player pool: {', '.join(missing_cols)}")
        st.info("💡 **Tip:** Go back to the Player Selection screen to refresh the data enrichment.")
        st.stop()
    
    position_counts = pool_df['position'].value_counts()
    avg_salary = pool_df['salary'].mean()
    total_projection = pool_df['projection'].sum()
    
    # Count locked players if selection_state column exists
    locked_players = []
    if 'selection_state' in pool_df.columns:
        locked_players = pool_df[pool_df['selection_state'] == PlayerSelection.LOCKED.value]
    
    st.markdown("""
    <div style="background-color: #1a1a1a; border-radius: 8px; padding: 1.5rem; margin: 1rem 0; border: 1px solid #333;">
        <h3 style="color: #f9fafb; margin-top: 0;">📊 Player Pool Summary</h3>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Players", len(pool_df))
    with col2:
        st.metric("Avg Salary", f"${avg_salary:,.0f}")
    with col3:
        st.metric("Total Proj Points", f"{total_projection:.1f}")
    with col4:
        pos_breakdown = ", ".join([f"{pos}: {count}" for pos, count in position_counts.items()])
        st.markdown(f"**Positions:**<br>{pos_breakdown}", unsafe_allow_html=True)
    
    # Display narrative intelligence summary if data is enriched
    has_narrative_data = 'injury_status' in pool_df.columns or 'itt' in pool_df.columns
    if has_narrative_data:
        st.markdown("<div style='margin-top: 1rem; padding: 1rem; background: #1e1e3a; border-radius: 6px; border-left: 4px solid #3b82f6;'>", unsafe_allow_html=True)
        st.markdown("**📊 Narrative Intelligence Data Available**", unsafe_allow_html=True)
        
        narrative_stats = []
        if 'injury_status' in pool_df.columns:
            injured_count = pool_df['injury_status'].notna().sum()
            if injured_count > 0:
                narrative_stats.append(f"🏥 {injured_count} players with injury reports")
        
        if 'itt' in pool_df.columns:
            itt_count = pool_df['itt'].notna().sum()
            if itt_count > 0:
                avg_itt = pool_df['itt'].mean()
                narrative_stats.append(f"🎰 {itt_count} players with ITT data (avg: {avg_itt:.1f})")
        
        if 'red_flags' in pool_df.columns:
            red_flag_count = (pool_df['red_flags'] > 0).sum()
            yellow_flag_count = (pool_df['yellow_flags'] > 0).sum()
            if red_flag_count > 0 or yellow_flag_count > 0:
                narrative_stats.append(f"⚠️ {red_flag_count} red flags, {yellow_flag_count} yellow flags")
        
        if narrative_stats:
            for stat in narrative_stats:
                st.markdown(f"• {stat}", unsafe_allow_html=True)
        else:
            st.markdown("• Enriched data loaded successfully", unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Display locked players if any
    if len(locked_players) > 0:
        st.markdown("<div style='margin-top: 1rem; padding: 1rem; background: #1e3a2e; border-radius: 6px; border-left: 4px solid #10b981;'>", unsafe_allow_html=True)
        st.markdown(f"**🔒 {len(locked_players)} Locked Players** (will appear in ALL lineups):", unsafe_allow_html=True)
        locked_names = ", ".join([f"**{row['name']}** ({row['position']})" for _, row in locked_players.iterrows()])
        st.markdown(locked_names, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)


def display_player_pool_details(pool_df: pd.DataFrame):
    """Display detailed player pool breakdown with narrative intelligence data."""
    # Check if we have narrative intelligence data
    has_narrative_data = 'injury_status' in pool_df.columns or 'itt' in pool_df.columns
    
    if not has_narrative_data:
        return  # Don't show this section if no narrative data
    
    with st.expander("🔍 View Player Pool Details (with Narrative Intelligence)", expanded=False):
        st.markdown("**Main Slate Players with Contextual Data**")
        
        # Prepare display columns
        display_cols = ['name', 'position', 'team', 'salary', 'projection']
        col_names = ['Player', 'Pos', 'Team', 'Salary', 'Proj']
        
        # Add narrative intelligence columns if they exist
        if 'itt' in pool_df.columns:
            display_cols.append('itt')
            col_names.append('ITT')
        
        if 'opponent' in pool_df.columns:
            display_cols.append('opponent')
            col_names.append('vs')
        
        if 'injury_status' in pool_df.columns:
            display_cols.append('injury_status')
            col_names.append('Injury')
        
        if 'injury_details' in pool_df.columns:
            display_cols.append('injury_details')
            col_names.append('Details')
        
        if 'red_flags' in pool_df.columns:
            display_cols.extend(['red_flags', 'yellow_flags', 'green_flags'])
            col_names.extend(['🔴', '🟡', '🟢'])
        
        # Filter to only include columns that exist
        available_cols = [col for col in display_cols if col in pool_df.columns]
        
        # Create display dataframe
        display_df = pool_df[available_cols].copy()
        
        # Format salary with $ and commas
        if 'salary' in display_df.columns:
            display_df['salary'] = display_df['salary'].apply(lambda x: f"${x:,.0f}")
        
        # Format ITT to 1 decimal
        if 'itt' in display_df.columns:
            display_df['itt'] = display_df['itt'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")
        
        # Format projection to 1 decimal
        if 'projection' in display_df.columns:
            display_df['projection'] = display_df['projection'].apply(lambda x: f"{x:.1f}")
        
        # Sort by position and then by projection (descending)
        if 'position' in display_df.columns:
            # Define position order
            pos_order = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 4, 'DST': 5}
            display_df['_pos_order'] = display_df['position'].map(pos_order)
            display_df = display_df.sort_values(['_pos_order', 'projection'], ascending=[True, False])
            display_df = display_df.drop('_pos_order', axis=1)
        
        # Apply column name mapping
        col_mapping = dict(zip(available_cols, [col_names[display_cols.index(col)] for col in available_cols]))
        display_df = display_df.rename(columns=col_mapping)
        
        # Display the table
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=400
        )
        
        # Add helpful notes
        st.caption("💡 **ITT** = Implied Team Total (Vegas projected points) | **Injury** statuses: Questionable (Q), Out (O), Doubtful (D)")


def display_constraints_summary(pool_df: pd.DataFrame, lineup_count: int, uniqueness_pct: int, 
                                  max_ownership_enabled: bool, max_ownership_pct: int, 
                                  validation_result: dict):
    """Display constraints summary panel."""
    st.markdown("---")
    st.markdown("### 📋 Constraints Summary")
    
    st.markdown("""
    <div style="background-color: #1a1a1a; border-radius: 8px; padding: 1.5rem; border: 1px solid #333;">
    """, unsafe_allow_html=True)
    
    # DraftKings Rules
    st.markdown("**DraftKings NFL Rules (Always Applied):**")
    st.markdown("""
    - Salary Cap: $50,000
    - Positions: 1 QB, 2 RB, 3 WR, 1 TE, 1 FLEX (RB/WR/TE), 1 DST
    """)
    
    # Player Pool Constraints
    st.markdown("**Player Pool:**")
    position_counts = pool_df['position'].value_counts()
    st.markdown(f"- {len(pool_df)} players total")
    st.markdown(f"- Positions: {position_counts.get('QB', 0)} QB, {position_counts.get('RB', 0)} RB, " +
                f"{position_counts.get('WR', 0)} WR, {position_counts.get('TE', 0)} TE, {position_counts.get('DST', 0)} DST")
    if max_ownership_enabled:
        st.markdown(f"- Ownership limited to ≤{max_ownership_pct}%")
    
    # Configuration
    st.markdown("**Configuration:**")
    st.markdown(f"- Lineup count: {lineup_count} lineups")
    st.markdown(f"- Uniqueness: {uniqueness_pct}% (≥{math.ceil(9 * uniqueness_pct / 100)} unique players per lineup)")
    
    # Estimated Time
    time_color = "green" if validation_result['estimated_time'] < 30 else "yellow" if validation_result['estimated_time'] < 60 else "red"
    st.markdown(f"**Estimated Generation Time:** <span style='color: {time_color};'>~{validation_result['estimated_time']} seconds</span>", 
                unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

