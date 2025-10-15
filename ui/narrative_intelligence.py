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


def get_main_slate_teams():
    """
    Extract main slate teams from uploaded player data.
    
    Returns:
        Set of team abbreviations that are on the main slate
    """
    try:
        # Get player data from session state
        if 'player_data' not in st.session_state:
            return set()
        
        player_df = st.session_state['player_data']
        if player_df is None or player_df.empty:
            return set()
        
        # Extract unique teams from the player data
        if 'team' in player_df.columns:
            main_slate_teams = set(player_df['team'].dropna().unique())
            return main_slate_teams
        else:
            return set()
            
    except Exception as e:
        return set()


def get_available_data_weeks():
    """
    Check which weeks have cached data available.
    
    Returns:
        Dictionary with 'vegas' and 'injury' keys containing lists of available weeks
    """
    try:
        import os
        from sqlalchemy import func
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
        # Show current analysis week
        current_week = st.session_state.get('current_week', 7)
        st.markdown(f"**Week {current_week}**")
    
    with col2:
        # Show data status
        vegas_count = len(st.session_state.vegas_lines_df) if st.session_state.vegas_lines_df is not None else 0
        injury_count = len(st.session_state.injury_reports_df) if st.session_state.injury_reports_df is not None else 0
        if vegas_count > 0 or injury_count > 0:
            st.caption(f"📊 Data loaded: {vegas_count} games, {injury_count} injuries")
        else:
            st.caption("📊 No data loaded yet")
    
    with col3:
        # Show last update times
        if st.session_state.last_vegas_update or st.session_state.last_injury_update:
            updates = []
            if st.session_state.last_vegas_update:
                vegas_time = get_time_ago(st.session_state.last_vegas_update)
                updates.append(f"Vegas: {vegas_time}")
            if st.session_state.last_injury_update:
                injury_time = get_time_ago(st.session_state.last_injury_update)
                updates.append(f"Injury: {injury_time}")
            st.caption(f"🕒 {' | '.join(updates)}")
    
    with col4:
        if st.button("▶️ Continue", use_container_width=True, type="primary", help="Next: Select Players"):
            # Show loading screen instead of transitioning immediately
            st.session_state['show_loading_screen'] = True
            st.session_state['loading_message'] = "📈 Analyzing historical trends..."
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
    with st.spinner(""):
        try:
            # Debug: Log the week being queried
            query_week = st.session_state.current_week
            
            # Use absolute path to database
            import os
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dfs_optimizer.db")
            
            session = create_session(db_path)
            lines = session.query(VegasLine).filter_by(week=query_week).all()
            
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
            else:
                # Try loading from JSON cache file as fallback
                import json
                cache_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache", f"vegas_lines_week{query_week}.json")
                
                if os.path.exists(cache_file):
                    with open(cache_file, 'r') as f:
                        cache_data = json.load(f)
                    
                    # Convert cache to DataFrame
                    data = []
                    for game in cache_data['data']:
                        data.append({
                            'Game': f"{game['away_team']} @ {game['home_team']}",
                            'Home Team': game['home_team'],
                            'Away Team': game['away_team'],
                            'Spread': f"{game['home_spread']:+.1f}" if game['home_spread'] else 'N/A',
                            'Total': f"{game['total']:.1f}" if game['total'] else 'N/A',
                            'Home ITT': f"{game['home_itt']:.1f}" if game['home_itt'] else 'N/A',
                            'Away ITT': f"{game['away_itt']:.1f}" if game['away_itt'] else 'N/A'
                        })
                    
                    st.session_state.vegas_lines_df = pd.DataFrame(data)
                    st.session_state.last_vegas_update = datetime.fromisoformat(cache_data['cached_at'])
                    pass  # Silently loaded from cache
                else:
                    pass  # No cached data - silently continue
            
            session.close()
            
        except Exception as e:
            st.error(f"❌ Error loading from database: {str(e)}")


