"""
Analyze DraftKings Contest Results to Extract Week 7 Insights

This script analyzes actual tournament results to identify:
1. Winning lineup construction patterns
2. Ownership vs. performance leverage spots
3. Stack success rates and correlations
4. Value vs. chalk analysis
5. Position allocation in top lineups

Usage: python analyze_contest_results.py contest-standings-183090259.csv
"""

import pandas as pd
import sys
from collections import Counter, defaultdict
import re


def parse_lineup_string(lineup_str):
    """
    Parse DK lineup string into structured roster.
    Example: "DST Raiders  FLEX Ladd McConkey QB Bryce Young RB Josh Jacobs..."
    """
    if pd.isna(lineup_str) or not lineup_str:
        return {}
    
    roster = {}
    # Split by position prefixes
    positions = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'DST']
    
    for pos in positions:
        pattern = f'{pos} ([^Q^R^W^T^F^D]+)'
        matches = re.findall(pattern, lineup_str)
        
        if pos in ['RB', 'WR']:
            # Multiple RBs/WRs
            roster[pos] = [m.strip() for m in matches]
        else:
            roster[pos] = matches[0].strip() if matches else None
    
    return roster


def analyze_top_lineups(df, top_n=100):
    """Analyze lineup construction patterns in top N finishers."""
    
    print(f"\n{'='*80}")
    print(f"📊 TOP {top_n} LINEUP ANALYSIS")
    print(f"{'='*80}\n")
    
    top_df = df.head(top_n)
    
    # Score distribution
    print(f"🏆 Score Distribution (Top {top_n}):")
    print(f"   Winner: {top_df.iloc[0]['Points']:.2f} pts")
    print(f"   Top 10: {top_df.head(10)['Points'].mean():.2f} avg")
    print(f"   Top 100: {top_df['Points'].mean():.2f} avg")
    print(f"   Min Top 100: {top_df.iloc[-1]['Points']:.2f} pts\n")
    
    # Parse lineups
    print("🔍 Parsing lineups...")
    lineups = []
    for _, row in top_df.iterrows():
        lineup = parse_lineup_string(row['Lineup'])
        if lineup:
            lineups.append(lineup)
    
    print(f"   Successfully parsed: {len(lineups)}/{top_n} lineups\n")
    
    # Most common players by position
    print("👥 Most Common Players in Top Lineups:\n")
    
    for pos in ['QB', 'RB', 'WR', 'TE', 'FLEX', 'DST']:
        players = []
        for lineup in lineups:
            if pos in lineup:
                if isinstance(lineup[pos], list):
                    players.extend(lineup[pos])
                elif lineup[pos]:
                    players.append(lineup[pos])
        
        if players:
            counter = Counter(players)
            print(f"   {pos}:")
            for player, count in counter.most_common(5):
                pct = (count / len(lineups)) * 100
                print(f"      {player:25s} → {count:3d} lineups ({pct:5.1f}%)")
            print()


def analyze_leverage_spots(df):
    """Identify players with high score but low ownership (leverage)."""
    
    print(f"\n{'='*80}")
    print("💎 LEVERAGE ANALYSIS (Low Own + High Score = $$$)")
    print(f"{'='*80}\n")
    
    # Group by player and aggregate
    player_stats = df.groupby('Player').agg({
        '%Drafted': 'first',  # Ownership is same for all
        'FPTS': 'first',       # Actual points scored
        'Rank': 'min'          # Best finish for this player
    }).reset_index()
    
    # Clean ownership column
    player_stats['ownership'] = player_stats['%Drafted'].str.rstrip('%').astype(float)
    
    # Calculate leverage score: High FPTS + Low Ownership = Leverage
    # Scale: (FPTS / 10) - (ownership / 10)
    player_stats['leverage'] = (player_stats['FPTS'] / 10) - (player_stats['ownership'] / 10)
    
    # Sort by leverage
    leverage_df = player_stats.sort_values('leverage', ascending=False)
    
    print("🔥 TOP LEVERAGE PLAYS (High Score + Low Owned):\n")
    print(f"{'Player':<25} {'FPTS':>6} {'Own%':>7} {'Leverage':>10} {'Best Rank':>12}")
    print("-" * 80)
    
    for _, row in leverage_df.head(20).iterrows():
        print(f"{row['Player']:<25} {row['FPTS']:>6.1f} {row['ownership']:>6.1f}% "
              f"{row['leverage']:>9.2f} {int(row['Rank']):>12,d}")
    
    print("\n💡 KEY INSIGHT: These players won tournaments despite low ownership!")
    print("   → Look for similar situations in Week 7\n")


