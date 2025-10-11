"""
DFS Lineup Optimizer - Main Streamlit Application

This is the main entry point for the DFS Lineup Optimizer web application.
"""

import streamlit as st
from ui.data_ingestion import render_data_ingestion
from ui.narrative_intelligence import show as render_narrative_intelligence
from ui.player_selection import render_player_selection
from ui.optimization_config import render_optimization_config
from ui.lineup_generation import render_lineup_generation
from ui.results import render_results


def main():
    """Main application entry point."""
    # Page configuration
    st.set_page_config(
        page_title="DFS Lineup Optimizer",
        page_icon="🏈",
        layout="wide",
        initial_sidebar_state="auto"  # Auto-collapse on mobile, expanded on desktop
    )
    
    # Initialize session state with persistence
    if 'page' not in st.session_state:
        st.session_state['page'] = 'data_ingestion'
    if 'player_data' not in st.session_state:
        st.session_state['player_data'] = None
    if 'selections' not in st.session_state:
        st.session_state['selections'] = {}
    
    # Route to appropriate page
    if st.session_state['page'] == 'data_ingestion':
        render_data_ingestion()
    elif st.session_state['page'] == 'narrative_intelligence':
        render_narrative_intelligence()
    elif st.session_state['page'] == 'player_selection':
        render_player_selection()
    elif st.session_state['page'] == 'optimization':
        render_optimization_config()
    elif st.session_state['page'] == 'lineup_generation':
        render_lineup_generation()
    elif st.session_state['page'] == 'results':
        render_results()


if __name__ == "__main__":
    main()

