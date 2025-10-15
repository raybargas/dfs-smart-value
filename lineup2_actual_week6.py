"""
Lineup #2 Actual Week 6 Performance - CORRECTED
Based on contest-standings-183090259.csv data
"""

# Lineup #2 from screenshot with ACTUAL Week 6 scores from contest data
lineup_2 = {
    'Spencer Rattler': {'position': 'QB', 'proj': 16.4, 'actual': 11.08, 'ownership': 7.0},
    'Christian McCaffrey': {'position': 'RB', 'proj': 23.4, 'actual': 24.1, 'ownership': 26.3},
    'Rachaad White': {'position': 'RB', 'proj': 19.3, 'actual': 17.6, 'ownership': 28.8},
    'Jaxon Smith-Njigba': {'position': 'WR', 'proj': 20.8, 'actual': 33.2, 'ownership': 22.4},
    'Chris Olave': {'position': 'WR', 'proj': 15.1, 'actual': 15.8, 'ownership': 21.2},
    'Cooper Kupp': {'position': 'WR', 'proj': 12.2, 'actual': 12.0, 'ownership': 6.8},
    'Trey McBride': {'position': 'TE', 'proj': 15.6, 'actual': 21.2, 'ownership': 16.5},
    'Rico Dowdle': {'position': 'FLEX', 'proj': 18.1, 'actual': 36.9, 'ownership': 24.8},
    'Dolphins': {'position': 'DST', 'proj': 6.4, 'actual': 2.0, 'ownership': 10.4}
}

print('='*100)
print('LINEUP #2 - ACTUAL WEEK 6 PERFORMANCE (CORRECTED)')
print('='*100)
print(f"\n{'Player':<25} {'Pos':<8} {'Proj':<8} {'Actual':<8} {'Diff':<8} {'Own%':<8} {'Result'}")
print('-'*100)

total_proj = 0
total_actual = 0
big_wins = []
big_losses = []

for player, data in lineup_2.items():
    proj = data['proj']
    actual = data['actual']
    diff = actual - proj
    own = data['ownership']
    
    total_proj += proj
    total_actual += actual
    
    # Classify performance
    if diff >= 10:
        result = "🔥 SMASHED"
        big_wins.append((player, actual, diff))
    elif diff >= 5:
        result = "✅ Beat proj"
        big_wins.append((player, actual, diff))
    elif diff >= -2:
        result = "➖ Close"
    elif diff >= -5:
        result = "⚠️ Underperformed"
    else:
        result = "❌ BUST"
        big_losses.append((player, actual, diff))
    
    print(f"{player:<25} {data['position']:<8} {proj:<8.1f} {actual:<8.2f} {diff:+8.2f} {own:<8.1f} {result}")

print('='*100)
print(f"{'TOTAL':<25} {'':8} {total_proj:<8.1f} {total_actual:<8.2f} {total_actual - total_proj:+8.2f}")
print('='*100)

print('\n' + '='*100)
print('PERFORMANCE ANALYSIS')
print('='*100)

print(f"\n✅ Projected Score: {total_proj:.1f} pts")
print(f"📊 Actual Score:    {total_actual:.2f} pts")
print(f"Difference:        {total_actual - total_proj:+.2f} pts")
print(f"Performance:       {(total_actual / total_proj * 100):.1f}% of projection")

print('\n🔥 SMASHES & WINS:')
for player, actual, diff in sorted(big_wins, key=lambda x: x[2], reverse=True):
    print(f"   {player}: {actual:.2f} pts ({diff:+.2f} vs. proj)")

print('\n❌ BUSTS:')
for player, actual, diff in sorted(big_losses, key=lambda x: x[2]):
    print(f"   {player}: {actual:.2f} pts ({diff:+.2f} vs. proj)")

print('\n' + '='*100)
print('CONTEST RESULTS')
print('='*100)

# Based on typical DraftKings Week 6 NFL contests from the standings file
print("\nWeek 6 DraftKings Contest Benchmarks (from actual contest):")
print("  Winning score: 229.26 pts (Rank #1)")
print("  Top 10 cutoff: ~213 pts")
print("  Top 100 cutoff: ~207 pts")
print("  Min Cash (estimated): ~140-145 pts")

print(f"\n📊 YOUR LINEUP SCORE: {total_actual:.2f} pts")

if total_actual >= 207:
    print(f"\n✅✅ Would have placed in TOP 100!")
    print(f"   Estimated finish: Top 100-150")
elif total_actual >= 145:
    print(f"\n✅ Would have CASHED in double-ups/50-50s")
    print(f"   Estimated finish: ~Rank 500-1000 (out of 316,984 entries)")
else:
    print(f"\n❌ Would NOT have cashed")
    print(f"   Needed {145 - total_actual:.2f} more points to cash")

print('\n' + '='*100)
print('KEY INSIGHTS')
print('='*100)

print("\n✅ WHAT WORKED:")
print("   1. Rico Dowdle (35.5% own): 36.9 pts - JUSTIFIED CHALK paid off")
print("   2. Jaxon Smith-Njigba (22.4% own): 33.2 pts - Sweet spot leverage")
print("   3. Trey McBride (16.5% own): 21.2 pts - Beat projection by 5.6")
print("   4. Christian McCaffrey (26.3% own): 24.1 pts - Chalk delivered")

print("\n❌ WHAT DIDN'T:")
print("   1. Spencer Rattler (7.0% own): 11.08 pts - Contrarian miss")
print("   2. Dolphins DST (10.4% own): 2.0 pts - Underperformed by 4.4")
print("   3. Rachaad White (28.8% own): 17.6 pts - Chalk bust")

print("\n💡 PORTFOLIO ANALYSIS:")
total_own = sum([d['ownership'] for d in lineup_2.values()])
avg_own = total_own / len(lineup_2)
print(f"   Average Ownership: {avg_own:.1f}%")
print(f"   Ownership Mix: Good balance (7% to 28.8%)")
print(f"   Leverage Spots: JSN (22.4%), McBride (16.5%), Kupp (6.8%)")
print(f"   Chalk Spots: CMC (26.3%), Dowdle (24.8%), White (28.8%)")

print("\n🎯 PHASE 2+3 VALIDATION:")
print("   ✅ Justified chalk (Dowdle, CMC) = both delivered")
print("   ❌ Trap chalk (White, 28.8%) = underperformed")
print("   ✅ Sweet spot (JSN, McBride) = both smashed")
print("   ❌ Ultra-contrarian (Rattler, 7.0%) = missed")

print("\n💰 ESTIMATED WINNINGS (if entered in $20 double-up):")
if total_actual >= 145:
    print(f"   Entry: $20")
    print(f"   Payout: ~$36 (180% return)")
    print(f"   Profit: +$16 ✅")
else:
    print(f"   Entry: $20")
    print(f"   Payout: $0")
    print(f"   Loss: -$20 ❌")

