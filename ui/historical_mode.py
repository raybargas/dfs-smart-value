"""
Historical Mode UI Component

This module provides UI components for running historical roster builds
using past week's data for testing and analysis.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import os
from typing import Dict, List, Optional

from src.database_models import create_session, VegasLine, InjuryReport
from src.data_cache import get_cache_status, list_cached_weeks


def get_current_nfl_week() -> int:
    """
    Calculate current NFL week based on date.
    NFL 2025 season starts September 4, 2025 (Week 1 Thursday).
    
    Returns:
        Current NFL week (1-18)
    """
    # NFL 2025 season start date (Week 1 Thursday)
    season_start = datetime(2025, 9, 4)
    current_date = datetime.now()
    
    # Calculate weeks since start
    days_since_start = (current_date - season_start).days
    week = (days_since_start // 7) + 1
    
    # Clamp to valid range (1-18)
    return max(1, min(18, week))


def render_historical_mode_selector():
    """
    Render the historical mode selector and week management interface.
    
    This component allows users to:
    1. Switch between current and historical mode
    2. Select specific weeks for analysis
    3. View available data for each week
    4. Fetch/load historical data
    """
    
    # Initialize session state for historical mode
    if 'historical_mode' not in st.session_state:
        st.session_state.historical_mode = False
    if 'selected_historical_week' not in st.session_state:
        st.session_state.selected_historical_week = get_current_nfl_week() - 1
    
    st.markdown("### 🕰️ Historical Analysis Mode")
    st.caption("Run roster builds using past week's data for testing and analysis")
    
    # Mode selector
    col1, col2 = st.columns([1, 2])
    
    with col1:
        historical_mode = st.toggle(
            "Historical Mode",
            value=st.session_state.historical_mode,
            help="Enable to use past week's data instead of current week"
        )
        
        if historical_mode != st.session_state.historical_mode:
            st.session_state.historical_mode = historical_mode
            st.rerun()
    
    with col2:
        if st.session_state.historical_mode:
            st.info("📊 **Historical Mode Active** - Using past week's data")
        else:
            st.info("📅 **Current Mode** - Using live/current week data")
    
    # Historical week selector (only show when in historical mode)
    if st.session_state.historical_mode:
        render_historical_week_selector()
    
    return st.session_state.historical_mode, st.session_state.selected_historical_week


def render_historical_week_selector():
    """Render the historical week selector with data availability info."""
    
    st.markdown("#### 📅 Select Historical Week")
    
    # Get available weeks from database
    available_weeks = get_available_data_weeks()
    
    # Week selector
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        selected_week = st.number_input(
            "Week",
            min_value=1,
            max_value=18,
            value=st.session_state.selected_historical_week,
            help="Select NFL week for historical analysis",
            key="historical_week_selector"
        )
        
        if selected_week != st.session_state.selected_historical_week:
            st.session_state.selected_historical_week = selected_week
            st.rerun()
    
    with col2:
        # Show data availability for selected week
        render_week_data_status(selected_week)
    
    with col3:
        # Quick actions
        if st.button("🔄 Load Week Data", help="Load data for selected week"):
            load_historical_week_data(selected_week)
    
    # Data management section
    render_data_management_section()


def render_week_data_status(week: int):
    """Render the data availability status for a specific week."""
    
    try:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dfs_optimizer.db")
        session = create_session(db_path)
        
        # Check Vegas data
        vegas_count = session.query(VegasLine).filter_by(week=week).count()
        
        # Check injury data
        injury_count = session.query(InjuryReport).filter_by(week=week).count()
        
        session.close()
        
        # Display status
        if vegas_count > 0 and injury_count > 0:
            st.success(f"✅ Week {week}: {vegas_count} games, {injury_count} injuries")
        elif vegas_count > 0 or injury_count > 0:
            st.warning(f"⚠️ Week {week}: {vegas_count} games, {injury_count} injuries (partial data)")
        else:
            st.error(f"❌ Week {week}: No data available")
            
    except Exception as e:
        st.error(f"❌ Error checking week {week} data: {str(e)}")


def render_data_management_section():
    """Render the data management section for historical weeks."""
    
    with st.expander("📊 Data Management", expanded=False):
        st.markdown("**Available Historical Data:**")
        
        # Get all available weeks
        try:
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dfs_optimizer.db")
            session = create_session(db_path)
            
            # Get weeks with Vegas data
            vegas_weeks = session.query(VegasLine.week).distinct().all()
            vegas_weeks = [w[0] for w in vegas_weeks] if vegas_weeks else []
            
            # Get weeks with injury data
            injury_weeks = session.query(InjuryReport.week).distinct().all()
            injury_weeks = [w[0] for w in injury_weeks] if injury_weeks else []
            
            session.close()
            
            if vegas_weeks or injury_weeks:
                all_weeks = sorted(set(vegas_weeks + injury_weeks))
                
                # Create a summary table
                data_summary = []
                for week in all_weeks:
                    vegas_count = vegas_weeks.count(week) if week in vegas_weeks else 0
                    injury_count = injury_weeks.count(week) if week in injury_weeks else 0
                    
                    data_summary.append({
                        'Week': week,
                        'Vegas Games': vegas_count,
                        'Injuries': injury_count,
                        'Status': 'Complete' if vegas_count > 0 and injury_count > 0 else 'Partial'
                    })
                
                df = pd.DataFrame(data_summary)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
            else:
                st.info("No historical data available. Use the API calls to fetch data for specific weeks.")
                
        except Exception as e:
            st.error(f"Error loading data summary: {str(e)}")
        
        # Cache management
        st.markdown("**Cache Management:**")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 Save Current Week to Cache"):
                save_current_week_to_cache()
        
        with col2:
            if st.button("📁 Load Week from Cache"):
                load_week_from_cache()


def get_available_data_weeks() -> Dict[str, List[int]]:
    """Get available weeks from database."""
    try:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dfs_optimizer.db")
        session = create_session(db_path)
        
        # Get weeks with Vegas data
        vegas_weeks = session.query(VegasLine.week).distinct().all()
        vegas_weeks = [w[0] for w in vegas_weeks] if vegas_weeks else []
        
        # Get weeks with injury data
        injury_weeks = session.query(InjuryReport.week).distinct().all()
        injury_weeks = [w[0] for w in injury_weeks] if injury_weeks else []
        
        session.close()
        
        return {
            'vegas': sorted(vegas_weeks),
            'injury': sorted(injury_weeks)
        }
    except Exception as e:
        st.error(f"Error getting available weeks: {str(e)}")
        return {'vegas': [], 'injury': []}


def load_historical_week_data(week: int):
    """Load data for a specific historical week."""
    
    try:
        from src.data_cache import load_vegas_lines_from_cache, load_injury_reports_from_cache
        
        with st.spinner(f"Loading Week {week} data..."):
            # Try to load from cache first
            vegas_loaded = load_vegas_lines_from_cache(week)
            injury_loaded = load_injury_reports_from_cache(week)
            
            if vegas_loaded and injury_loaded:
                st.success(f"✅ Loaded Week {week} data from cache")
            elif vegas_loaded or injury_loaded:
                st.warning(f"⚠️ Partially loaded Week {week} data from cache")
            else:
                st.info(f"ℹ️ No cached data for Week {week}. Use API calls to fetch fresh data.")
                
    except Exception as e:
        st.error(f"Error loading Week {week} data: {str(e)}")


def save_current_week_to_cache():
    """Save current week's data to cache."""
    
    try:
        from src.data_cache import save_vegas_lines_to_cache, save_injury_reports_to_cache
        
        current_week = st.session_state.get('current_week', get_current_nfl_week())
        
        with st.spinner(f"Saving Week {current_week} to cache..."):
            vegas_saved = save_vegas_lines_to_cache(current_week)
            injury_saved = save_injury_reports_to_cache(current_week)
            
            if vegas_saved and injury_saved:
                st.success(f"✅ Saved Week {current_week} to cache")
            elif vegas_saved or injury_saved:
                st.warning(f"⚠️ Partially saved Week {current_week} to cache")
            else:
                st.error(f"❌ Failed to save Week {current_week} to cache")
                
    except Exception as e:
        st.error(f"Error saving to cache: {str(e)}")