def fetch_injury_reports():
    """Fetch injury reports from ESPN API with rich context and affected players."""
    with st.spinner("Fetching injury reports from ESPN API..."):
        try:
            from src.api.espn_api import ESPNAPIClient
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from src.database_models import InjuryReport
            
            # Fetch from ESPN (no key required)
            espn_client = ESPNAPIClient()
            injuries = espn_client.fetch_injuries()
            espn_client.close()
            
            if injuries:
                # Filter out IR players (not relevant for weekly DFS)
                filtered_injuries = [
                    inj for inj in injuries 
                    if inj.get('injury_status', '').upper() not in ['IR', 'INJURED RESERVE']
                ]
                
                # Store directly to database
                engine = create_engine('sqlite:///dfs_optimizer.db')
                Session = sessionmaker(bind=engine)
                session = Session()
                
                try:
                    # Clear existing injuries for this week
                    session.query(InjuryReport).filter_by(
                        week=st.session_state.current_week
                    ).delete()
                    
                    # Store ESPN injuries
                    for injury in filtered_injuries:
                        injury_report = InjuryReport(
                            week=st.session_state.current_week,
                            player_name=injury['player_name'],
                            team=injury['team'],
                            position=injury.get('position', ''),
                            injury_status=injury['injury_status'],
                            practice_status='',  # ESPN doesn't provide this
                            body_part=injury.get('body_part', ''),
                            description=injury.get('long_comment') or injury.get('short_comment', '')
                        )
                        session.add(injury_report)
                    
                    session.commit()
                finally:
                    session.close()
                
                # Store rich ESPN data in session state for display
                st.session_state.espn_injury_data = injuries  # Full ESPN data with context
                
                # Convert to DataFrame for basic display
                df = pd.DataFrame(filtered_injuries)
                
                # Map status to short codes for better readability
                def format_status(status):
                    status_map = {
                        'Questionable': 'Q',
                        'Doubtful': 'D',
                        'Out': 'Out',
                        'IR': 'IR',
                        'Active': 'Q'  # Active typically means game-time decision
                    }
                    return status_map.get(status, status)
                
                # Format for display
                display_df = pd.DataFrame({
                    'Player': df['player_name'],
                    'Team': df['team'],
                    'Pos': df.get('position', 'N/A'),
                    'Status': df['injury_status'].apply(format_status),
                    'Injury': df['body_part'],
                    'Context': df['short_comment'].apply(lambda x: x[:80] + '...' if len(x) > 80 else x),
                    'Affected': df['affected_players'].apply(lambda x: ', '.join(x) if x else '—')
                })
                
                st.session_state.injury_reports_df = display_df
                
                # Log for transparency
                total_fetched = len(injuries)
                filtered_out = total_fetched - len(filtered_injuries)
                affected_count = len([inj for inj in filtered_injuries if inj.get('affected_players')])
                
                st.session_state.last_injury_update = datetime.now()
                set_rate_limit('injury')
                
                # Clear enriched player data cache so Player Selection will re-enrich with new data
                if 'enriched_player_data' in st.session_state:
                    del st.session_state['enriched_player_data']
                
                # Success message with stats
                msg = f"✅ Fetched {len(filtered_injuries)} DFS-relevant injury reports from ESPN"
                if filtered_out > 0:
                    msg += f" ({filtered_out} IR/non-DFS players filtered)"
                st.success(msg)
                
                if affected_count > 0:
                    st.caption(f"👥 {affected_count} injuries have identified affected players (backups, committee changes, etc.)")
                st.caption(f"📊 Filtered to DFS positions only: QB, RB, WR, TE, K, DST")
                
                # Reload from database to ensure display is in sync
                load_injury_reports_from_db()
            else:
                st.error("❌ No injury data found from ESPN")
            
        except Exception as e:
            st.error(f"❌ Error fetching injury reports: {str(e)}")


