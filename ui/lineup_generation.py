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
    
    # Step 1: Validate session state (prerequisite checks)
    if 'optimization_config' not in st.session_state or 'player_pool' not in st.session_state:
        # Missing data - show error and provide navigation back
        st.error("⚠️ Missing configuration. Please go back to Optimization Configuration.")
        
        if st.button("← Back to Configuration", type="primary"):
            st.session_state['page'] = 'optimization'
            st.rerun()
        
        return  # Exit early if validation fails
    
    # Step 2: Read configuration from session state
    config = st.session_state['optimization_config']
    player_pool_df = st.session_state['player_pool']
    
    # Step 3: Display generation status message
    st.markdown(f"""
    <div style="text-align: center; margin: 2rem 0;">
        <h2 style="color: #f9fafb;">🔄 Generating {config['lineup_count']} Lineups...</h2>
        <p style="color: #9ca3af;">Please wait while we optimize your lineups.</p>
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
            optimization_objective=config.get('optimization_objective', 'projection')
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
        'player_pool_size': len(player_pool_df),
        'max_ownership_enabled': config.get('max_ownership_enabled', False),
        'max_ownership_pct': config.get('max_ownership_pct', None),
        'optimization_objective': config.get('optimization_objective', 'projection')
    }
    
    # Step 6: Handle results (success vs partial failure)
    if error:
        # Partial success - show warning and options
        st.warning(f"⚠️ {error}")
        
        if len(lineups) > 0:
            st.success(f"✅ Successfully generated **{len(lineups)}** of {config['lineup_count']} lineups in **{generation_time:.1f} seconds**.")
            
            st.markdown("""
            **What happened?**  
            The optimizer successfully generated some lineups but couldn't complete the full batch. 
            This typically means the uniqueness constraint was too tight for your player pool size.
            """)
            
            # Show two options: adjust settings or view partial results
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("← Adjust Settings and Retry", use_container_width=True):
                    st.session_state['page'] = 'optimization'
                    st.rerun()
            
            with col2:
                if st.button("View Results →", type="primary", use_container_width=True):
                    st.session_state['page'] = 'results'
                    st.rerun()
        else:
            # No lineups generated - critical failure
            st.error("❌ Could not generate any lineups. Please adjust your settings and try again.")
            
            st.markdown("""
            **Possible issues:**
            - Player pool too small for the uniqueness constraint
            - Ownership filter excluded too many players
            - Salary cap constraints impossible to satisfy
            """)
            
            if st.button("← Back to Configuration", type="primary", use_container_width=True):
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

