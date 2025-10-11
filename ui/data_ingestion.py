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
from styles import (
    get_base_styles,
    get_hero_section_styles,
    get_upload_zone_styles,
    get_card_styles,
    get_badge_styles
)


def render_data_ingestion():
    """
    Render the data ingestion UI component.
    
    Provides file upload, parsing, validation, and data display functionality.
    """
    # Apply modern styles
    st.markdown(get_base_styles(), unsafe_allow_html=True)
    st.markdown(get_card_styles(), unsafe_allow_html=True)
    st.markdown(get_badge_styles(), unsafe_allow_html=True)
    
    # ULTRA-COMPACT Header: Single line, inline everything
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.5rem 0; margin-bottom: 0.75rem;">
        <div style="display: flex; align-items: baseline; gap: 1rem;">
            <h2 style="margin: 0; font-size: 1.5rem; font-weight: 700; display: inline;">
                🏈 <span class="gradient-text">DFS Lineup Optimizer</span>
            </h2>
            <span style="color: #707070; font-size: 0.875rem;">Smart Value-Driven Builder</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Ultra-compact 2-column layout: Upload | Info
    col_upload, col_help = st.columns([4, 0.5])
    
    with col_upload:
        uploaded_file = st.file_uploader(
            "📂 Upload Player Data",
            type=['csv', 'xlsx', 'xls'],
            help="Upload CSV or Excel file with player data",
            key="player_data_uploader",
            label_visibility="visible"
        )
    
    with col_help:
        st.markdown('<div style="padding-top: 1.75rem;">', unsafe_allow_html=True)
        with st.expander("ℹ️"):
            st.caption("**Need:** Name, Pos, Salary, Proj")
            st.caption("**Formats:** CSV, Excel")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Auto-load saved dataset on first visit (if no data in session and no upload)
    if 'player_data' not in st.session_state or st.session_state['player_data'] is None:
        if uploaded_file is None and 'auto_loaded' not in st.session_state:
            # Try to auto-load the saved dataset
            import os
            import io
            current_dir = os.path.dirname(os.path.abspath(__file__))
            test_file_path = os.path.join(current_dir, "..", "DKSalaries_Week6_2025.xlsx")
            
            if os.path.exists(test_file_path):
                try:
                    with open(test_file_path, 'rb') as f:
                        file_content = f.read()
                        uploaded_file = io.BytesIO(file_content)
                        uploaded_file.name = "DKSalaries_Week6_2025.xlsx"
                        st.session_state['auto_loaded'] = True
                except Exception:
                    pass
    
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
    
    # Determine if this is from auto-load
    is_from_auto_load = st.session_state.get('auto_loaded', False)
    if is_from_auto_load:
        # Clear the flag after first use
        if 'auto_loaded' in st.session_state:
            del st.session_state['auto_loaded']
    
    if uploaded_file is not None:
        try:
            with st.spinner("📊 Parsing file..."):
                # Parse and validate
                df, summary = load_and_validate_player_data(uploaded_file)
                
                # Store in session state
                st.session_state['player_data'] = df
                st.session_state['data_summary'] = summary
                
                # Save uploaded file as new default dataset (only if manually uploaded, not auto-loaded)
                if not is_from_auto_load:
                    try:
                        import os
                        import datetime
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        test_file_path = os.path.join(current_dir, "..", "DKSalaries_Week6_2025.xlsx")
                        timestamp_file = os.path.join(current_dir, "..", "last_upload_timestamp.txt")
                        
                        # Reset file pointer to beginning
                        uploaded_file.seek(0)
                        
                        # Save uploaded file content to test data location
                        with open(test_file_path, 'wb') as f:
                            f.write(uploaded_file.read())
                        
                        # Save timestamp
                        with open(timestamp_file, 'w') as f:
                            f.write(datetime.datetime.now().isoformat())
                        
                        # Reset pointer again for further processing
                        uploaded_file.seek(0)
                    except Exception as save_error:
                        # Non-critical error - just log it
                        pass
                
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
            display_success_message(summary, is_from_auto_load)
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


def display_success_message(summary: Dict[str, Any], is_from_auto_load: bool = False) -> None:
    """Display success message with player count - compact inline."""
    total = summary['total_players']
    position_breakdown = summary.get('position_breakdown', {})
    
    # Compact inline summary with position counts
    positions_text = " · ".join([f"{pos}: {count}" for pos, count in sorted(position_breakdown.items())])
    
    # Get timestamp info if available
    import os
    import datetime
    current_dir = os.path.dirname(os.path.abspath(__file__))
    timestamp_file = os.path.join(current_dir, "..", "last_upload_timestamp.txt")
    
    last_updated_text = ""
    if os.path.exists(timestamp_file):
        try:
            with open(timestamp_file, 'r') as f:
                timestamp_str = f.read().strip()
                upload_time = datetime.datetime.fromisoformat(timestamp_str)
                
                # Calculate time ago
                now = datetime.datetime.now()
                diff = now - upload_time
                
                if diff.days > 0:
                    last_updated_text = f"{diff.days}d ago"
                elif diff.seconds >= 3600:
                    hours = diff.seconds // 3600
                    last_updated_text = f"{hours}h ago"
                elif diff.seconds >= 60:
                    minutes = diff.seconds // 60
                    last_updated_text = f"{minutes}m ago"
                else:
                    last_updated_text = "Just now"
        except:
            pass
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.success(f"✅ Loaded **{total} players** · {positions_text}")
        if is_from_auto_load and last_updated_text:
            st.caption(f"🕒 Dataset from {last_updated_text}")
        elif not is_from_auto_load:
            st.caption("💾 Saved as default dataset")
    with col2:
        if st.button("▶️ Continue", 
                     type="primary", 
                     use_container_width=True, 
                     help="Continue to Narrative Intelligence",
                     key="continue_to_narrative"):
            st.session_state['page'] = 'narrative_intelligence'
            st.rerun()


def display_data_summary(summary: Dict[str, Any]) -> None:
    """Position breakdown already shown inline - skip separate section."""
    pass


def display_continue_button() -> None:
    """Continue button already shown inline - skip separate button."""
    pass


def display_upload_placeholder() -> None:
    """Display compact placeholder when no file is uploaded."""
    st.info("👆 Upload CSV/Excel to get started")


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

