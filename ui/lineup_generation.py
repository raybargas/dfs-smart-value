"""
Lineup Generation UI Component

This module implements the Streamlit UI wrapper for triggering lineup optimization
and handling results/errors. It calls the optimizer engine and manages navigation.
"""

import streamlit as st
import time
from pathlib import Path
import sys

# Add src directory to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from optimizer import generate_lineups


def render_lineup_generation():
    """
    Lineup Generation UI Component.
    
    This component:
    1. Validates that required session state data exists (config + player pool)
    2. Triggers lineup generation by calling the optimizer
    3. Stores results in session state for the results display page
    4. Handles errors by showing partial results and retry options
    5. Auto-navigates to results page on success
    
    This is a "pass-through" component - it runs immediately on load, shows
    progress, and navigates to the next page. Users don't interact with it directly.
    """
    
    # Apply compact styles
    from src.styles import get_base_styles, get_card_styles
    st.markdown(get_base_styles(), unsafe_allow_html=True)
    st.markdown(get_card_styles(), unsafe_allow_html=True)
    
    # Step 1: Validate session state (prerequisite checks)
    if 'optimization_config' not in st.session_state or 'player_pool' not in st.session_state:
        # Missing data - show error and provide navigation back
        st.error("⚠️ Missing configuration. Please go back to Optimization Configuration.")
        
        if st.button("⬅️ Back to Configuration", type="primary"):
            st.session_state['page'] = 'optimization'
            st.rerun()
        
        return  # Exit early if validation fails
    
    # Step 2: Read configuration from session state
    config = st.session_state['optimization_config']
    player_pool_df = st.session_state['player_pool']
    
    # Step 3: Apply Smart Value filter (if enabled)
    filter_strategy = config.get('filter_strategy', 'simple')
    min_smart_value = config.get('min_smart_value', 0)
    positional_floors = config.get('positional_floors', None)
    portfolio_avg_sv = config.get('portfolio_avg_smart_value', None)
    
    # Pre-filtering for simple/positional modes (portfolio uses LP constraint)
    if filter_strategy in ['simple', 'positional'] and 'smart_value' in player_pool_df.columns:
        original_count = len(player_pool_df)
        
        if filter_strategy == 'simple' and min_smart_value > 0:
            # Global filter
            player_pool_df = player_pool_df[player_pool_df['smart_value'] >= min_smart_value].copy()
            st.caption(f"📊 Pool filtered: {original_count} → {len(player_pool_df)} players (Smart Value ≥ {min_smart_value})")
            
        elif filter_strategy == 'positional' and positional_floors:
            # Position-specific filter
            def meets_threshold(row):
                threshold = positional_floors.get(row['position'], 0)
                return row['smart_value'] >= threshold
            
            player_pool_df = player_pool_df[player_pool_df.apply(meets_threshold, axis=1)].copy()
            
            # Show position-wise filtering
            filter_summary = ", ".join([f"{pos}≥{val}" for pos, val in positional_floors.items()])
            st.caption(f"📊 Pool filtered: {original_count} → {len(player_pool_df)} players ({filter_summary})")
        
        # Validate we still have enough players per position
        if len(player_pool_df) < original_count:  # Only validate if filtering was applied
            position_counts = player_pool_df.groupby('position').size()
            min_required = {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 1, 'DST': 1}
            
            for pos, min_count in min_required.items():
                actual_count = position_counts.get(pos, 0)
                if actual_count < min_count:
                    st.error(f"⚠️ Not enough {pos}s after filtering (need {min_count}, have {actual_count}). Lower your Smart Value threshold.")
                    if st.button("⬅️ Back to Configuration"):
                        st.session_state['page'] = 'optimization'
                        st.rerun()
                    return
    
    # For portfolio mode, show info (constraint applied in optimizer)
    elif filter_strategy == 'portfolio' and portfolio_avg_sv:
        st.caption(f"📊 Portfolio constraint: Lineup average Smart Value ≥ {portfolio_avg_sv}")
    
    # ULTRA-COMPACT Loading message
    st.markdown(f"""
    <div style="text-align: center; padding: 1rem 0; margin-bottom: 1rem;">
        <h2 style="margin: 0; font-size: 1.5rem; font-weight: 700;">
            🔄 <span class="gradient-text">Generating {config['lineup_count']} Lineups</span>
        </h2>
        <p style="color: #707070; font-size: 0.875rem; margin: 0.5rem 0 0 0;">Please wait...</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Add a progress indicator
    with st.spinner("Optimizing lineups with PuLP solver..."):
        # Step 4: Call optimizer with timing
        start_time = time.time()
        
        lineups, error = generate_lineups(
            player_pool_df=player_pool_df,
            lineup_count=config['lineup_count'],
            uniqueness_pct=config['uniqueness_pct'],
            max_ownership_enabled=config.get('max_ownership_enabled', False),
            max_ownership_pct=config.get('max_ownership_pct', None),
            stacking_enabled=config.get('stacking_enabled', True),  # Default ON for GPPs
            portfolio_avg_smart_value=portfolio_avg_sv  # For portfolio mode
        )
        
        generation_time = time.time() - start_time
    
    # Step 5: Store results in session state (for results display page)
    st.session_state['lineups'] = lineups
    st.session_state['generation_metadata'] = {
        'lineups_requested': config['lineup_count'],
        'lineups_generated': len(lineups),
        'generation_time_seconds': generation_time,
        'error_message': error,
        'uniqueness_pct': config['uniqueness_pct'],
        'player_pool_size': len(player_pool_df),  # After filtering
        'filter_strategy': config.get('filter_strategy', 'simple'),
        'min_smart_value': config.get('min_smart_value', 0),  # For simple mode
        'positional_floors': config.get('positional_floors', None),  # For positional mode
        'portfolio_avg_smart_value': config.get('portfolio_avg_smart_value', None),  # For portfolio mode
        'max_ownership_enabled': config.get('max_ownership_enabled', False),
        'max_ownership_pct': config.get('max_ownership_pct', None)
    }
    
    # Step 6: Handle results (success vs partial failure)
    if error:
        # Partial success - show warning and options
        st.warning(f"⚠️ {error}")
        
        if len(lineups) > 0:
            st.success(f"✅ Successfully generated **{len(lineups)}** of {config['lineup_count']} lineups in **{generation_time:.1f} seconds**.")
            
            st.info("""
            **Note:** The optimizer couldn't generate the full batch. 
            This typically means the uniqueness constraint was too tight for your player pool size.
            """)
            
            # COMPACT navigation: adjust or view results
            col1, col2 = st.columns([1, 4])
            
            with col1:
                if st.button("⬅️ Adjust", use_container_width=True, help="Go back to adjust settings"):
                    st.session_state['page'] = 'optimization'
                    st.rerun()
            
            with col2:
                if st.button("▶️ View Results", type="primary", use_container_width=True):
                    st.session_state['page'] = 'results'
                    st.rerun()
        else:
            # No lineups generated - critical failure
            st.error("❌ Could not generate any lineups. Please adjust your settings and try again.")
            
            st.info("""
            **Possible issues:** Player pool too small, uniqueness too tight, or ownership filter too strict.
            """)
            
            if st.button("⬅️ Back to Configuration", type="primary", use_container_width=True):
                st.session_state['page'] = 'optimization'
                st.rerun()
    else:
        # Full success - show success message and auto-navigate
        st.success(f"✅ Generated **{len(lineups)} lineups** in **{generation_time:.1f} seconds**!")
        
        # Brief pause to let user see the success message
        time.sleep(0.5)
        
        # Auto-navigate to results page
        st.session_state['page'] = 'results'
        st.rerun()

