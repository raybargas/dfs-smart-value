"""
Results Display UI Component

This module displays generated lineups with detailed statistics and export options.
"""

import streamlit as st
import pandas as pd
from typing import List
from pathlib import Path
import sys

# Add src directory to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from models import Lineup
import sqlite3
from datetime import datetime
from typing import Dict, Optional


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


def load_historical_player_scores(week: int) -> Optional[Dict[str, float]]:
    """
    Load actual DraftKings fantasy scores for players from a historical week.
    
    Args:
        week: NFL week number to load scores for
        
    Returns:
        Dictionary mapping player names to their actual DraftKings fantasy scores
        Returns None if no historical data available
    """
    try:
        import os
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dfs_optimizer.db")
        
        if not os.path.exists(db_path):
            return None
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Query player game stats for the specified week
        query = """
        SELECT player_name, fantasy_points_draftkings
        FROM player_game_stats pgs
        JOIN game_boxscores gb ON pgs.game_id = gb.game_id
        WHERE gb.week = ? AND pgs.fantasy_points_draftkings IS NOT NULL
        """
        
        cursor.execute(query, (week,))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return None
            
        # Convert to dictionary
        historical_scores = {}
        for player_name, dk_points in rows:
            # Handle potential name variations (case insensitive)
            historical_scores[player_name.lower()] = dk_points
            
        return historical_scores
        
    except Exception as e:
        st.error(f"❌ Error loading historical scores for Week {week}: {str(e)}")
        return None


def calculate_lineup_actual_score(lineup: Lineup, historical_scores: Dict[str, float]) -> Optional[float]:
    """
    Calculate the actual DraftKings score for a lineup using historical data.
    
    Args:
        lineup: Lineup object to score
        historical_scores: Dictionary of player names to actual scores
        
    Returns:
        Total actual score for the lineup, or None if any player missing
    """
    if not historical_scores:
        return None
        
    total_score = 0.0
    missing_players = []
    
    for player in lineup.players:
        # Try exact match first
        if player.name in historical_scores:
            total_score += historical_scores[player.name]
        elif player.name.lower() in historical_scores:
            total_score += historical_scores[player.name.lower()]
        else:
            missing_players.append(player.name)
    
    # Return None if any players are missing from historical data
    if missing_players:
        return None
        
    return round(total_score, 2)


