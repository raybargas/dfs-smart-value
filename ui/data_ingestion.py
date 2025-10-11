"""
Data Ingestion UI Component

This module implements the Streamlit UI for uploading and validating player data files.
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any
import sys
from pathlib import Path

# Add src directory to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from parser import load_and_validate_player_data
from opponent_lookup import build_opponent_lookup


def render_data_ingestion():
    """
    Render the data ingestion UI component.
    
    Provides file upload, parsing, validation, and data display functionality.
    """
    # Header - more compact
    st.markdown("### 🏈 DFS Lineup Optimizer")
    st.markdown("#### 📁 Upload Player Data")
    
    # Instructions
    with st.expander("ℹ️ Upload Instructions", expanded=False):
        st.markdown("""
        **Required Columns:**
        - Player Name (or Name, Player)
        - Position (or Pos)
        - Salary (or Cost, Price)
        - Projection (or Proj, FPPG, Points)
        
        **Optional Columns:**
        - Team
        - Opponent
        - Ownership (or Own, Own%)
        - Player ID
        
        **Supported Formats:** CSV (.csv), Excel (.xlsx, .xls)
        
        **Data Requirements:**
        - Salary range: $3,000 - $10,000
        - Valid positions: QB, RB, WR, TE, DST
        - Projections must be positive numbers
        """)
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a CSV or Excel file",
        type=['csv', 'xlsx', 'xls'],
        help="Upload your weekly player projections file",
        key="player_data_uploader",
        accept_multiple_files=False,
        disabled=False
    )
    
    # Quick test data button
    if st.button("📁 Load Test Data", help="Load the sample test data for testing"):
        try:
            import io
            import os
            # Get the absolute path to test_data.csv
            current_dir = os.path.dirname(os.path.abspath(__file__))
            test_file_path = os.path.join(current_dir, "..", "test_data.csv")
            
            if os.path.exists(test_file_path):
                with open(test_file_path, 'rb') as f:
                    file_content = f.read()
                    uploaded_file = io.BytesIO(file_content)
                    uploaded_file.name = "test_data.csv"
                    st.session_state['uploaded_test_file'] = uploaded_file
                    st.success("✅ Test data loaded successfully!")
                    st.rerun()  # Trigger processing
            else:
                st.error(f"Test data file not found at: {test_file_path}")
        except Exception as e:
            st.error(f"Error loading test data: {e}")
            import traceback
            st.error(traceback.format_exc())
    
    # Check if we already have loaded data and should just display it
    if 'player_data' in st.session_state and st.session_state['player_data'] is not None and uploaded_file is None:
        # Display previously loaded data
        df = st.session_state['player_data']
        summary = st.session_state.get('data_summary', {})
        if summary:
            display_success_message(summary)
            display_data_summary(summary)
            display_continue_button()
        return
    
    # Process uploaded file (either from uploader or test data button)
    if 'uploaded_test_file' in st.session_state and st.session_state['uploaded_test_file'] is not None:
        uploaded_file = st.session_state['uploaded_test_file']
        # Clear after retrieving
        del st.session_state['uploaded_test_file']
    
    if uploaded_file is not None:
        try:
            with st.spinner("📊 Parsing file..."):
                # Parse and validate
                df, summary = load_and_validate_player_data(uploaded_file)
                
                # Store in session state
                st.session_state['player_data'] = df
                st.session_state['data_summary'] = summary
                
                # Build opponent lookup from Vegas lines (Week 6 - current week)
                # This creates a clean team -> opponent mapping
                # TODO: Make week dynamic based on current NFL week
                opponent_map = build_opponent_lookup(week=6, db_path="dfs_optimizer.db")
                st.session_state['opponent_lookup'] = opponent_map
            
            # Clear any cached DFS metrics, season stats, and smart value when new data is loaded
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
            
            # Display success and summary
            display_success_message(summary)
            display_data_summary(summary)
            display_continue_button()
            
        except KeyError as e:
            display_missing_column_error(str(e), uploaded_file.name)
        except ValueError as e:
            display_value_error(str(e))
        except pd.errors.ParserError as e:
            display_parser_error(str(e))
        except Exception as e:
            display_generic_error(str(e))
    
    else:
        # Show placeholder when no file uploaded
        display_upload_placeholder()


def display_success_message(summary: Dict[str, Any]) -> None:
    """Display success message with player count."""
    total = summary['total_players']
    st.success(f"✅ Successfully loaded {total} players")


def display_data_summary(summary: Dict[str, Any]) -> None:
    """Display position breakdown."""
    st.markdown("##### 📊 Position Breakdown")
    
    # Position breakdown in columns - more compact
    position_breakdown = summary['position_breakdown']
    if position_breakdown:
        cols = st.columns(len(position_breakdown))
        for i, (pos, count) in enumerate(sorted(position_breakdown.items())):
            with cols[i]:
                st.markdown(f"**{pos}:** {count}")


def display_continue_button() -> None:
    """Display button to proceed to next step."""
    st.write("")  # Spacing
    if st.button("▶️ Next: View Narrative Intelligence", type="primary", use_container_width=True, help="Continue to narrative intelligence view"):
        st.session_state['page'] = 'narrative_intelligence'
        st.rerun()


def display_upload_placeholder() -> None:
    """Display placeholder when no file is uploaded."""
    st.info("👆 Please upload a player data file to get started")
    
    # Sample data format
    with st.expander("📄 Example Data Format"):
        sample_data = pd.DataFrame({
            'Name': ['Patrick Mahomes', 'Christian McCaffrey', 'Tyreek Hill'],
            'Position': ['QB', 'RB', 'WR'],
            'Salary': [8500, 9200, 8000],
            'Projection': [24.2, 22.1, 21.8],
            'Team': ['KC', 'SF', 'MIA'],
            'Opponent': ['LV', '@ARI', '@BUF'],
            'Ownership': [28.5, 32.0, 22.3]
        })
        st.dataframe(sample_data, hide_index=True)


def display_missing_column_error(error_msg: str, filename: str) -> None:
    """Display error for missing required columns."""
    st.error("❌ Missing Required Column")
    st.write(error_msg)
    
    st.write("**Suggestions:**")
    st.write("- Check that your file has columns for: Name, Position, Salary, Projection")
    st.write("- Column names can vary (e.g., 'Proj' instead of 'Projection')")
    st.write("- Ensure the first row contains column headers")
    
    with st.expander("See supported column name variations"):
        st.markdown("""
        - **Name:** Name, Player, Player Name
        - **Position:** Position, Pos
        - **Salary:** Salary, Cost, Price
        - **Projection:** Projection, Proj, FPPG, Points
        """)


def display_value_error(error_msg: str) -> None:
    """Display error for value errors (unsupported format, conversion issues)."""
    st.error("❌ Data Error")
    st.write(error_msg)
    
    if "Unsupported file format" in error_msg:
        st.write("**Supported Formats:**")
        st.write("- CSV files (.csv)")
        st.write("- Excel files (.xlsx, .xls)")
    elif "Cannot convert" in error_msg:
        st.write("**Suggestions:**")
        st.write("- Check that numeric columns (Salary, Projection) contain only numbers")
        st.write("- Remove any text or special characters from numeric fields")
        st.write("- Ensure there are no blank rows in your data")


def display_parser_error(error_msg: str) -> None:
    """Display error for file parsing issues."""
    st.error("❌ File Parsing Error")
    st.write("Your file appears to be malformed or corrupted.")
    st.write("")
    st.write(f"**Error Details:** {error_msg}")
    st.write("")
    
    st.write("**Suggestions:**")
    st.write("- Ensure the file is a valid CSV or Excel file")
    st.write("- Check for extra commas or inconsistent column counts")
    st.write("- Try opening the file in Excel/Google Sheets and re-saving")
    st.write("- For CSV files, ensure encoding is UTF-8")


def display_generic_error(error_msg: str) -> None:
    """Display generic error message."""
    st.error("❌ An Error Occurred")
    st.write("An unexpected error occurred while processing your file.")
    st.write("")
    st.write(f"**Error Details:** {error_msg}")
    st.write("")
    st.write("Please check your file format and try again. If the problem persists, contact support.")

