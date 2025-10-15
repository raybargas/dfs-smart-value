"""
Lineup Optimization Module

This module implements PuLP-based linear programming optimization to generate
DraftKings-valid NFL lineups that maximize projected points while respecting
salary cap, position requirements, uniqueness, and ownership constraints.
"""

import pulp
import pandas as pd
import math
from typing import List, Tuple, Optional

from models import Player, Lineup, PlayerSelection


def generate_lineups(
    player_pool_df: pd.DataFrame,
    lineup_count: int,
    uniqueness_pct: float,
    max_ownership_enabled: bool = False,
    max_ownership_pct: float = None,
    stacking_enabled: bool = True,
    portfolio_avg_smart_value: float = None,
    stacking_penalty_weight: float = 1.0,
    max_exposure_pct: float = 1.0
) -> Tuple[List[Lineup], Optional[str]]:
    """
    Generate N unique DraftKings-valid lineups using linear programming.
    
    This function generates lineups sequentially, adding uniqueness constraints
    after each successful lineup to ensure diversity. The optimization uses
    PuLP with CBC solver to maximize projected fantasy points while respecting
    all DraftKings contest rules.
    
    Note: Smart Value should be used to filter the player pool BEFORE calling this
    function, not as an optimization objective (position-specific scaling makes it
    incompatible with cross-position LP optimization).
    
    Args:
        player_pool_df: DataFrame with player data (filtered pool from Component 2)
            Required columns: name, position, salary, projection, team, opponent
            Optional columns: ownership, player_id, smart_value
        lineup_count: Number of lineups to generate (1-20)
        uniqueness_pct: Minimum uniqueness between lineups (0.40-0.70)
            Example: 0.55 means any two lineups share at most 4 players
        max_ownership_enabled: Whether to apply ownership constraint
        max_ownership_pct: Maximum ownership percentage (0-1.0) if enabled
            Example: 0.30 means no player can exceed 30% projected ownership
        stacking_enabled: Whether to enforce QB + WR/TE same team constraint (default True)
            True: Force QB + at least 1 WR/TE from same team (GPP strategy)
            False: Pure optimization without team correlation requirements
        stacking_penalty_weight: Weight for stacking penalty (0.0 = no penalty, 1.0 = full penalty)
            Applied post-generation to adjust Smart Value scores for unrealistic stacking
        max_exposure_pct: Maximum exposure percentage for any single player (0.20-1.0)
            Example: 0.40 means no player can appear in more than 40% of lineups
            Default: 1.0 (no exposure limit)
    
    Returns:
        Tuple of (List of Lineup objects, Error message or None)
        - On full success: (all lineups, None)
        - On partial success: (N-1 lineups, error message explaining why Nth failed)
        - On immediate failure: ([], error message)
    
    Raises:
        ValueError: If player_pool_df is empty or missing required columns
    """
    # Validate input DataFrame
    required_columns = ['name', 'position', 'salary', 'projection', 'team', 'opponent']
    missing_columns = [col for col in required_columns if col not in player_pool_df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
    
    if len(player_pool_df) == 0:
        raise ValueError("Player pool DataFrame is empty")
    
    # Calculate max shared players from uniqueness percentage
    # Example: 55% uniqueness → must differ by 5 → can share max 4
    max_shared = int(9 * (1 - uniqueness_pct))
    
    # Calculate max lineups per player from exposure percentage
    max_lineups_per_player = int(lineup_count * max_exposure_pct)
    
    # Track player exposure across all lineups
    player_exposure_count = {}
    
    lineups = []
    
    for i in range(lineup_count):
        lineup, error = _generate_single_lineup(
            player_pool_df=player_pool_df,
            previous_lineups=lineups,
            max_shared=max_shared,
            max_ownership_enabled=max_ownership_enabled,
            max_ownership_pct=max_ownership_pct,
            lineup_number=i + 1,
            stacking_enabled=stacking_enabled,
            portfolio_avg_smart_value=portfolio_avg_smart_value,
            player_exposure_count=player_exposure_count,
            max_lineups_per_player=max_lineups_per_player
        )
        
        if error:
            # Return partial results with error message
            return lineups, f"Could not generate lineup {i+1}: {error}"
        
        lineups.append(lineup)
        
        # Update player exposure counts
        for player in lineup.players:
            player_exposure_count[player.name] = player_exposure_count.get(player.name, 0) + 1
    
    # Apply stacking penalty to all generated lineups
    if stacking_penalty_weight > 0:
        try:
            from stacking_analyzer import apply_stacking_penalty_to_lineups
            lineups = apply_stacking_penalty_to_lineups(lineups, stacking_penalty_weight)
        except ImportError:
            # Stacking analyzer not available - skip penalty
            pass
    
    return lineups, None  # Full success


def _generate_single_lineup(
    player_pool_df: pd.DataFrame,
    previous_lineups: List[Lineup],
    max_shared: int,
    max_ownership_enabled: bool,
    max_ownership_pct: float,
    lineup_number: int,
    stacking_enabled: bool = True,
    portfolio_avg_smart_value: float = None,
    player_exposure_count: dict = None,
    max_lineups_per_player: int = None
) -> Tuple[Optional[Lineup], Optional[str]]:
    """
    Generate a single lineup using PuLP linear programming.
    
    This function formulates and solves a linear programming problem to maximize
    projected fantasy points subject to salary cap, position requirements, 
    ownership (if enabled), and uniqueness constraints.
    
    Args:
        player_pool_df: DataFrame with all available players
        previous_lineups: List of already-generated lineups (for uniqueness)
        max_shared: Maximum number of players that can be shared with any previous lineup
        max_ownership_enabled: Whether to apply ownership constraint
        max_ownership_pct: Maximum ownership (0-1.0) if enabled
        lineup_number: Lineup ID for this lineup
        stacking_enabled: Whether to enforce QB + WR/TE same team constraint
    
    Returns:
        Tuple of (Lineup object or None, Error message or None)
        - On success: (Lineup, None)
        - On failure: (None, error message explaining infeasibility)
    """
    # Convert DataFrame to Player objects
    players = _dataframe_to_players(player_pool_df)
    
    # Create LP problem: maximize projected points
    prob = pulp.LpProblem(f"DFS_Lineup_{lineup_number}", pulp.LpMaximize)
    
    # Decision variables: Binary (0 or 1) for each player
    # Use player names as keys (must be unique in pool)
    player_vars = {
        player.name: pulp.LpVariable(
            f"player_{player.name.replace(' ', '_')}_{lineup_number}", 
            cat='Binary'
        )
        for player in players
    }
    
    # Objective function: Maximize projected fantasy points
    # Note: Smart Value should be used to FILTER the player pool before calling this function,
    # not as an optimization objective (position-specific scaling makes it incompatible 
    # with cross-position LP optimization)
    prob += pulp.lpSum([
        player_vars[p.name] * p.projection for p in players
    ]), "Total_Projection"
    
    # Constraint 1: Salary cap ($50,000)
    prob += pulp.lpSum([
        player_vars[p.name] * p.salary for p in players
    ]) <= 50000, "Salary_Cap"
    
    # Constraint 1b: Minimum salary usage (must use at least 96% of cap = $48,000)
    # This prevents leaving money on the table and forces optimizer to find better players
    prob += pulp.lpSum([
        player_vars[p.name] * p.salary for p in players
    ]) >= 48000, "Minimum_Salary_Usage"
    
    # Separate players by position for position constraints
    qbs = [p for p in players if p.position == 'QB']
    rbs = [p for p in players if p.position == 'RB']
    wrs = [p for p in players if p.position == 'WR']
    tes = [p for p in players if p.position == 'TE']
    dsts = [p for p in players if p.position in ['DST', 'D/ST', 'DEF']]
    flex_eligible = rbs + wrs + tes
    
    # Constraint 2: Position requirements (DraftKings NFL standard)
    prob += pulp.lpSum([player_vars[p.name] for p in qbs]) == 1, "Exactly_1_QB"
    prob += pulp.lpSum([player_vars[p.name] for p in rbs]) >= 2, "At_Least_2_RB"
    prob += pulp.lpSum([player_vars[p.name] for p in wrs]) >= 3, "At_Least_3_WR"
    prob += pulp.lpSum([player_vars[p.name] for p in tes]) >= 1, "At_Least_1_TE"
    prob += pulp.lpSum([player_vars[p.name] for p in dsts]) == 1, "Exactly_1_DST"
    
    # FLEX constraint: Total RB+WR+TE must equal 7 (2 RB + 3 WR + 1 TE + 1 FLEX)
    prob += pulp.lpSum([player_vars[p.name] for p in flex_eligible]) == 7, "RB_WR_TE_Total_7"
    
    # Total players must be exactly 9
    prob += pulp.lpSum([player_vars[p.name] for p in players]) == 9, "Total_9_Players"
    
    # Constraint 2b: Limit TEs to maximum 2 (prevents TE overload)
    # This ensures FLEX slot prioritizes RB/WR unless TE has exceptional value
    prob += pulp.lpSum([player_vars[p.name] for p in tes]) <= 2, "Max_2_TE"
    
    # Constraint 2c: Portfolio Average Smart Value (if enabled)
    # This allows individual players below threshold if lineup average is acceptable
    # Example: Can include a chalky stud with SV=30 if balanced by SV=80+ players
    if portfolio_avg_smart_value is not None:
        # Check if all players have smart_value attribute
        players_with_sv = [p for p in players if hasattr(p, 'smart_value') and p.smart_value is not None]
        
        if len(players_with_sv) == len(players):
            # All players have Smart Value - can apply constraint
            prob += pulp.lpSum([
                player_vars[p.name] * p.smart_value for p in players
            ]) >= portfolio_avg_smart_value * 9, "Portfolio_Average_Smart_Value"
        # If some players missing Smart Value, skip constraint (already filtered in UI)
    
    # Constraint 3: Locked players (MUST be in every lineup)
    locked_players = [p for p in players if p.selection == PlayerSelection.LOCKED]
    for locked_player in locked_players:
        prob += player_vars[locked_player.name] == 1, f"Lock_{locked_player.name.replace(' ', '_')}"
    
    # Constraint 4: Ownership (if enabled)
    if max_ownership_enabled and max_ownership_pct is not None:
        for player in players:
            if player.ownership is not None:
                # Binary constraint: if selected, ownership must be <= max
                # This is simplified: player_vars[player.name] * (ownership / 100) <= max_ownership_pct
                # Since player_vars is binary (0 or 1):
                # - If player_vars = 0: constraint is 0 <= max (always true)
                # - If player_vars = 1: constraint is (ownership/100) <= max
                prob += player_vars[player.name] * (player.ownership / 100) <= max_ownership_pct, \
                       f"Ownership_{player.name.replace(' ', '_')}"
    
    # Constraint 5: Uniqueness (relative to all previous lineups)
    for prev_idx, prev_lineup in enumerate(previous_lineups):
        # Get names of players in previous lineup
        prev_player_names = set(p.name for p in prev_lineup.players)
        
        # Sum of shared players must be <= max_shared
        prob += pulp.lpSum([
            player_vars[p.name] for p in players if p.name in prev_player_names
        ]) <= max_shared, f"Uniqueness_vs_Lineup_{prev_idx + 1}"
    
    # Constraint 5b: Max Exposure (limit how many lineups a player can appear in)
    if player_exposure_count is not None and max_lineups_per_player is not None:
        for player in players:
            current_exposure = player_exposure_count.get(player.name, 0)
            # If player has reached max exposure, exclude them from this lineup
            if current_exposure >= max_lineups_per_player:
                prob += player_vars[player.name] == 0, f"MaxExposure_{player.name.replace(' ', '_')}"
    
    # Constraint 6: Stacking (if enabled)
    if stacking_enabled:
        # Forward constraint: For each QB, ensure at least 1 WR/TE from same team is selected
        for qb in qbs:
            qb_team = qb.team
            
            # Find all WRs and TEs from same team as this QB
            same_team_pass_catchers = [
                p for p in (wrs + tes) if p.team == qb_team
            ]
            
            if same_team_pass_catchers:
                # If this QB is selected (player_vars[qb.name] == 1), 
                # then at least 1 pass catcher from same team must also be selected
                # Constraint: sum(same_team_pass_catchers) >= player_vars[qb.name]
                prob += pulp.lpSum([
                    player_vars[p.name] for p in same_team_pass_catchers
                ]) >= player_vars[qb.name], f"Stack_QB_{qb.name.replace(' ', '_')}"
        
        # Reverse constraint: If 2+ pass catchers from same team, QB must be included
        # Group pass catchers by team
        team_pass_catchers = {}
        for player in wrs + tes:
            if player.team not in team_pass_catchers:
                team_pass_catchers[player.team] = []
            team_pass_catchers[player.team].append(player)
        
        for team, pass_catchers in team_pass_catchers.items():
            if len(pass_catchers) >= 2:  # Only apply if team has 2+ pass catchers
                # Find QB from same team
                team_qb = next((qb for qb in qbs if qb.team == team), None)
                
                if team_qb:
                    # If 2+ pass catchers from this team are selected, QB must be selected
                    # Create constraint: sum(pass_catchers) >= 2 * player_vars[team_qb.name]
                    # This means: if 2+ pass catchers selected, QB must be selected (1)
                    # If 0-1 pass catchers selected, QB can be 0 or 1
                    prob += pulp.lpSum([player_vars[p.name] for p in pass_catchers]) >= 2 * player_vars[team_qb.name], f"Stack_Reverse_{team}"
    
    # Constraint 7: GAME STACK (NEW from Week 6 analysis)
    # Force 2-3 players from at least one high-scoring game (50+ total)
    # This mimics the winning pattern: Josh Jacobs + Jaxon Smith-Njigba (64% of top 100)
    if stacking_enabled and 'opponent' in player_pool_df.columns:
        # Identify games and their totals
        game_totals = {}
        for p in players:
            if hasattr(p, 'opponent') and p.opponent and hasattr(p, 'game_total'):
                # Create game key (sorted team pair to avoid duplicates)
                game_key = tuple(sorted([p.team, p.opponent]))
                if game_key not in game_totals:
                    game_totals[game_key] = p.game_total if hasattr(p, 'game_total') else 0
        
        # Identify high-scoring games (50+ total = ceiling environment)
        high_total_games = {k: v for k, v in game_totals.items() if v >= 48}
        
        if high_total_games:
            # For at least ONE high-total game, we must have 2-3 players
            # Create binary indicator for each game
            game_indicators = {}
            for game_key in high_total_games:
                game_indicators[game_key] = pulp.LpVariable(
                    f"game_stack_{game_key[0]}_{game_key[1]}", 
                    cat='Binary'
                )
                
                # Get all players from this game
                game_players = [
                    p for p in players 
                    if p.team in game_key and hasattr(p, 'opponent') and p.opponent in game_key
                ]
                
                # If indicator = 1, then we must select 3+ players from this game (STRENGTHENED)
                # Was 2+, now 3+ for tighter correlation (addresses Sam Darnold lineup issue)
                prob += pulp.lpSum([player_vars[p.name] for p in game_players]) >= 3 * game_indicators[game_key], \
                       f"GameStack_Min_{game_key[0]}_{game_key[1]}"
                
                # Soft max (encourage 3-4, but allow more if optimal)
                # No hard max constraint - let optimizer decide
            
            # Force at least ONE high-total game to be stacked
            prob += pulp.lpSum([game_indicators[game_key] for game_key in high_total_games]) >= 1, \
                   "At_Least_One_Game_Stack"
    
    # Constraint 8: INTELLIGENT DEFAULTS (Auto-safety without UI toggles)
    # Based on Week 6 analysis: prevent all-contrarian lottery tickets
    
    # 8a. QB SAFETY FLOOR: QB must have Smart Value ≥ 50 OR ownership ≥ 8%
    # Prevents Sam Darnold (0.8 pts) type busts
    if qbs:
        for qb in qbs:
            # QB meets safety if: (smart_value >= 50) OR (ownership >= 8%)
            smart_value = qb.smart_value if hasattr(qb, 'smart_value') and qb.smart_value else 0
            ownership = qb.ownership if qb.ownership else 0
            
            # BLOCK unsafe QBs (neither condition met)
            if smart_value < 50 and ownership < 8:
                # Force this QB to NOT be selected (set to 0)
                prob += player_vars[qb.name] == 0, f"Block_Unsafe_QB_{qb.name.replace(' ', '_')}"
    
    # 8b. BALANCED OWNERSHIP: Max 2 players under 8% ownership (STRICTER)
    # Week 6 analysis: Winners had 1-2 leverage plays, not 6
    # Prevents too many ultra-contrarian lottery tickets
    if 'ownership' in player_pool_df.columns:
        low_own_players = [
            p for p in players 
            if p.ownership is not None and p.ownership < 8.0
        ]
        if low_own_players:
            prob += pulp.lpSum([player_vars[p.name] for p in low_own_players]) <= 2, \
                   "Max_2_Low_Owned"
        
        # NEW: Require at least 2 chalk players (15%+ ownership)
        # Ensures stable base - Week 6 winners had 2-3 chalk anchors
        chalk_players = [
            p for p in players
            if p.ownership is not None and p.ownership >= 15.0
        ]
        if chalk_players:
            prob += pulp.lpSum([player_vars[p.name] for p in chalk_players]) >= 2, \
                   "At_Least_2_Chalk_Anchors"
    
    # 8c. CORE POSITION ANCHOR: At least 1 RB with ownership 15-30% AND Smart Value 70+
    # Ensures one reliable RB to build around (not all dart throws)
    anchor_rbs = [
        p for p in rbs
        if (p.ownership is not None and 15 <= p.ownership <= 30) and
           (hasattr(p, 'smart_value') and p.smart_value and p.smart_value >= 70)
    ]
    if anchor_rbs:
        prob += pulp.lpSum([player_vars[p.name] for p in anchor_rbs]) >= 1, \
               "At_Least_1_Anchor_RB"
    
    # 8d. LINEUP COHESION: Already handled by game stack constraint (#3)
    # Note: Cannot add soft cohesion bonus to objective because multiplying
    # two binary variables (player_vars[p1] * player_vars[p2]) creates non-linear
    # expressions which PuLP cannot handle (requires quadratic programming).
    # The strengthened game stack constraint (3+ from same game) enforces
    # cohesion sufficiently.
    
    # Solve the LP problem using CBC solver (suppress output)
    status = prob.solve(pulp.PULP_CBC_CMD(msg=0))
    
    # Check if optimal solution found
    if status != pulp.LpStatusOptimal:
        error_msg = _interpret_infeasibility(
            status, 
            lineup_number, 
            portfolio_avg_smart_value=portfolio_avg_smart_value,
            max_ownership_enabled=max_ownership_enabled,
            max_ownership_pct=max_ownership_pct,
            locked_count=len(locked_players)
        )
        return None, error_msg
    
    # Extract solution: get selected players
    selected_players = [p for p in players if player_vars[p.name].varValue == 1]
    
    # Sanity check: should have exactly 9 players
    if len(selected_players) != 9:
        return None, f"Solver returned {len(selected_players)} players instead of 9"
    
    # Build Lineup object from selected players
    lineup = _build_lineup_from_players(selected_players, lineup_number)
    
    return lineup, None


def _dataframe_to_players(df: pd.DataFrame) -> List[Player]:
    """
    Convert DataFrame rows to Player objects.
    
    Args:
        df: DataFrame with player data
            Required columns: name, position, salary, projection, team, opponent
            Optional columns: ownership, player_id, selection_state
    
    Returns:
        List of Player objects
    """
    players = []
    
    for _, row in df.iterrows():
        # Handle optional ownership field
        ownership = None
        if 'ownership' in row.index and pd.notna(row['ownership']):
            ownership = float(row['ownership'])
        
        # Handle optional player_id field
        player_id = None
        if 'player_id' in row.index and pd.notna(row['player_id']):
            player_id = str(row['player_id'])
        
        # Handle selection state (for locked players)
        selection_state = PlayerSelection.NORMAL
        if 'selection_state' in row.index and pd.notna(row['selection_state']):
            state_value = row['selection_state']
            if state_value == PlayerSelection.LOCKED.value:
                selection_state = PlayerSelection.LOCKED
            elif state_value == PlayerSelection.EXCLUDED.value:
                selection_state = PlayerSelection.EXCLUDED
        
        # Handle optional smart_value field (for advanced optimization)
        smart_value = None
        if 'smart_value' in row.index and pd.notna(row['smart_value']):
            smart_value = float(row['smart_value'])
        
        # Handle optional game_total field (for game stacking)
        game_total = None
        if 'game_total' in row.index and pd.notna(row['game_total']):
            game_total = float(row['game_total'])
        
        player = Player(
            name=row['name'],
            position=row['position'],
            salary=int(row['salary']),
            projection=float(row['projection']),
            team=row['team'],
            opponent=row['opponent'],
            ownership=ownership,
            player_id=player_id,
            selection=selection_state,
            smart_value=smart_value
        )
        
        # Add game_total as an attribute if available
        if game_total is not None:
            player.game_total = game_total
        players.append(player)
    
    return players


def _build_lineup_from_players(players: List[Player], lineup_number: int) -> Lineup:
    """
    Build Lineup object from 9 selected players, assigning positions correctly.
    
    This function separates players by position and assigns them to the
    appropriate lineup slots. The FLEX position is determined by selecting
    the highest-projected player among remaining RBs, WRs, and TEs after
    filling the core position slots.
    
    Args:
        players: List of exactly 9 Player objects (selected by LP solver)
        lineup_number: Lineup ID for the new lineup
    
    Returns:
        Lineup object with all positions assigned
    
    Raises:
        IndexError: If not enough players of a required position
    """
    # Separate players by position
    qbs = [p for p in players if p.position == 'QB']
    rbs = [p for p in players if p.position == 'RB']
    wrs = [p for p in players if p.position == 'WR']
    tes = [p for p in players if p.position == 'TE']
    dsts = [p for p in players if p.position in ['DST', 'D/ST', 'DEF']]
    
    # Sort each position by projection (descending) for consistent assignment
    qbs.sort(key=lambda p: p.projection, reverse=True)
    rbs.sort(key=lambda p: p.projection, reverse=True)
    wrs.sort(key=lambda p: p.projection, reverse=True)
    tes.sort(key=lambda p: p.projection, reverse=True)
    dsts.sort(key=lambda p: p.projection, reverse=True)
    
    # Assign core positions (QB, DST always single)
    qb = qbs[0]
    dst = dsts[0]
    
    # Assign RBs (first 2 to RB1, RB2; remaining eligible for FLEX)
    rb1 = rbs[0]
    rb2 = rbs[1]
    remaining_rbs = rbs[2:] if len(rbs) > 2 else []
    
    # Assign WRs (first 3 to WR1, WR2, WR3; remaining eligible for FLEX)
    wr1 = wrs[0]
    wr2 = wrs[1]
    wr3 = wrs[2]
    remaining_wrs = wrs[3:] if len(wrs) > 3 else []
    
    # Assign TE (first to TE slot; remaining eligible for FLEX)
    te = tes[0]
    remaining_tes = tes[1:] if len(tes) > 1 else []
    
    # Determine FLEX: pick highest projection among remaining RB/WR/TE
    flex_candidates = remaining_rbs + remaining_wrs + remaining_tes
    
    if not flex_candidates:
        raise ValueError("No players remaining for FLEX position")
    
    flex = max(flex_candidates, key=lambda p: p.projection)
    
    return Lineup(
        lineup_id=lineup_number,
        qb=qb,
        rb1=rb1,
        rb2=rb2,
        wr1=wr1,
        wr2=wr2,
        wr3=wr3,
        te=te,
        flex=flex,
        dst=dst
    )


def _interpret_infeasibility(
    status: int, 
    lineup_number: int,
    portfolio_avg_smart_value: float = None,
    max_ownership_enabled: bool = False,
    max_ownership_pct: float = None,
    locked_count: int = 0
) -> str:
    """
    Interpret LP solver status code and return user-friendly error message with suggestions.
    
    Args:
        status: PuLP status code from prob.solve()
        lineup_number: The lineup number that failed
        portfolio_avg_smart_value: Portfolio average constraint value (if used)
        max_ownership_enabled: Whether ownership filter is enabled
        max_ownership_pct: Maximum ownership percentage (if enabled)
        locked_count: Number of locked players
    
    Returns:
        Human-readable error message explaining the failure with actionable suggestions
    """
    base_messages = {
        pulp.LpStatusInfeasible: "Constraints are too strict - no valid lineup exists",
        pulp.LpStatusUnbounded: "Problem is unbounded (internal error)",
        pulp.LpStatusNotSolved: "Solver failed to run",
    }
    
    error_msg = base_messages.get(status, f"Unknown status: {status}")
    
    # Provide helpful suggestions
    suggestions = []
    
    if portfolio_avg_smart_value:
        suggestions.append(f"Lower the Portfolio Average Smart Value (currently {portfolio_avg_smart_value:.0f})")
    
    if max_ownership_enabled and max_ownership_pct:
        suggestions.append(f"Increase Max Ownership (currently {max_ownership_pct*100:.0f}%)")
    
    if locked_count > 0:
        suggestions.append(f"Unlock some players (currently {locked_count} locked)")
    
    # Always suggest adjusting filters
    suggestions.append("Lower your Smart Value filter thresholds")
    
    suggestion_text = " OR ".join(suggestions) if suggestions else "Try adjusting your constraints"
    
    return f"{error_msg}. Try: {suggestion_text}"