def render_results():
    """
    Results Display Component.
    
    Displays:
    1. Generation summary (count, time, success rate)
    2. Individual lineup cards with detailed stats
    3. Historical scoring (if analyzing past weeks)
    4. Export options (DraftKings CSV format)
    5. Navigation back to modify settings
    """
    
    # Apply compact styles
    from src.styles import get_base_styles, get_card_styles
    st.markdown(get_base_styles(), unsafe_allow_html=True)
    st.markdown(get_card_styles(), unsafe_allow_html=True)
    
    # Validate session state
    if 'lineups' not in st.session_state or 'generation_metadata' not in st.session_state:
        st.error("⚠️ No lineup data found. Please generate lineups first.")
        if st.button("⬅️ Back to Optimization", type="primary"):
            st.session_state['page'] = 'optimization'
            st.rerun()
        return
    
    lineups: List[Lineup] = st.session_state['lineups']
    metadata = st.session_state['generation_metadata']
    
    # Check if this is a historical week analysis
    current_week = st.session_state.get('current_week', None)
    is_historical = current_week is not None and current_week < get_current_nfl_week()
    
    # Load historical scores if analyzing past week
    historical_scores = None
    if is_historical:
        historical_scores = load_historical_player_scores(current_week)
    
    # ULTRA-COMPACT Header: Single line
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.5rem 0; margin-bottom: 0.75rem;">
        <div style="display: flex; align-items: baseline; gap: 1rem;">
            <h2 style="margin: 0; font-size: 1.5rem; font-weight: 700; display: inline;">
                🏆 <span class="gradient-text">Generated Lineups</span>
            </h2>
            <span style="color: #707070; font-size: 0.875rem;">Review & export</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # COMPACT Generation Summary
    st.caption("📊 Generation Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Lineups Generated",
            f"{metadata['lineups_generated']} / {metadata['lineups_requested']}"
        )
    
    with col2:
        st.metric(
            "Generation Time",
            f"{metadata['generation_time_seconds']:.2f}s"
        )
    
    with col3:
        st.metric(
            "Player Pool Size",
            metadata['player_pool_size']
        )
    
    with col4:
        uniqueness_pct = int(metadata['uniqueness_pct'] * 100)
        st.metric(
            "Uniqueness",
            f"{uniqueness_pct}%"
        )
    
    # Show error message if partial generation
    if metadata['error_message']:
        st.warning(f"⚠️ {metadata['error_message']}")
    
    if len(lineups) == 0:
        st.error("❌ No lineups were generated. Please adjust your settings and try again.")
        if st.button("⬅️ Back to Optimization", type="primary"):
            st.session_state['page'] = 'optimization'
            st.rerun()
        return
    
    # Player Exposure Analysis
    st.caption("👥 Player Exposure Analysis")
    
    # Calculate exposure for all players
    player_exposure = {}
    for lineup in lineups:
        for player in lineup.players:
            player_exposure[player.name] = player_exposure.get(player.name, 0) + 1
    
    # Sort by exposure count (descending)
    sorted_exposure = sorted(player_exposure.items(), key=lambda x: x[1], reverse=True)
    
    # Get top 10 most exposed players
    top_exposed = sorted_exposure[:10]
    
    # Display in columns
    if top_exposed:
        exposure_text = " | ".join([f"{name} ({count}/{len(lineups)})" for name, count in top_exposed[:5]])
        st.caption(f"**Top Exposure:** {exposure_text}")
        
        # Show warning for high exposure
        max_exposure = top_exposed[0][1] if top_exposed else 0
        max_exposure_pct = (max_exposure / len(lineups)) * 100 if len(lineups) > 0 else 0
        
        if max_exposure_pct > 70:
            st.warning(f"⚠️ High exposure detected: {top_exposed[0][0]} appears in {max_exposure}/{len(lineups)} lineups ({max_exposure_pct:.0f}%). Consider lowering Max Exposure setting.")
    
    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    
    # COMPACT Optimization Transparency Section
    st.markdown("### 🔍 Optimization Details")
    
    optimization_objective = metadata.get('optimization_objective', 'projection')
    
    if optimization_objective == 'smart_value':
        st.success("""
        **🧠 Smart Value Optimization**
        
        These lineups were built by maximizing your custom **Smart Value Score**, not just raw projections.
        
        **Your Smart Value formula incorporated:**
        """)
        
        # Get weights from session state if available
        custom_weights = st.session_state.get('smart_value_custom_weights', {
            'base': 0.15,
            'opportunity': 0.25,
            'trends': 0.10,
            'risk': 0.05,
            'matchup': 0.25,
            'leverage': 0.20,
            'regression': 0.05
        })
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown(f"""
            **Main Category Weights:**
            - 💰 **Base Value** ({custom_weights.get('base', 0.15)*100:.0f}%): Projection per $1K salary
            - 📊 **Opportunity** ({custom_weights.get('opportunity', 0.25)*100:.0f}%): Snap %, targets, red zone usage
            - 📈 **Trends** ({custom_weights.get('trends', 0.10)*100:.0f}%): Momentum, role expansion, recent production
            - ⚠️ **Risk Adjustment** ({custom_weights.get('risk', 0.05)*100:.0f}%): Variance, consistency
            - 🎯 **Matchup** ({custom_weights.get('matchup', 0.25)*100:.0f}%): Vegas lines, game environment
            - 💎 **Leverage** ({custom_weights.get('leverage', 0.20)*100:.0f}%): Ceiling potential + low ownership
            - ⚠️ **80/20 Regression** ({custom_weights.get('regression', 0.05)*100:.0f}%): Penalty for 20+ point scorers
            """)
        
        with col2:
            st.markdown("""
            **This means the optimizer:**
            ✅ Valued players with strong recent trends  
            ✅ Avoided regression candidates (80/20 rule)  
            ✅ Prioritized high-volume opportunities  
            ✅ Accounted for salary value, not just projections  
            ✅ Used your position-specific customizations  
            ✅ Applied your sub-weight configurations
            ✅ Considered leverage and ownership factors
            """)
        
        # Show position-specific overrides if any
        position_weights = st.session_state.get('position_specific_weights', {})
        if any(position_weights.values()):
            st.info(f"""
            **🎯 Position-Specific Overrides Applied:** {', '.join([pos for pos, weights in position_weights.items() if weights])}
            """)
    else:
        st.info("""
        **📊 Projection-Based Optimization**
        
        Lineups maximize **total projected fantasy points** while respecting:
        - 💰 **Salary Cap**: $48K-$50K (96-100% usage required)
        - 👥 **Position Requirements**: 1 QB, 2+ RB, 3+ WR, 1+ TE, 1 DST, 1 FLEX (max 2 TEs)
        - 🔄 **Uniqueness**: {int(metadata['uniqueness_pct']*100)}% lineup diversity
        """)
        
        # Show Smart Value filter if applied
        filter_strategy = metadata.get('filter_strategy', 'simple')
        min_sv = metadata.get('min_smart_value', 0)
        pos_floors = metadata.get('positional_floors', None)
        portfolio_avg = metadata.get('portfolio_avg_smart_value', None)
        hard_floor = metadata.get('hard_floor', 0)
        
        # PHASE 4: Show hard floor defense if applied
        if hard_floor > 0:
            st.info(f"""
            🛡️ **Hard Floor Defense: {hard_floor}**
            
            All players below Smart Value **{hard_floor}** were blocked before applying your filter strategy.
            
            **Trap chalk protection**: Prevents extreme low-value chalk (e.g., Puka Nacua Week 6) from entering lineups.
            """)
        
        if filter_strategy == 'simple' and min_sv > 0:
            st.success(f"""
            **🧠 Smart Value Filter Applied (Simple)**
            
            Only players with Smart Value ≥ **{min_sv}** were considered.
            
            This ensures lineups are built from high-quality plays with:
            ✅ Strong opportunity metrics (volume, usage)  
            ✅ Favorable matchups and game environments  
            ✅ Positive momentum and trends  
            ✅ Ownership leverage for tournaments
            """)
        elif filter_strategy == 'positional' and pos_floors:
            floors_text = ", ".join([f"{pos}: {val}" for pos, val in pos_floors.items()])
            st.success(f"""
            **🧠 Smart Value Filter Applied (Positional)**
            
            Position-specific thresholds: **{floors_text}**
            
            This ensures each position meets custom quality standards:
            ✅ Flexible thresholds per position  
            ✅ Higher standards for key positions  
            ✅ More options for value positions
            """)
        elif filter_strategy == 'portfolio' and portfolio_avg:
            # Calculate actual average for first lineup
            actual_avg = None
            if len(lineups) > 0:
                lineup_smart_values = [
                    getattr(p, 'smart_value', 0) 
                    for p in lineups[0].players 
                    if hasattr(p, 'smart_value')
                ]
                if lineup_smart_values:
                    actual_avg = sum(lineup_smart_values) / len(lineup_smart_values)
            
            avg_text = f"Required: **{portfolio_avg:.0f}** | Actual: **{actual_avg:.1f}**" if actual_avg else f"Required: **{portfolio_avg:.0f}**"
            
            st.success(f"""
            **💼 Smart Value Portfolio Constraint Applied**
            
            Lineup average Smart Value: {avg_text}
            
            This allows maximum flexibility:
            ✅ Can include "chalk" studs (low SV) if balanced  
            ✅ Prioritizes overall lineup quality  
            ✅ Prevents all-contrarian or all-chalk lineups  
            ✅ Optimal for blending projections + strategy
            """)
        
        if metadata.get('max_ownership_enabled'):
            st.info(f"✅ **Ownership Filter**: Limited to players ≤ {int(metadata.get('max_ownership_pct', 0)*100)}% projected ownership")
    
    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    
    # COMPACT lineup section
    st.markdown("### 🏈 Your Lineups")
    
    # Show historical scoring info if available
    if is_historical and historical_scores:
        st.info(f"📊 **Historical Analysis Mode** - Showing actual Week {current_week} scores alongside projections")
    elif is_historical and not historical_scores:
        st.warning(f"⚠️ **Historical Analysis Mode** - No actual scores available for Week {current_week}")
    
    for lineup in lineups:
        # Calculate actual score if historical data available
        actual_score = None
        if historical_scores:
            actual_score = calculate_lineup_actual_score(lineup, historical_scores)
        
        # Build expander title
        if actual_score is not None:
            title = f"**Lineup #{lineup.lineup_id}** - ${lineup.total_salary:,} | " \
                   f"Proj: {lineup.total_projection:.1f} pts | " \
                   f"**Actual: {actual_score:.1f} pts** | " \
                   f"${lineup.salary_remaining:,} remaining"
        else:
            title = f"**Lineup #{lineup.lineup_id}** - ${lineup.total_salary:,} | " \
                   f"{lineup.total_projection:.1f} pts | " \
                   f"${lineup.salary_remaining:,} remaining"
        
        with st.expander(
            title,
            expanded=(lineup.lineup_id == 1)  # Expand first lineup by default
        ):
            # Create lineup table
            lineup_data = []
            
            positions = [
                ("QB", lineup.qb),
                ("RB", lineup.rb1),
                ("RB", lineup.rb2),
                ("WR", lineup.wr1),
                ("WR", lineup.wr2),
                ("WR", lineup.wr3),
                ("TE", lineup.te),
                ("FLEX", lineup.flex),
                ("DST", lineup.dst)
            ]
            
            for pos_label, player in positions:
                row = {
                    "Position": pos_label,
                    "Player": player.name,
                    "Team": player.team,
                    "Opponent": player.opponent,
                    "Salary": f"${player.salary:,}",
                    "Projection": f"{player.projection:.1f}",
                    "Own%": f"{player.ownership:.1f}%" if player.ownership else "N/A"
                }
                
                # Add actual score if historical data available
                if historical_scores:
                    player_actual = None
                    if player.name in historical_scores:
                        player_actual = historical_scores[player.name]
                    elif player.name.lower() in historical_scores:
                        player_actual = historical_scores[player.name.lower()]
                    
                    if player_actual is not None:
                        row["Actual"] = f"{player_actual:.1f}"
                        # Add performance indicator
                        diff = player_actual - player.projection
                        if diff >= 5:
                            row["Performance"] = "🔥"
                        elif diff >= 2:
                            row["Performance"] = "✅"
                        elif diff >= -2:
                            row["Performance"] = "➖"
                        elif diff >= -5:
                            row["Performance"] = "⚠️"
                        else:
                            row["Performance"] = "❌"
                    else:
                        row["Actual"] = "N/A"
                        row["Performance"] = "?"
                
                # Show Smart Value if using Smart Value optimization, otherwise show traditional Value
                if metadata.get('optimization_objective') == 'smart_value':
                    smart_val = getattr(player, 'smart_value', None)
                    row["Smart Value"] = f"{smart_val:.0f}" if smart_val is not None else "N/A"  # 0-100 scale
                else:
                    row["Value"] = f"{player.value:.2f}"
                
                lineup_data.append(row)
            
            df = pd.DataFrame(lineup_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Lineup stats
            if actual_score is not None:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Projected Score", f"{lineup.total_projection:.1f}")
                
                with col2:
                    st.metric("Actual Score", f"{actual_score:.1f}")
                
                with col3:
                    diff = actual_score - lineup.total_projection
                    st.metric("Difference", f"{diff:+.1f}", delta=f"{diff:+.1f}")
                
                with col4:
                    performance_pct = (actual_score / lineup.total_projection * 100) if lineup.total_projection > 0 else 0
                    st.metric("Performance", f"{performance_pct:.1f}%")
            else:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown(f"**Total Salary:** ${lineup.total_salary:,} / $50,000")
                
                with col2:
                    st.markdown(f"**Total Projection:** {lineup.total_projection:.1f} pts")
                
                with col3:
                    st.markdown(f"**Salary Remaining:** ${lineup.salary_remaining:,}")
                # Show Smart Value average if using Smart Value optimization
                if metadata.get('optimization_objective') == 'smart_value':
                    smart_values = [getattr(p, 'smart_value', 0) for p in lineup.players]
                    avg_smart = sum(smart_values) / 9 if smart_values else 0
                    st.markdown(f"**Avg Smart Value:** {avg_smart:.0f}/100")  # Show as whole number out of 100
                else:
                    avg_value = sum(p.value for p in lineup.players) / 9
                    st.markdown(f"**Avg Value:** {avg_value:.2f} pts/$1K")
    
    # Historical Analysis Summary
    if is_historical and historical_scores:
        st.markdown("---")
        st.markdown("### 📊 Historical Analysis Summary")
        
        # Calculate summary statistics
        actual_scores = []
        projected_scores = []
        
        for lineup in lineups:
            actual_score = calculate_lineup_actual_score(lineup, historical_scores)
            if actual_score is not None:
                actual_scores.append(actual_score)
                projected_scores.append(lineup.total_projection)
        
        if actual_scores:
            avg_projected = sum(projected_scores) / len(projected_scores)
            avg_actual = sum(actual_scores) / len(actual_scores)
            best_actual = max(actual_scores)
            worst_actual = min(actual_scores)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Avg Projected", f"{avg_projected:.1f}")
            
            with col2:
                st.metric("Avg Actual", f"{avg_actual:.1f}")
            
            with col3:
                st.metric("Best Lineup", f"{best_actual:.1f}")
            
            with col4:
                st.metric("Worst Lineup", f"{worst_actual:.1f}")
            
            # Performance analysis
            st.markdown("**Performance Analysis:**")
            over_performed = sum(1 for i, proj in enumerate(projected_scores) if actual_scores[i] > proj)
            under_performed = len(actual_scores) - over_performed
            
            st.markdown(f"- **Over-performed:** {over_performed}/{len(actual_scores)} lineups ({over_performed/len(actual_scores)*100:.1f}%)")
            st.markdown(f"- **Under-performed:** {under_performed}/{len(actual_scores)} lineups ({under_performed/len(actual_scores)*100:.1f}%)")
            
            # Contest context
            st.markdown("**Contest Context (Week 6 DraftKings):**")
            st.markdown("- **Winning Score:** ~229 pts")
            st.markdown("- **Top 10 Cutoff:** ~213 pts") 
            st.markdown("- **Min Cash:** ~140-145 pts")
            
            cash_count = sum(1 for score in actual_scores if score >= 145)
            st.markdown(f"- **Your Cash Rate:** {cash_count}/{len(actual_scores)} lineups ({cash_count/len(actual_scores)*100:.1f}%)")
    
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    
    # COMPACT Export section
    st.markdown("### 💾 Export")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### 📥 DraftKings Upload")
        st.caption("CSV formatted for DraftKings import")
        csv_data = _generate_draftkings_csv(lineups)
        st.download_button(
            label="⬇️ DraftKings CSV",
            data=csv_data,
            file_name=f"draftkings_lineups_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
            type="primary"
        )
    
    with col2:
        st.markdown("#### 📊 Detailed Export")
        st.caption("Full lineup data with all metrics")
        detailed_csv = _generate_detailed_export(lineups, metadata)
        st.download_button(
            label="⬇️ Detailed CSV",
            data=detailed_csv,
            file_name=f"lineups_detailed_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col3:
        st.markdown("#### ⚙️ Configuration")
        st.caption("Save your Smart Value weights")
        
        if metadata.get('optimization_objective') == 'smart_value':
            config_json = _generate_configuration_export()
            st.download_button(
                label="⬇️ Smart Value Config",
                data=config_json,
                file_name=f"smart_value_config_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
        else:
            st.info("N/A for projection mode")
    
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    
    # ULTRA-COMPACT Navigation
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("⬅️ Back", use_container_width=True, help="Back to Optimization"):
            st.session_state['page'] = 'optimization'
            st.rerun()
    
    with col2:
        if st.button("🔄 Regenerate", use_container_width=True, help="Generate new lineups"):
            st.session_state['page'] = 'lineup_generation'
            st.rerun()
    
    with col3:
        if st.button("🏠 Start Over", use_container_width=True, help="Back to data upload"):
            # Clear session state
            st.session_state['page'] = 'data_ingestion'
            st.session_state['player_data'] = None
            st.session_state['selections'] = {}
            if 'player_pool' in st.session_state:
                del st.session_state['player_pool']
            if 'optimization_config' in st.session_state:
                del st.session_state['optimization_config']
            if 'lineups' in st.session_state:
                del st.session_state['lineups']
            if 'generation_metadata' in st.session_state:
                del st.session_state['generation_metadata']
            st.rerun()


def _generate_draftkings_csv(lineups: List[Lineup]) -> str:
    """
    Generate DraftKings-compatible CSV export.
    
    Args:
        lineups: List of Lineup objects to export
    
    Returns:
        CSV string formatted for DraftKings upload
    """
    rows = []
    
    # Header row
    headers = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
    rows.append(",".join(headers))
    
    # Data rows - one per lineup
    for lineup in lineups:
        players = [
            lineup.qb.name,
            lineup.rb1.name,
            lineup.rb2.name,
            lineup.wr1.name,
            lineup.wr2.name,
            lineup.wr3.name,
            lineup.te.name,
            lineup.flex.name,
            lineup.dst.name
        ]
        rows.append(",".join(f'"{p}"' for p in players))
    
    return "\n".join(rows)


def _generate_detailed_export(lineups: List[Lineup], metadata: dict) -> str:
    """
    Generate detailed CSV export with all lineup metrics.
    
    Includes: lineup ID, position, player, team, opponent, salary, projection,
    value, ownership, Smart Value (if used), and lineup totals.
    
    Args:
        lineups: List of Lineup objects to export
        metadata: Generation metadata with optimization settings
    
    Returns:
        Detailed CSV string with all metrics
    """
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    headers = [
        "Lineup_ID", "Position", "Player", "Team", "Opponent", 
        "Salary", "Projection", "Value", "Ownership"
    ]
    
    # Add Smart Value column if used
    if metadata.get('optimization_objective') == 'smart_value':
        headers.append("Smart_Value")
    
    writer.writerow(headers)
    
    # Data rows
    for lineup in lineups:
        positions = [
            ("QB", lineup.qb),
            ("RB1", lineup.rb1),
            ("RB2", lineup.rb2),
            ("WR1", lineup.wr1),
            ("WR2", lineup.wr2),
            ("WR3", lineup.wr3),
            ("TE", lineup.te),
            ("FLEX", lineup.flex),
            ("DST", lineup.dst)
        ]
        
        for pos_label, player in positions:
            row = [
                lineup.lineup_id,
                pos_label,
                player.name,
                player.team,
                player.opponent,
                player.salary,
                f"{player.projection:.2f}",
                f"{player.value:.2f}",
                f"{player.ownership:.1f}" if player.ownership else "N/A"
            ]
            
            # Add Smart Value if available
            if metadata.get('optimization_objective') == 'smart_value':
                smart_val = getattr(player, 'smart_value', 'N/A')
                row.append(f"{smart_val:.0f}" if isinstance(smart_val, (int, float)) else "N/A")  # 0-100 scale
            
            writer.writerow(row)
        
        # Add summary row for this lineup
        summary_row = [
            lineup.lineup_id,
            "TOTAL",
            "-",
            "-",
            "-",
            lineup.total_salary,
            f"{lineup.total_projection:.2f}",
            f"{sum(p.value for p in lineup.players) / 9:.2f}",
            "-"
        ]
        
        if metadata.get('optimization_objective') == 'smart_value':
            # Add average Smart Value if available
            smart_values = [getattr(p, 'smart_value', None) for p in lineup.players]
            smart_values = [v for v in smart_values if v is not None]
            avg_smart = sum(smart_values) / len(smart_values) if smart_values else 0
            summary_row.append(f"{avg_smart:.0f}")  # 0-100 scale
        
        writer.writerow(summary_row)
        writer.writerow([])  # Blank row between lineups
    
    return output.getvalue()


def _generate_configuration_export() -> str:
    """
    Generate JSON export of Smart Value configuration.
    
    Exports main weights, sub-weights, and position-specific overrides
    so users can save and reload their custom optimization settings.
    
    Returns:
        JSON string with configuration
    """
    import json
    
    config = {
        "configuration_type": "Smart Value DFS Optimizer",
        "version": "1.0",
        "timestamp": pd.Timestamp.now().isoformat(),
        "main_weights": st.session_state.get('smart_value_custom_weights', {
            'base': 0.40,
            'opportunity': 0.30,
            'trends': 0.15,
            'risk': 0.10,
            'matchup': 0.05
        }),
        "sub_weights": st.session_state.get('smart_value_sub_weights', {
            'opp_target_share': 0.60,
            'opp_snap_pct': 0.30,
            'opp_rz_targets': 0.10,
            'trends_momentum': 0.50,
            'trends_trend': 0.30,
            'trends_fpg': 0.20,
            'risk_regression': 0.50,
            'risk_variance': 0.30,
            'risk_consistency': 0.20
        }),
        "position_specific_weights": st.session_state.get('position_specific_weights', {})
    }
    
    # Add descriptions for readability
    config["description"] = {
        "main_weights": "Main category weights that sum to 100%",
        "sub_weights": "Sub-factor weights within each category",
        "position_specific_weights": "Position-specific overrides (QB, RB, WR, TE, DST)"
    }
    
    return json.dumps(config, indent=2)

