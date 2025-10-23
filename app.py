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
        layout="wide"
    )
    
    # Run database migrations once on startup (silent check)
    if 'migrations_checked' not in st.session_state:
        try:
            from migrations.run_migrations import run_all_migrations
            import io
            import sys
            
            # Suppress all migration output (including errors)
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            
            try:
                run_all_migrations()
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            
            st.session_state['migrations_checked'] = True
        except Exception:
            # Silent fail - migrations may already be complete
            # Database tables will be created on first use if missing
            st.session_state['migrations_checked'] = True
    
    # Initialize session state with persistence
    if 'page' not in st.session_state:
        st.session_state['page'] = 'data_ingestion'
    if 'player_data' not in st.session_state:
        st.session_state['player_data'] = None
    if 'selections' not in st.session_state:
        st.session_state['selections'] = {}
    if 'current_week' not in st.session_state:
        st.session_state['current_week'] = 8  # Default to current NFL week
    
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

