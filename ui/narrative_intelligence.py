"""
Narrative Intelligence Tab - DFS Optimizer
Displays Vegas lines, injury reports, and contextual data
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import API clients
from src.api.odds_api import OddsAPIClient
from src.api.mysportsfeeds_api import MySportsFeedsClient
from src.database_models import create_session, VegasLine, InjuryReport


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


def get_available_data_weeks():
    """
    Check which weeks have cached data available.
    
    Returns:
        Dictionary with 'vegas' and 'injury' keys containing lists of available weeks
    """
    try:
        from sqlalchemy import func
        session = create_session()
        
        # Get weeks with Vegas data
        vegas_weeks = session.query(VegasLine.week).distinct().all()
        vegas_weeks = [w[0] for w in vegas_weeks] if vegas_weeks else []
        
        # Get weeks with injury data
        injury_weeks = session.query(InjuryReport.week).distinct().all()
        injury_weeks = [w[0] for w in injury_weeks] if injury_weeks else []
        
        session.close()
        
        return {
            'vegas': ', '.join(map(str, sorted(vegas_weeks))) if vegas_weeks else 'None',
            'injury': ', '.join(map(str, sorted(injury_weeks))) if injury_weeks else 'None'
        }
    except Exception as e:
        return {'vegas': 'Error', 'injury': 'Error'}


def show():
    """Main function to render the Narrative Intelligence page."""
    # Apply compact styles
    from src.styles import get_base_styles, get_card_styles
    st.markdown(get_base_styles(), unsafe_allow_html=True)
    st.markdown(get_card_styles(), unsafe_allow_html=True)
    
    # ULTRA-COMPACT Header: Single line
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.5rem 0; margin-bottom: 0.5rem;">
        <div style="display: flex; align-items: baseline; gap: 1rem;">
            <h2 style="margin: 0; font-size: 1.5rem; font-weight: 700; display: inline;">
                📊 <span class="gradient-text">Narrative Intelligence</span>
            </h2>
            <span style="color: #707070; font-size: 0.875rem;">Context for smarter picks</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'vegas_lines_df' not in st.session_state:
        st.session_state.vegas_lines_df = None
    if 'injury_reports_df' not in st.session_state:
        st.session_state.injury_reports_df = None
    if 'last_vegas_update' not in st.session_state:
        st.session_state.last_vegas_update = None
    if 'last_injury_update' not in st.session_state:
        st.session_state.last_injury_update = None
    if 'current_week' not in st.session_state:
        st.session_state.current_week = get_current_nfl_week()
    
    # Auto-load data on first visit (silently)
    if 'narrative_data_auto_loaded' not in st.session_state:
        st.session_state.narrative_data_auto_loaded = False
    
    if not st.session_state.narrative_data_auto_loaded:
        # Try to auto-load cached data silently
        try:
            from src.db_init import initialize_database
            current_week = st.session_state.current_week
            
            # Load from cache silently (won't hit APIs unless cache is missing)
            initialize_database(current_week, use_cache=True, force_refresh=False, verbose=False)
            st.session_state.narrative_data_auto_loaded = True
            
            # Load data into session state
            load_vegas_lines_from_db()
            load_injury_reports_from_db()
        except Exception:
            # Non-critical - just log silently
            pass
    
    # Check database and cache status (silently)
    try:
        from src.db_init import check_data_freshness
        
        data_status = check_data_freshness()
        current_week = st.session_state.current_week
        
        # If no data, show simple "Load Data" button
        if not data_status.get('vegas_lines') or not data_status.get('injury_reports'):
            st.info("💡 **Data not loaded yet** - Click below to load Vegas lines and injury reports")
            
            if st.button("📥 Load Data from APIs", type="primary", use_container_width=True):
                from src.db_init import initialize_database
                if initialize_database(current_week, use_cache=True, force_refresh=False, verbose=True):
                    load_vegas_lines_from_db()
                    load_injury_reports_from_db()
                    st.rerun()
                else:
                    st.error("❌ Failed to load data. Check API keys in settings.")
            
            st.markdown("---")
        else:
            # Data loaded - show optional refresh in collapsed expander
            with st.expander("🔄 Refresh Data (Optional)"):
                st.caption("Fetch latest data from APIs")
                
                if st.button("🌐 Refresh from APIs", use_container_width=True):
                    from src.db_init import initialize_database
                    if initialize_database(current_week, use_cache=False, force_refresh=True, verbose=True):
                        load_vegas_lines_from_db()
                        load_injury_reports_from_db()
                        st.rerun()
                    else:
                        st.error("❌ API fetch failed.")
    except Exception:
        # Silently fail - data will load on button click
        pass
    
    # ULTRA-COMPACT Week selector and status - single row
    col1, col2, col3, col4 = st.columns([0.8, 2, 1.5, 1])
    
    with col1:
        previous_week = st.session_state.current_week
        st.session_state.current_week = st.number_input(
            "Week",
            min_value=1,
            max_value=18,
            value=st.session_state.current_week,
            help="NFL week",
            label_visibility="collapsed"
        )
        if st.session_state.current_week != previous_week:
            load_vegas_lines_from_db()
            load_injury_reports_from_db()
    
    with col2:
        available_weeks = get_available_data_weeks()
        if available_weeks['vegas'] or available_weeks['injury']:
            st.caption(f"📊 Vegas: Wk {available_weeks['vegas']} | Injury: Wk {available_weeks['injury']}")
    
    with col3:
        # Combine success messages inline
        vegas_count = len(st.session_state.vegas_lines_df) if st.session_state.vegas_lines_df is not None else 0
        injury_count = len(st.session_state.injury_reports_df) if st.session_state.injury_reports_df is not None else 0
        if vegas_count > 0 or injury_count > 0:
            st.caption(f"✅ {vegas_count} games | {injury_count} injuries")
    
    with col4:
        if st.button("▶️ Continue", use_container_width=True, type="primary", help="Next: Select Players"):
            st.session_state['page'] = 'player_selection'
            st.rerun()
    
    # Section 1: Vegas Lines & Implied Team Totals
    render_vegas_lines_section()
    
    st.divider()
    
    # Section 2: Injury Reports
    render_injury_reports_section()
    
    # Navigation (compact at bottom)
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    render_navigation()


def render_vegas_lines_section():
    """Render Vegas Lines section with data table and refresh button."""
    st.markdown("### 🎰 Vegas Lines")
    st.caption("Team scoring expectations from betting markets")
    
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        # Check API key
        odds_api_key = os.getenv('ODDS_API_KEY')
        if not odds_api_key:
            st.warning("⚠️ ODDS_API_KEY not found in .env file")
            st.info("💡 Get a free API key at https://the-odds-api.com")
            api_available = False
        else:
            api_available = True
        
        # Refresh button
        refresh_disabled = not api_available or is_rate_limited('vegas')
        
        if st.button(
            "🔄 Update Vegas Lines",
            disabled=refresh_disabled,
            help="Fetch latest odds from The Odds API" if not refresh_disabled else "Rate limited - wait before refreshing"
        ):
            fetch_vegas_lines()
    
    with col2:
        # Load from cache button
        if st.button("💾 Load Cached Data", help="Load Vegas lines from database"):
            load_vegas_lines_from_db()
    
    with col3:
        # Show last update time
        if st.session_state.last_vegas_update:
            time_ago = get_time_ago(st.session_state.last_vegas_update)
            st.caption(f"Last updated: {time_ago}")
        
        # Show rate limit countdown
        if is_rate_limited('vegas'):
            remaining = get_rate_limit_remaining('vegas')
            st.caption(f"⏱️ Refresh available in {remaining}")
    
    # Display data table
    if st.session_state.vegas_lines_df is not None and not st.session_state.vegas_lines_df.empty:
        display_vegas_lines_table(st.session_state.vegas_lines_df)
    else:
        st.info("📭 No Vegas data loaded. Click 'Update Vegas Lines' or 'Load Cached Data'.")


def render_injury_reports_section():
    """Render Injury Reports section with data table and refresh button."""
    st.markdown("### 🏥 Injury Reports")
    st.caption("Player health status and practice participation")
    
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        # Check API key
        msf_api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
        if not msf_api_key:
            st.warning("⚠️ MYSPORTSFEEDS_API_KEY not found in .env file")
            st.info("💡 Get a free API key at https://www.mysportsfeeds.com")
            api_available = False
        else:
            api_available = True
        
        # Refresh button
        refresh_disabled = not api_available or is_rate_limited('injury')
        
        if st.button(
            "🔄 Refresh Injury Reports",
            disabled=refresh_disabled,
            help="Fetch latest injury data" if not refresh_disabled else "Rate limited - wait before refreshing"
        ):
            fetch_injury_reports()
    
    with col2:
        # Load from cache button
        if st.button("💾 Load Cached Injuries", help="Load injury reports from database"):
            load_injury_reports_from_db()
    
    with col3:
        # Show last update time
        if st.session_state.last_injury_update:
            time_ago = get_time_ago(st.session_state.last_injury_update)
            st.caption(f"Last updated: {time_ago}")
        
        # Show rate limit countdown
        if is_rate_limited('injury'):
            remaining = get_rate_limit_remaining('injury')
            st.caption(f"⏱️ Refresh available in {remaining}")
    
    # Display data table
    if st.session_state.injury_reports_df is not None and not st.session_state.injury_reports_df.empty:
        display_injury_reports_table(st.session_state.injury_reports_df)
    else:
        st.info("📭 No injury data loaded. Click 'Refresh Injury Reports' or 'Load Cached Injuries'.")


def render_future_placeholder():
    """Render placeholder for future enhancements."""
    st.header("🔮 Additional Context (Coming Soon)")
    
    st.markdown("""
    **Future enhancements planned for Phase 2D:**
    
    - ⛅ **Weather Data** - Wind, precipitation, temperature impact
    - 📰 **News & Narratives** - Revenge games, homecoming, prime-time exposure
    - 📈 **Pace & Playcalling** - Team tempo and situational tendencies
    - 🎯 **Matchup Analysis** - DVOA rankings and positional advantages
    - 💭 **Sentiment Tracking** - Social media buzz and trending players
    - 🏆 **Milestone Watch** - Players approaching career milestones
    
    *These features will provide even deeper context for pool selection.*
    """)


def render_navigation():
    """Render compact bottom navigation."""
    col1, col2 = st.columns([1, 4])
    
    with col1:
        if st.button("⬅️ Back", use_container_width=True, help="Back to Data Ingestion"):
            st.session_state['page'] = 'data_ingestion'
            st.rerun()


# ===== Data Fetching Functions =====

def fetch_vegas_lines():
    """Fetch Vegas lines from The Odds API."""
    with st.spinner("Fetching Vegas lines from The Odds API..."):
        try:
            odds_api_key = os.getenv('ODDS_API_KEY')
            client = OddsAPIClient(api_key=odds_api_key)
            
            # Fetch odds (Note: Odds API returns all upcoming games)
            games = client.fetch_nfl_odds(use_cache=False)
            
            # Filter games to only show the selected week
            current_week = st.session_state.current_week
            filtered_games = [g for g in games if client._calculate_nfl_week(g['commence_time']) == current_week]
            
            if not filtered_games and games:
                st.warning(f"⚠️ API returned {len(games)} games, but none match Week {current_week}. Showing all games instead.")
                filtered_games = games
            
            if filtered_games:
                # Convert to DataFrame
                df = pd.DataFrame(filtered_games)
                
                # Format for display
                display_df = pd.DataFrame({
                    'Game': df.apply(lambda row: f"{row['away_team']} @ {row['home_team']}", axis=1),
                    'Home Team': df['home_team'],
                    'Away Team': df['away_team'],
                    'Spread': df['spread_home'].apply(lambda x: f"{x:+.1f}" if pd.notna(x) else 'N/A'),
                    'Total': df['total'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else 'N/A'),
                    'Home ITT': df['itt_home'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else 'N/A'),
                    'Away ITT': df['itt_away'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else 'N/A')
                })
                
                st.session_state.vegas_lines_df = display_df
                st.session_state.last_vegas_update = datetime.now()
                set_rate_limit('vegas')
                
                # Clear enriched player data cache so Player Selection will re-enrich with new data
                if 'enriched_player_data' in st.session_state:
                    del st.session_state['enriched_player_data']
                
                st.success(f"✅ Fetched {len(filtered_games)} games for Week {current_week} - Player Selection will reload with new data")
            else:
                st.error("❌ No games found. Check API key or week number.")
            
            client.close()
            
        except Exception as e:
            st.error(f"❌ Error fetching Vegas lines: {str(e)}")


def load_vegas_lines_from_db():
    """Load Vegas lines from database cache."""
    with st.spinner("Loading cached Vegas lines from database..."):
        try:
            session = create_session()
            lines = session.query(VegasLine).filter_by(week=st.session_state.current_week).all()
            
            if lines:
                # Convert to DataFrame
                data = []
                for line in lines:
                    data.append({
                        'Game': f"{line.away_team} @ {line.home_team}",
                        'Home Team': line.home_team,
                        'Away Team': line.away_team,
                        'Spread': f"{line.home_spread:+.1f}" if line.home_spread else 'N/A',
                        'Total': f"{line.total:.1f}" if line.total else 'N/A',
                        'Home ITT': f"{line.home_itt:.1f}" if line.home_itt else 'N/A',
                        'Away ITT': f"{line.away_itt:.1f}" if line.away_itt else 'N/A'
                    })
                
                st.session_state.vegas_lines_df = pd.DataFrame(data)
                
                # Get latest update time
                if lines:
                    st.session_state.last_vegas_update = max(line.fetched_at for line in lines)
                
                st.success(f"✅ Loaded {len(lines)} games from database cache")
            else:
                st.warning(f"⚠️ No cached data found for Week {st.session_state.current_week}")
            
            session.close()
            
        except Exception as e:
            st.error(f"❌ Error loading from database: {str(e)}")


def fetch_injury_reports():
    """Fetch injury reports from MySportsFeeds API and store in database."""
    with st.spinner("Fetching injury reports from MySportsFeeds API..."):
        try:
            msf_api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
            # CRITICAL: Must pass db_path to ensure data is stored correctly
            client = MySportsFeedsClient(api_key=msf_api_key, db_path="dfs_optimizer.db")
            
            # Fetch injuries (stores to database via _store_injuries)
            injuries = client.fetch_injuries(
                season=2025,
                week=st.session_state.current_week,
                use_cache=False  # Force fresh fetch from API
            )
            
            if injuries:
                # Filter out IR players (not relevant for weekly DFS)
                filtered_injuries = [
                    inj for inj in injuries 
                    if inj.get('injury_status', '').upper() not in ['IR', 'INJURED RESERVE']
                ]
                
                # Convert to DataFrame
                df = pd.DataFrame(filtered_injuries)
                
                # Format for display
                display_df = pd.DataFrame({
                    'Player': df['player_name'],
                    'Team': df['team'],
                    'Position': df.get('position', 'N/A'),
                    'Status': df['injury_status'],
                    'Practice': df['practice_status'],
                    'Injury': df['body_part'],  # Match column name with load_from_db
                    'Updated': df['last_update'].apply(lambda x: x.strftime('%m/%d %I:%M %p') if pd.notna(x) else 'N/A')
                })
                
                st.session_state.injury_reports_df = display_df
                
                # Log for transparency
                total_fetched = len(injuries)
                filtered_out = total_fetched - len(filtered_injuries)
                st.session_state.last_injury_update = datetime.now()
                set_rate_limit('injury')
                
                # Clear enriched player data cache so Player Selection will re-enrich with new data
                if 'enriched_player_data' in st.session_state:
                    del st.session_state['enriched_player_data']
                
                # Success message with filtering info
                msg = f"✅ Fetched {len(filtered_injuries)} weekly injury reports"
                if filtered_out > 0:
                    msg += f" ({filtered_out} IR players filtered out)"
                st.success(msg)
                
                # Reload from database to ensure display is in sync
                load_injury_reports_from_db()
            else:
                st.error("❌ No injury data found. Check API key or week number.")
            
            client.close()
            
        except Exception as e:
            st.error(f"❌ Error fetching injury reports: {str(e)}")


def load_injury_reports_from_db():
    """Load injury reports from database cache."""
    with st.spinner("Loading cached injury reports from database..."):
        try:
            session = create_session()
            reports = session.query(InjuryReport).filter_by(week=st.session_state.current_week).all()
            
            if reports:
                # Convert to DataFrame (filter out IR players - not relevant for weekly DFS)
                data = []
                for report in reports:
                    # Skip IR players (Injured Reserve = out for multiple weeks)
                    status_upper = report.injury_status.upper() if report.injury_status else ''
                    if status_upper in ['IR', 'INJURED RESERVE']:
                        continue
                    
                    data.append({
                        'Player': report.player_name,
                        'Team': report.team,
                        'Position': report.position or 'N/A',
                        'Status': report.injury_status,
                        'Practice': report.practice_status,
                        'Injury': report.body_part,  # Renamed from 'Body Part'
                        'Updated': report.updated_at.strftime('%m/%d %I:%M %p') if report.updated_at else 'N/A'
                    })
                
                st.session_state.injury_reports_df = pd.DataFrame(data)
                
                # Get latest update time
                if reports:
                    st.session_state.last_injury_update = max(
                        report.updated_at for report in reports if report.updated_at
                    )
                
                st.success(f"✅ Loaded {len(reports)} injury reports from database cache")
            else:
                st.warning(f"⚠️ No cached injury data found for Week {st.session_state.current_week}")
            
            session.close()
            
        except Exception as e:
            st.error(f"❌ Error loading from database: {str(e)}")


# ===== Display Functions =====

def display_vegas_lines_table(df):
    """Display Vegas lines in a formatted table."""
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Game': st.column_config.TextColumn('Game', width='medium'),
            'Home Team': st.column_config.TextColumn('Home', width='small'),
            'Away Team': st.column_config.TextColumn('Away', width='small'),
            'Spread': st.column_config.TextColumn('Spread', width='small'),
            'Total': st.column_config.TextColumn('Total', width='small'),
            'Home ITT': st.column_config.TextColumn('Home ITT', width='small', help='Implied Team Total'),
            'Away ITT': st.column_config.TextColumn('Away ITT', width='small', help='Implied Team Total')
        }
    )
    
    # Summary stats
    if 'Home ITT' in df.columns and 'Away ITT' in df.columns:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Games Loaded", len(df))
        with col2:
            # Find highest ITT
            all_itts = []
            for val in list(df['Home ITT']) + list(df['Away ITT']):
                if val != 'N/A':
                    all_itts.append(float(val))
            if all_itts:
                st.metric("Highest ITT", f"{max(all_itts):.1f}")
        with col3:
            if all_itts:
                st.metric("Lowest ITT", f"{min(all_itts):.1f}")


def display_injury_reports_table(df):
    """Display injury reports in a formatted table with color coding (IR filtered out)."""
    # Add color coding based on status
    def color_status(val):
        if not val or not isinstance(val, str):
            return ''
        val_upper = val.upper()
        if val_upper == 'QUESTIONABLE' or val_upper == 'Q':
            return 'background-color: #fff3cd'  # Yellow
        elif val_upper == 'DOUBTFUL' or val_upper == 'D':
            return 'background-color: #f8d7da'  # Light red
        elif val_upper in ['OUT', 'O']:
            return 'background-color: #f5c6cb'  # Red
        return ''
    
    styled_df = df.style.applymap(color_status, subset=['Status'])
    
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Player': st.column_config.TextColumn('Player', width='large'),
            'Team': st.column_config.TextColumn('Team', width='small'),
            'Position': st.column_config.TextColumn('Pos', width='small'),
            'Status': st.column_config.TextColumn('Status', width='medium', help='Game status: Questionable, Doubtful, or Out for this week'),
            'Practice': st.column_config.TextColumn('Practice', width='small'),
            'Injury': st.column_config.TextColumn('Injury', width='large'),
            'Updated': st.column_config.TextColumn('Updated', width='medium')
        }
    )
    
    # Summary stats (IR filtered out)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Weekly Injuries", len(df))
    with col2:
        # Match full status names from the API
        q_count = len(df[df['Status'].str.upper() == 'QUESTIONABLE'])
        st.metric("Questionable", q_count)
    with col3:
        d_count = len(df[df['Status'].str.upper() == 'DOUBTFUL'])
        st.metric("Doubtful", d_count)
    with col4:
        # Only Out (IR already filtered)
        o_count = len(df[df['Status'].str.upper().isin(['OUT', 'O'])])
        st.metric("Out", o_count)


# ===== Rate Limiting Functions =====

def is_rate_limited(api_type):
    """Check if API is rate limited."""
    key = f'{api_type}_last_call'
    if key in st.session_state:
        elapsed = datetime.now() - st.session_state[key]
        # Rate limit: 15 minutes between calls
        return elapsed < timedelta(minutes=15)
    return False


def set_rate_limit(api_type):
    """Set rate limit timestamp."""
    key = f'{api_type}_last_call'
    st.session_state[key] = datetime.now()


def get_rate_limit_remaining(api_type):
    """Get remaining time until next API call allowed."""
    key = f'{api_type}_last_call'
    if key in st.session_state:
        elapsed = datetime.now() - st.session_state[key]
        remaining = timedelta(minutes=15) - elapsed
        minutes = int(remaining.total_seconds() / 60)
        seconds = int(remaining.total_seconds() % 60)
        return f"{minutes}m {seconds}s"
    return "0m 0s"


def get_time_ago(timestamp):
    """Get human-readable time ago string."""
    if not timestamp:
        return "Never"
    
    elapsed = datetime.now() - timestamp
    
    if elapsed < timedelta(minutes=1):
        return "Just now"
    elif elapsed < timedelta(hours=1):
        minutes = int(elapsed.total_seconds() / 60)
        return f"{minutes}m ago"
    elif elapsed < timedelta(days=1):
        hours = int(elapsed.total_seconds() / 3600)
        return f"{hours}h ago"
    else:
        days = elapsed.days
        return f"{days}d ago"


if __name__ == "__main__":
    show()

