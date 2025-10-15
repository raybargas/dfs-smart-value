"""
Stacking Analyzer Module

This module analyzes DFS lineups for same-team stacking patterns and calculates
appropriate penalties based on realistic correlation scenarios.

The stacking penalty addresses the issue where optimizers create unrealistic
lineups with 3+ players from the same team, which rarely all hit their ceilings
simultaneously due to game script dependencies and diminishing returns.
"""

from typing import Dict, List, Tuple
from collections import Counter
try:
    from .models import Lineup, Player
except ImportError:
    from models import Lineup, Player


def detect_stacking_patterns(lineup: Lineup) -> Dict[str, int]:
    """
    Analyze a lineup for same-team stacking patterns.
    
    Args:
        lineup: Lineup object to analyze
        
    Returns:
        Dict mapping team abbreviations to player counts
        Example: {'KC': 3, 'SF': 2, 'BUF': 1}
    """
    team_counts = Counter()
    
    for player in lineup.players:
        team_counts[player.team] += 1
    
    return dict(team_counts)


def calculate_stacking_penalty(lineup: Lineup, penalty_weight: float = 1.0) -> float:
    """
    Calculate stacking penalty for a lineup based on same-team player counts.
    
    Penalty Rules:
    - 2 players from same team: No penalty (legitimate stacking)
    - 3 players from same team: 10% penalty per additional player
    - 4+ players from same team: 20% penalty per additional player
    - Multiple teams with 3+ players: Penalties are additive
    
    Args:
        lineup: Lineup object to analyze
        penalty_weight: Multiplier for penalty strength (0.0 = no penalty, 1.0 = full penalty)
        
    Returns:
        float: Penalty multiplier (0.0 = no penalty, 0.3 = 30% penalty)
    """
    team_counts = detect_stacking_patterns(lineup)
    
    total_penalty = 0.0
    
    for team, count in team_counts.items():
        if count >= 3:
            # Calculate penalty based on excess players
            excess_players = count - 2  # 2 players is acceptable
            
            if count == 3:
                # 3 players: 10% penalty
                team_penalty = excess_players * 0.10
            elif count == 4:
                # 4 players: 20% penalty
                team_penalty = excess_players * 0.20
            else:
                # 5+ players: 30% penalty (cap)
                team_penalty = min(excess_players * 0.30, 0.30)
            
            total_penalty += team_penalty
    
    # Apply penalty weight multiplier
    final_penalty = total_penalty * penalty_weight
    
    # Cap total penalty at 50% to prevent extreme cases
    return min(final_penalty, 0.50)


def get_stacking_analysis(lineup: Lineup) -> Dict[str, any]:
    """
    Get detailed stacking analysis for a lineup.
    
    Args:
        lineup: Lineup object to analyze
        
    Returns:
        Dict with detailed stacking information:
        - team_counts: Dict of team -> player count
        - penalty: Calculated penalty multiplier
        - stacking_teams: List of teams with 3+ players
        - analysis: Human-readable analysis string
    """
    team_counts = detect_stacking_patterns(lineup)
    penalty = calculate_stacking_penalty(lineup)
    
    # Find teams with stacking (3+ players)
    stacking_teams = [team for team, count in team_counts.items() if count >= 3]
    
    # Build analysis string
    analysis_parts = []
    
    if not stacking_teams:
        analysis_parts.append("✅ No stacking detected (all teams have ≤2 players)")
    else:
        for team in stacking_teams:
            count = team_counts[team]
            analysis_parts.append(f"⚠️ {team}: {count} players")
        
        if penalty > 0:
            analysis_parts.append(f"📉 Penalty: {penalty:.1%} Smart Value reduction")
    
    return {
        'team_counts': team_counts,
        'penalty': penalty,
        'stacking_teams': stacking_teams,
        'analysis': " | ".join(analysis_parts)
    }


def apply_stacking_penalty_to_lineups(lineups: List[Lineup], penalty_weight: float = 1.0) -> List[Lineup]:
    """
    Apply stacking penalty to a list of lineups by adjusting their Smart Value scores.
    
    Args:
        lineups: List of Lineup objects
        penalty_weight: Multiplier for penalty strength (0.0 = no penalty, 1.0 = full penalty)
        
    Returns:
        List of Lineup objects with adjusted Smart Value scores
    """
    for lineup in lineups:
        penalty = calculate_stacking_penalty(lineup, penalty_weight)
        
        # Apply penalty to Smart Value (if it exists)
        if hasattr(lineup, 'smart_value') and lineup.smart_value is not None:
            lineup.smart_value *= (1.0 - penalty)
        
        # Store penalty info for debugging/display
        lineup.stacking_penalty = penalty
        lineup.stacking_analysis = get_stacking_analysis(lineup)
    
    return lineups


def validate_stacking_rules(lineup: Lineup) -> Tuple[bool, str]:
    """
    Validate if a lineup follows reasonable stacking rules.
    
    Args:
        lineup: Lineup object to validate
        
    Returns:
        Tuple of (is_valid, reason)
    """
    team_counts = detect_stacking_patterns(lineup)
    
    # Check for excessive stacking
    max_team_count = max(team_counts.values()) if team_counts else 0
    
    if max_team_count >= 4:
        return False, f"Too many players from one team (max: {max_team_count})"
    
    # Check for multiple teams with 3+ players
    teams_with_3_plus = [team for team, count in team_counts.items() if count >= 3]
    
    if len(teams_with_3_plus) > 1:
        return False, f"Multiple teams with 3+ players: {teams_with_3_plus}"
    
    return True, "Valid stacking pattern"


# Example usage and testing
if __name__ == "__main__":
    # Test with sample lineup data
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from models import Player, Lineup, PlayerSelection
    
    # Create test players
    test_players = [
        Player("QB1", "QB", 6000, 20.0, "KC", "BUF", 15.0),
        Player("RB1", "RB", 7000, 18.0, "KC", "BUF", 25.0),
        Player("RB2", "RB", 5000, 15.0, "SF", "TB", 20.0),
        Player("WR1", "WR", 8000, 22.0, "KC", "BUF", 30.0),
        Player("WR2", "WR", 6000, 16.0, "KC", "BUF", 18.0),
        Player("WR3", "WR", 4000, 12.0, "SF", "TB", 10.0),
        Player("TE1", "TE", 3000, 8.0, "SF", "TB", 5.0),
        Player("FLEX1", "WR", 3500, 10.0, "SF", "TB", 8.0),
        Player("DST1", "DST", 2000, 6.0, "SF", "TB", 12.0)
    ]
    
    # Create test lineup
    test_lineup = Lineup(
        lineup_id=1,
        qb=test_players[0],
        rb1=test_players[1],
        rb2=test_players[2],
        wr1=test_players[3],
        wr2=test_players[4],
        wr3=test_players[5],
        te=test_players[6],
        flex=test_players[7],
        dst=test_players[8]
    )
    
    # Test stacking analysis
    analysis = get_stacking_analysis(test_lineup)
    print("Stacking Analysis:")
    print(f"Team counts: {analysis['team_counts']}")
    print(f"Penalty: {analysis['penalty']:.1%}")
    print(f"Stacking teams: {analysis['stacking_teams']}")
    print(f"Analysis: {analysis['analysis']}")
    
    # Test validation
    is_valid, reason = validate_stacking_rules(test_lineup)
    print(f"\nValidation: {'✅ Valid' if is_valid else '❌ Invalid'}")
    print(f"Reason: {reason}")
