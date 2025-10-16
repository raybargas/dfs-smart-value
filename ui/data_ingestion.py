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
    
    # Week selector
    col1, col2 = st.columns([1, 3])
    
    with col1:
        selected_week = st.selectbox(
            "NFL Week",
            options=list(range(1, 19)),
            index=st.session_state.get('current_week', 7) - 1,
            help="Select the NFL week for analysis",
            key="week_selector"
        )
        
        # Update session state if week changed
        if selected_week != st.session_state.get('current_week', 7):
            st.session_state['current_week'] = selected_week
            
            # Try to load historical data for this week from database
            try:
                from historical_data_manager import HistoricalDataManager
                import datetime
                
                manager = HistoricalDataManager()
                historical_df = manager.load_historical_snapshot(
                    week=selected_week,
                    season=2024,
                    site='DraftKings'
                )
                manager.close()
                
                if historical_df is not None and not historical_df.empty:
                    # Found historical data for this week - load it
                    summary = {
                        'total_players': len(historical_df),
                        'positions': historical_df['position'].value_counts().to_dict(),
                        'salary_min': int(historical_df['salary'].min()),
                        'salary_max': int(historical_df['salary'].max()),
                        'salary_avg': int(historical_df['salary'].mean()),
                        'teams': historical_df['team'].nunique()
                    }
                    
                    # Get metadata from slate
                    slate_meta = manager.get_slate_metadata(
                        week=selected_week,
                        season=2024,
                        site='DraftKings'
                    )
                    
                    st.session_state['player_data'] = historical_df
                    st.session_state['data_summary'] = summary
                    st.session_state['data_source'] = 'historical'
                    st.session_state['data_week'] = selected_week
                    
                    if slate_meta and 'created_at' in slate_meta:
                        st.session_state['data_loaded_at'] = datetime.datetime.fromisoformat(slate_meta['created_at'])
                    
                    st.info(f"📚 Loaded historical data for Week {selected_week}")
                else:
                    # No historical data - clear session
                    if 'player_data' in st.session_state:
                        del st.session_state['player_data']
                    if 'data_summary' in st.session_state:
                        del st.session_state['data_summary']
            except Exception as e:
                # If historical load fails, just clear the data
            if 'player_data' in st.session_state:
                del st.session_state['player_data']
            if 'data_summary' in st.session_state:
                del st.session_state['data_summary']
            
            st.rerun()
    
    with col2:
        st.caption(f"📅 Analyzing Week {selected_week} data")
    
    # Two-column layout: Upload or Auto-Fetch
    col_upload, col_fetch = st.columns([3, 1])
    
    with col_upload:
    uploaded_file = st.file_uploader(
            "Upload file",
        type=['csv', 'xlsx', 'xls'],
        help="Upload CSV or Excel file with player data",
        key="player_data_uploader",
            label_visibility="collapsed"
        )
    
    with col_fetch:
        if st.button(
            "📡 Fetch from API",
            help="Fetch DFS salaries from MySportsFeeds API for selected week",
            use_container_width=True,
            type="secondary"
        ):
            # Check if API key is set
            import os
            api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
            
            if not api_key:
                st.error("""
                ❌ **MySportsFeeds API Key not found**
                
                Set your API key:
                ```bash
                export MYSPORTSFEEDS_API_KEY="your_key_here"
                ```
                
                Or provide it manually in the sidebar.
                """)
            else:
                with st.spinner(f"🔄 Fetching Week {selected_week} salaries from MySportsFeeds..."):
                    try:
                        # Import Wednesday data prep workflow
                        from historical_data_manager import HistoricalDataManager
                        from api.dfs_salaries_api import fetch_salaries
                        
                        # Fetch salaries
                        df_salaries = fetch_salaries(
                            api_key=api_key,
                            week=selected_week,
                            season=2024,
                            site='draftkings'
                        )
                        
                        if df_salaries is not None and not df_salaries.empty:
                            # Filter to SUNDAY MAIN SLATE ONLY
                            # MySportsFeeds returns ALL slates (33+) for the entire week
                            # We want the biggest slate = Sunday afternoon main slate (~10-14 games)
                            original_count = len(df_salaries)
                            
                            if 'slate_label' in df_salaries.columns:
                                # Count players per slate to find the biggest one (= main Sunday slate)
                                slate_counts = df_salaries.groupby('slate_label').size()
                                main_slate = slate_counts.idxmax()  # Slate with most players = main slate
                                df_salaries = df_salaries[df_salaries['slate_label'] == main_slate].copy()
                            
                            # Remove duplicate players (keep first occurrence)
                            if 'player_name' in df_salaries.columns:
                                df_salaries = df_salaries.drop_duplicates(subset=['player_name'], keep='first')
                            
                            # Filter to only players with projections > 0
                            if 'projection' in df_salaries.columns:
                                df_salaries = df_salaries[df_salaries['projection'] > 0].copy()
                        
                        if df_salaries is not None and not df_salaries.empty:
                            # Create slate and store (for historical tracking)
                            manager = HistoricalDataManager()
                            try:
                                # Extract games from data
                                games = []
                                if 'opponent' in df_salaries.columns:
                                    teams = df_salaries['team'].unique().tolist()
                                    for i in range(0, len(teams), 2):
                                        if i + 1 < len(teams):
                                            games.append(f"{teams[i]}@{teams[i+1]}")
                                
                                # Create slate
                                slate_id = manager.create_slate(
                                    week=selected_week,
                                    season=2024,
                                    site='DraftKings',
                                    contest_type='Classic',
                                    games=games
                                )
                                
                                # Store player pool
                                manager.store_player_pool_snapshot(
                                    slate_id=slate_id,
                                    player_data=df_salaries,
                                    smart_value_profile=None,
                                    projection_source='mysportsfeeds_dfs',
                                    ownership_source='pending'
                                )
                                
                                st.success(f"✅ Created slate: {slate_id}")
                            except ValueError as e:
                                if "already exists" in str(e):
                                    st.info(f"ℹ️ Slate already exists for Week {selected_week}")
                                else:
                                    st.warning(f"⚠️ Could not create slate: {e}")
                            finally:
                                manager.close()
                            
                            # Parse and validate (same as manual upload)
                            summary = {
                                'total_players': len(df_salaries),
                                'positions': df_salaries['position'].value_counts().to_dict(),
                                'salary_min': int(df_salaries['salary'].min()),
                                'salary_max': int(df_salaries['salary'].max()),
                                'salary_avg': int(df_salaries['salary'].mean()),
                                'teams': df_salaries['team'].nunique()
                            }
                            
                            # Store in session state with timestamp and week
                            import datetime
                            st.session_state['player_data'] = df_salaries
                            st.session_state['data_summary'] = summary
                            st.session_state['data_source'] = 'api'
                            st.session_state['data_loaded_at'] = datetime.datetime.now()
                            st.session_state['data_week'] = selected_week
                            
                            st.success(f"✅ Fetched {len(df_salaries)} players from MySportsFeeds API!")
                            st.rerun()
                        else:
                            st.error("❌ No salary data found for this week")
                    
                    except Exception as e:
                        st.error(f"❌ Failed to fetch data: {str(e)}")
                        st.info("""
                        **Troubleshooting**:
                        - Verify your MySportsFeeds API key is correct
                        - Ensure you have the "DFS" addon in your subscription
                        - Check that Week {selected_week} salaries are available
                        
                        **Manual fallback**: Upload CSV/Excel file instead.
                        """.format(selected_week=selected_week))
    
    # Track if this is a manual upload (from file uploader widget)
    is_manual_upload = uploaded_file is not None
    
    # Auto-load data on first visit (if no data in session and no manual upload)
    if 'player_data' not in st.session_state or st.session_state['player_data'] is None:
        if not is_manual_upload and 'auto_loaded' not in st.session_state:
            # PRIORITY 1: Try to load historical data for current week from database
            try:
                from historical_data_manager import HistoricalDataManager
                import datetime
                
                manager = HistoricalDataManager()
                historical_df = manager.load_historical_snapshot(
                    week=selected_week,
                    season=2024,
                    site='DraftKings'
                )
                
                if historical_df is not None and not historical_df.empty:
                    # Found historical data - load it
                    summary = {
                        'total_players': len(historical_df),
                        'positions': historical_df['position'].value_counts().to_dict(),
                        'salary_min': int(historical_df['salary'].min()),
                        'salary_max': int(historical_df['salary'].max()),
                        'salary_avg': int(historical_df['salary'].mean()),
                        'teams': historical_df['team'].nunique()
                    }
                    
                    # Get metadata
                    slate_meta = manager.get_slate_metadata(
                        week=selected_week,
                        season=2024,
                        site='DraftKings'
                    )
                    
                    st.session_state['player_data'] = historical_df
                    st.session_state['data_summary'] = summary
                    st.session_state['data_source'] = 'historical'
                    st.session_state['data_week'] = selected_week
                    
                    if slate_meta and 'created_at' in slate_meta:
                        st.session_state['data_loaded_at'] = datetime.datetime.fromisoformat(slate_meta['created_at'])
                    
                    st.session_state['auto_loaded'] = True
                    manager.close()
                else:
                    manager.close()
                    # PRIORITY 2: Fallback to old CSV file if no historical data
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
            except Exception:
                # If historical load fails, try CSV fallback
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
    
    # Determine if this is from auto-load (only True if auto-load just happened)
    is_from_auto_load = st.session_state.get('auto_loaded', False) and not is_manual_upload
    
    # Clear auto-load flag after first use
    if 'auto_loaded' in st.session_state:
        del st.session_state['auto_loaded']
    
    if uploaded_file is not None:
        try:
            with st.spinner("📊 Parsing file..."):
                # Parse and validate
                df, summary = load_and_validate_player_data(uploaded_file)
                
                # Store in session state with metadata
                import datetime
                st.session_state['player_data'] = df
                st.session_state['data_summary'] = summary
                st.session_state['data_source'] = 'csv'
                st.session_state['data_loaded_at'] = datetime.datetime.now()
                st.session_state['data_week'] = selected_week
                
                # Save uploaded file as new default dataset (only if manually uploaded)
                if is_manual_upload:
                    try:
                        import os
                        import datetime
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        test_file_path = os.path.join(current_dir, "..", "DKSalaries_Week6_2025.xlsx")
                        timestamp_file = os.path.join(current_dir, "..", "last_upload_timestamp.txt")
                        
                        # Reset file pointer to beginning
                        uploaded_file.seek(0)
                        file_content = uploaded_file.read()
                        
                        # Save uploaded file content to test data location
                        with open(test_file_path, 'wb') as f:
                            f.write(file_content)
                        
                        # Save timestamp
                        current_time = datetime.datetime.now()
                        with open(timestamp_file, 'w') as f:
                            f.write(current_time.isoformat())
                        
                        # Mark that we successfully saved
                        st.session_state['manual_upload_saved'] = True
                        
                    except Exception as save_error:
                        # Show error but don't fail the upload
                        st.warning(f"⚠️ Could not save as default dataset: {save_error}")
                        st.session_state['manual_upload_saved'] = False
                
                # Build opponent lookup from Vegas lines for selected week
                # This creates a clean team -> opponent mapping
                current_week = st.session_state.get('current_week', 7)
                opponent_map = build_opponent_lookup(week=current_week, db_path="dfs_optimizer.db")
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
    import datetime
    
    total = summary['total_players']
    position_breakdown = summary.get('position_breakdown', {})
    
    # Compact inline summary with position counts
    positions_text = " · ".join([f"{pos}: {count}" for pos, count in sorted(position_breakdown.items())])
    
    # Get timestamp and source from session state (new method)
    data_source = st.session_state.get('data_source', 'unknown')
    data_loaded_at = st.session_state.get('data_loaded_at')
    data_week = st.session_state.get('data_week', st.session_state.get('current_week', 7))
                
                # Calculate time ago
    last_updated_text = "recently"
    if data_loaded_at:
                now = datetime.datetime.now()
        diff = now - data_loaded_at
                
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
    
    # Build source-specific caption
    if data_source == 'api':
        source_icon = "📡"
        source_text = f"Fetched from API · Week {data_week}"
    elif data_source == 'csv':
        source_icon = "📂"
        source_text = f"CSV Upload · Week {data_week}"
    elif data_source == 'historical':
        source_icon = "📚"
        source_text = f"Historical Data · Week {data_week}"
    else:
        source_icon = "💾"
        source_text = f"Loaded · Week {data_week}"
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.success(f"✅ Loaded **{total} players** · {positions_text}")
        st.caption(f"{source_icon} {source_text} · {last_updated_text}")
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

