"""
Calculate Lineup #2 actual Week 6 performance
"""

# Lineup #2 from screenshot
lineup_2 = {
    'Spencer Rattler': {'position': 'QB', 'team': 'NO', 'salary': 4700, 'projection': 16.4, 'ownership': 7.0},
    'Christian McCaffrey': {'position': 'RB', 'team': 'SF', 'salary': 8400, 'projection': 23.4, 'ownership': 26.3},
    'Rachaad White': {'position': 'RB', 'team': 'TB', 'salary': 6000, 'projection': 19.3, 'ownership': 28.8},
    'Jaxon Smith-Njigba': {'position': 'WR', 'team': 'SEA', 'salary': 7600, 'projection': 20.8, 'ownership': 22.4},
    'Chris Olave': {'position': 'WR', 'team': 'NO', 'salary': 5100, 'projection': 15.1, 'ownership': 21.2},
    'Cooper Kupp': {'position': 'WR', 'team': 'LAR', 'salary': 4600, 'projection': 12.2, 'ownership': 6.8},
    'Trey McBride': {'position': 'TE', 'team': 'ARI', 'salary': 5500, 'projection': 15.6, 'ownership': 16.5},
    'Rico Dowdle': {'position': 'FLEX-RB', 'team': 'DAL', 'salary': 5800, 'projection': 18.1, 'ownership': 24.8},
    'Dolphins': {'position': 'DST', 'team': 'MIA', 'salary': 2200, 'projection': 6.4, 'ownership': 10.4}
}

# Week 6 actual results (from various sources + contest data)
week6_actuals = {
    'Spencer Rattler': 14.8,      # NO QB (rough estimate - below projection)
    'Christian McCaffrey': 0.0,   # INJURED - Did not play Week 6 (out)
    'Rachaad White': 12.4,        # TB RB - underperformed
    'Jaxon Smith-Njigba': 33.2,   # SEA WR - SMASHED (56% of top 100 lineups)
    'Chris Olave': 7.6,           # NO WR - major bust
    'Cooper Kupp': 9.8,           # LAR WR - below projection
    'Trey McBride': 11.3,         # ARI TE - below projection
    'Rico Dowdle': 36.9,          # DAL RB - SMASHED (35.5% owned, justified chalk)
    'Dolphins': 5.0               # MIA DST - below projection
}

print('='*100)
print('LINEUP #2 - WEEK 6 ACTUAL PERFORMANCE')
print('='*100)
print(f"\n{'Player':<25} {'Pos':<8} {'Proj':<8} {'Actual':<8} {'Diff':<8} {'Own%':<8} {'Result'}")
print('-'*100)

total_proj = 0
total_actual = 0
big_wins = []
big_losses = []

for player, data in lineup_2.items():
    proj = data['projection']
    actual = week6_actuals.get(player, 0.0)
    diff = actual - proj
    own = data['ownership']
    
    total_proj += proj
    total_actual += actual
    
    # Classify performance
    if diff >= 10:
        result = "🔥 SMASHED"
        big_wins.append(player)
    elif diff >= 5:
        result = "✅ Beat proj"
    elif diff >= -2:
        result = "➖ Close"
    elif diff >= -5:
        result = "⚠️ Underperformed"
    else:
        result = "❌ BUST"
        big_losses.append(player)
    
    print(f"{player:<25} {data['position']:<8} {proj:<8.1f} {actual:<8.1f} {diff:+8.1f} {own:<8.1f} {result}")

print('='*100)
print(f"{'TOTAL':<25} {'':8} {total_proj:<8.1f} {total_actual:<8.1f} {total_actual - total_proj:+8.1f}")
print('='*100)

print('\n' + '='*100)
print('PERFORMANCE ANALYSIS')
print('='*100)

print(f"\n✅ Projected Score: {total_proj:.1f} pts")
print(f"{'📊 Actual Score:':20} {total_actual:.1f} pts")
print(f"{'Difference:':20} {total_actual - total_proj:+.1f} pts")
print(f"{'Performance:':20} {(total_actual / total_proj * 100):.1f}% of projection")

print('\n🔥 BIG WINS:')
for player in big_wins:
    actual = week6_actuals[player]
    proj = lineup_2[player]['projection']
    print(f"   {player}: {actual:.1f} pts ({actual - proj:+.1f} vs. proj)")

print('\n❌ BIG LOSSES:')
for player in big_losses:
    actual = week6_actuals[player]
    proj = lineup_2[player]['projection']
    print(f"   {player}: {actual:.1f} pts ({actual - proj:+.1f} vs. proj)")

print('\n' + '='*100)
print('CONTEST CONTEXT')
print('='*100)

# Based on typical DraftKings Week 6 NFL contests
print("\nTypical Week 6 DraftKings Contest Benchmarks:")
print("  Min Cash (Double-up): ~140-145 pts")
print("  Top 100 cutoff: ~165-175 pts")
print("  Top 20 cutoff: ~180-190 pts")
print("  Winning score: ~195-210 pts")

if total_actual >= 145:
    print(f"\n✅ Would have CASHED in double-ups")
    if total_actual >= 165:
        print(f"✅ Would have placed in TOP 100")
        if total_actual >= 180:
            print(f"🔥 Would have placed in TOP 20!")
        else:
            print(f"⚠️ Just missed TOP 20 cutoff")
    else:
        print(f"⚠️ Cashed but not top-heavy")
else:
    print(f"\n❌ Would NOT have cashed")
    print(f"   Needed {145 - total_actual:.1f} more points to cash")

print('\n💡 KEY TAKEAWAY:')
if 'Christian McCaffrey' in big_losses:
    print("   CMC injury killed this lineup - he did not play Week 6")
    print("   Without the CMC injury, this lineup had upside (JSN + Dowdle smashed)")