def load_injury_reports_from_db():
    """Load injury reports from database cache."""
    with st.spinner(""):
        try:
            import os
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dfs_optimizer.db")
            session = create_session(db_path)
            current_week = st.session_state.get('current_week', 7)
            reports = session.query(InjuryReport).filter_by(week=current_week).all()
            
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
            else:
                pass  # No cached data - silently continue
            
            session.close()
            
        except Exception as e:
            st.error(f"❌ Error loading from database: {str(e)}")


# ===== Display Functions =====

def display_vegas_lines_table(df):
    """Display Vegas lines in a formatted table, filtered to main slate teams."""
    # Get main slate teams
    main_slate_teams = get_main_slate_teams()
    
    # Filter to only show games with main slate teams
    if main_slate_teams:
        # Convert Vegas team names to abbreviations for comparison
        # Vegas Lines use full names (e.g., "Kansas City Chiefs") while player data uses abbreviations (e.g., "KC")
        from src.opponent_lookup import TEAM_NAME_TO_ABBR
        
        def convert_to_abbrev(team_name):
            """Convert full team name to abbreviation."""
            return TEAM_NAME_TO_ABBR.get(team_name, team_name)
        
        # Convert Vegas team names to abbreviations
        df['Home Team Abbr'] = df['Home Team'].apply(convert_to_abbrev)
        df['Away Team Abbr'] = df['Away Team'].apply(convert_to_abbrev)
        
        # Filter games where either home or away team is in main slate
        filtered_df = df[
            df['Home Team Abbr'].isin(main_slate_teams) | 
            df['Away Team Abbr'].isin(main_slate_teams)
        ].copy()
        
        # Remove the temporary abbreviation columns
        filtered_df = filtered_df.drop(['Home Team Abbr', 'Away Team Abbr'], axis=1)
        
        # Show filtering info
        original_count = len(df)
        filtered_count = len(filtered_df)
        if original_count > filtered_count:
            st.caption(f"🎯 Filtered to main slate: {original_count} → {filtered_count} games ({len(main_slate_teams)} teams)")
        
        # Use filtered data for display
        display_df = filtered_df
    else:
        # No main slate data available, show all games
        display_df = df
        st.caption("📋 Showing all games (no player data loaded for main slate filtering)")
    
    st.dataframe(
        display_df,
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
    if 'Home ITT' in display_df.columns and 'Away ITT' in display_df.columns:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Games Loaded", len(display_df))
        with col2:
            # Find highest ITT
            all_itts = []
            for val in list(display_df['Home ITT']) + list(display_df['Away ITT']):
                if val != 'N/A':
                    all_itts.append(float(val))
            if all_itts:
                st.metric("Highest ITT", f"{max(all_itts):.1f}")
        with col3:
            if all_itts:
                st.metric("Lowest ITT", f"{min(all_itts):.1f}")


def display_injury_reports_table(df):
    """Display injury reports with ESPN context and affected players (IR filtered out), filtered to main slate teams."""
    # Get main slate teams
    main_slate_teams = get_main_slate_teams()
    
    # Filter to only show injuries from main slate teams
    if main_slate_teams:
        # Filter injuries where team is in main slate
        # Note: Injury reports should already use abbreviations, but let's be safe
        filtered_df = df[df['Team'].isin(main_slate_teams)].copy()
        
        # Show filtering info
        original_count = len(df)
        filtered_count = len(filtered_df)
        if original_count > filtered_count:
            st.caption(f"🎯 Filtered to main slate: {original_count} → {filtered_count} injuries ({len(main_slate_teams)} teams)")
        
        # Use filtered data for display
        display_df = filtered_df
    else:
        # No main slate data available, show all injuries
        display_df = df
        st.caption("📋 Showing all injuries (no player data loaded for main slate filtering)")
    
    # Add color coding based on status (now using short codes: Q, D, Out)
    def color_status(val):
        if not val or not isinstance(val, str):
            return ''
        val_upper = val.upper()
        if val_upper == 'Q':
            return 'background-color: #fff3cd; color: #856404; font-weight: bold'  # Yellow
        elif val_upper == 'D':
            return 'background-color: #f8d7da; color: #721c24; font-weight: bold'  # Light red
        elif val_upper == 'OUT':
            return 'background-color: #f5c6cb; color: #721c24; font-weight: bold'  # Red
        return ''
    
    styled_df = display_df.style.applymap(color_status, subset=['Status'])
    
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Player': st.column_config.TextColumn('Player', width='medium'),
            'Team': st.column_config.TextColumn('Team', width='small'),
            'Pos': st.column_config.TextColumn('Pos', width='small'),
            'Status': st.column_config.TextColumn('Status', width='small', help='Q=Questionable, D=Doubtful, Out=Ruled Out'),
            'Injury': st.column_config.TextColumn('Injury', width='small'),
            'Context': st.column_config.TextColumn('Context', width='large', help='ESPN injury context (click player for full details)'),
            'Affected': st.column_config.TextColumn('Affected Players', width='medium', help='Backups or players impacted by this injury')
        }
    )
    
    # Summary stats (IR filtered out)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("DFS Injuries", len(display_df))
    with col2:
        q_count = len(display_df[display_df['Status'].str.upper() == 'Q'])
        st.metric("Questionable", q_count)
    with col3:
        d_count = len(display_df[display_df['Status'].str.upper() == 'D'])
        st.metric("Doubtful", d_count)
    with col4:
        o_count = len(display_df[display_df['Status'].str.upper() == 'OUT'])
        st.metric("Out", o_count)
    
    # Expandable full context viewer
    if 'espn_injury_data' in st.session_state:
        st.markdown("---")
        st.caption("💬 **Full ESPN Commentary** (select a player to view detailed analysis)")
        
        # Get all ESPN injuries
        espn_data = st.session_state.espn_injury_data
        
        # Filter to active (non-IR) players
        active_espn = [
            inj for inj in espn_data 
            if inj.get('injury_status', '').upper() not in ['IR', 'INJURED RESERVE']
        ]
        
        # Further filter to main slate teams if available
        if main_slate_teams:
            active_espn = [
                inj for inj in active_espn 
                if inj.get('team', '') in main_slate_teams
            ]
        
        # Create player selector
        player_options = [f"{inj['player_name']} ({inj['team']} {inj['position']})" for inj in active_espn]
        
        if player_options:
            selected = st.selectbox(
                "Select player for full context",
                options=['— Select a player —'] + player_options,
                key='injury_detail_selector'
            )
            
            if selected and selected != '— Select a player —':
                # Find the selected player's data
                player_name = selected.split(' (')[0]
                player_data = next((inj for inj in active_espn if inj['player_name'] == player_name), None)
                
                if player_data:
                    # Display full context in an info box
                    with st.expander(f"📰 {player_name} — Full ESPN Analysis", expanded=True):
                        col_a, col_b = st.columns([1, 1])
                        
                        with col_a:
                            st.markdown(f"**Team:** {player_data['team']}")
                            st.markdown(f"**Position:** {player_data['position']}")
                            st.markdown(f"**Status:** {player_data['injury_status']}")
                            st.markdown(f"**Injury:** {player_data.get('body_part', 'N/A')}")
                        
                        with col_b:
                            affected = player_data.get('affected_players', [])
                            if affected:
                                st.markdown(f"**Affected Players:**")
                                for ap in affected:
                                    st.markdown(f"- {ap}")
                            else:
                                st.markdown("**Affected Players:** None identified")
                        
                        # Full long comment
                        long_comment = player_data.get('long_comment', '')
                        if long_comment:
                            st.markdown("---")
                            st.markdown("**📝 Full ESPN Commentary:**")
                            st.markdown(long_comment)
                        else:
                            short_comment = player_data.get('short_comment', '')
                            if short_comment:
                                st.markdown("---")
                                st.markdown("**📝 ESPN Commentary:**")
                                st.markdown(short_comment)


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