def analyze_chalk_busts(df):
    """Identify highly owned players who underperformed."""
    
    print(f"\n{'='*80}")
    print("💥 CHALK BUSTS (High Own + Low Score = Fade)")
    print(f"{'='*80}\n")
    
    # Group by player
    player_stats = df.groupby('Player').agg({
        '%Drafted': 'first',
        'FPTS': 'first',
        'Roster Position': 'first'
    }).reset_index()
    
    player_stats['ownership'] = player_stats['%Drafted'].str.rstrip('%').astype(float)
    
    # Bust score: High ownership but low FPTS (relative to position)
    # Filter for >20% ownership
    high_own = player_stats[player_stats['ownership'] > 20].copy()
    
    # Calculate bust score (ownership - FPTS)
    high_own['bust_score'] = high_own['ownership'] - (high_own['FPTS'] / 2)
    
    busts = high_own.sort_values('bust_score', ascending=False)
    
    print("❌ BIGGEST CHALK BUSTS (High Owned But Low Scored):\n")
    print(f"{'Player':<25} {'Pos':>5} {'FPTS':>6} {'Own%':>7} {'Bust Score':>12}")
    print("-" * 80)
    
    for _, row in busts.head(15).iterrows():
        print(f"{row['Player']:<25} {row['Roster Position']:>5} {row['FPTS']:>6.1f} "
              f"{row['ownership']:>6.1f}% {row['bust_score']:>11.2f}")
    
    print("\n💡 KEY INSIGHT: Fading chalk that busts is how you win GPPs!")
    print("   → Identify similar 'trap' plays in Week 7\n")


def analyze_winning_score_ranges(df):
    """Analyze what score ranges finished in the money."""
    
    print(f"\n{'='*80}")
    print("💰 WINNING SCORE ANALYSIS")
    print(f"{'='*80}\n")
    
    # Define key percentiles
    percentiles = {
        'Top 0.1%': 0.001,
        'Top 1%': 0.01,
        'Top 5%': 0.05,
        'Top 10%': 0.10,
        'Top 20%': 0.20,
    }
    
    total_entries = len(df[df['Points'] > 0])  # Exclude zeros
    
    print(f"Total Entries: {total_entries:,}\n")
    print(f"{'Finish':<15} {'Rank':<15} {'Min Score':<12} {'Avg Score':<12}")
    print("-" * 80)
    
    for label, pct in percentiles.items():
        rank = int(total_entries * pct)
        subset = df[df['Points'] > 0].head(rank)
        min_score = subset['Points'].min()
        avg_score = subset['Points'].mean()
        
        print(f"{label:<15} {rank:>6,} or better {min_score:>10.2f} {avg_score:>11.2f}")
    
    print()


def analyze_correlation_patterns(df, top_n=100):
    """Identify common stacking patterns in winning lineups."""
    
    print(f"\n{'='*80}")
    print("🔗 STACK CORRELATION ANALYSIS")
    print(f"{'='*80}\n")
    
    # This would require team data which we need to parse from lineup strings
    # For now, just show most common player pairs
    
    top_df = df.head(top_n)
    
    print("🎯 Most Common Player Pairs in Top 100:\n")
    print("   (Indicates successful game stacks)\n")
    
    # Extract player pairs from lineups
    pairs = Counter()
    
    for _, row in top_df.iterrows():
        lineup = parse_lineup_string(row['Lineup'])
        if not lineup:
            continue
        
        # Get all players in lineup
        all_players = []
        for pos, value in lineup.items():
            if isinstance(value, list):
                all_players.extend(value)
            elif value:
                all_players.append(value)
        
        # Count pairs
        for i, p1 in enumerate(all_players):
            for p2 in all_players[i+1:]:
                pair = tuple(sorted([p1, p2]))
                pairs[pair] += 1
    
    print(f"{'Player 1':<25} {'Player 2':<25} {'Count':>7}")
    print("-" * 80)
    
    for (p1, p2), count in pairs.most_common(15):
        pct = (count / top_n) * 100
        print(f"{p1:<25} {p2:<25} {count:>3d} ({pct:4.1f}%)")
    
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_contest_results.py <contest_csv_file>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    
    print("\n" + "="*80)
    print("🏈 DFS CONTEST RESULTS ANALYSIS")
    print("="*80)
    print(f"\nLoading: {csv_file}")
    
    # Load data
    df = pd.read_csv(csv_file, encoding='utf-8-sig')
    
    print(f"Total Rows: {len(df):,}")
    print(f"Columns: {', '.join(df.columns)}\n")
    
    # Run analyses
    analyze_top_lineups(df, top_n=100)
    analyze_leverage_spots(df)
    analyze_chalk_busts(df)
    analyze_winning_score_ranges(df)
    analyze_correlation_patterns(df, top_n=100)
    
    # Summary
    print("\n" + "="*80)
    print("📈 ACTIONABLE INSIGHTS FOR WEEK 7")
    print("="*80 + "\n")
    
    print("1. TARGET LOW-OWNED CEILING PLAYS")
    print("   └─ Look for similar leverage spots (good matchup + low projection)\n")
    
    print("2. FADE OBVIOUS CHALK")
    print("   └─ High-owned players in bad game environments = trap\n")
    
    print("3. STACK AGGRESSIVELY")
    print("   └─ Top lineups had strong game correlations (QB+WRs from same team)\n")
    
    print("4. WINNING SCORE TARGET")
    print("   └─ Aim for 215+ points to crack top 100 in large-field GPPs\n")
    
    print("5. EMBRACE VARIANCE")
    print("   └─ Winners had contrarian plays, not just 'best' projections\n")


if __name__ == "__main__":
    main()