def load_week_from_cache():
    """Load week data from cache with week selection."""
    
    try:
        from src.data_cache import list_cached_weeks
        
        cached_weeks = list_cached_weeks()
        
        if cached_weeks:
            selected_week = st.selectbox(
                "Select week to load from cache:",
                options=cached_weeks,
                key="cache_week_selector"
            )
            
            if st.button("Load Selected Week"):
                load_historical_week_data(selected_week)
        else:
            st.info("No cached weeks available.")
            
    except Exception as e:
        st.error(f"Error loading from cache: {str(e)}")


def get_current_analysis_week() -> int:
    """
    Get the week number to use for analysis.
    
    Returns:
        Week number for analysis (historical week if in historical mode, current week otherwise)
    """
    if st.session_state.get('historical_mode', False):
        return st.session_state.get('selected_historical_week', get_current_nfl_week() - 1)
    else:
        return st.session_state.get('current_week', get_current_nfl_week())


def render_historical_mode_indicator():
    """Render a compact indicator showing current analysis mode."""
    
    if st.session_state.get('historical_mode', False):
        week = st.session_state.get('selected_historical_week', get_current_nfl_week() - 1)
        st.markdown(f"🕰️ **Historical Mode**: Analyzing Week {week}")
    else:
        week = st.session_state.get('current_week', get_current_nfl_week())
        st.markdown(f"📅 **Current Mode**: Analyzing Week {week}")
