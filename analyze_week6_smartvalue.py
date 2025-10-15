"""
Analyze Week 6 Smart Value Performance vs. Actual Winners
"""

import pandas as pd
import sqlite3

# Load Week 6 salaries (skip first row which is actual header)
df = pd.read_excel('DKSalaries_Week6_2025.xlsx', header=0, skiprows=[0])

# Key players from winning lineups
key_players = {
    'De\'Von Achane': {'actual_pts': 34.0, 'ownership': 4.7, 'leverage': 2.93},
    'George Pickens': {'actual_pts': 34.8, 'ownership': 10.6, 'leverage': 2.42},
    'Kayshon Boutte': {'actual_pts': 26.3, 'ownership': 1.3, 'leverage': 2.50},
    'Josh Jacobs': {'actual_pts': 32.0, 'ownership': 28.9, 'leverage': 1.21},
    'Rico Dowdle': {'actual_pts': 36.9, 'ownership': 35.5, 'leverage': 1.46},
    'Jaxon Smith-Njigba': {'actual_pts': 33.2, 'ownership': 23.8, 'leverage': 0.98},
    'Ladd McConkey': {'actual_pts': 26.0, 'ownership': 14.1, 'leverage': 1.19},
    'Puka Nacua': {'actual_pts': 4.8, 'ownership': 30.8, 'leverage': -2.60},
    'Bryce Young': {'actual_pts': 19.5, 'ownership': 8.4, 'leverage': 1.11},
    'Michael Mayer': {'actual_pts': 16.0, 'ownership': 4.1, 'leverage': 1.19},
}

print('='*100)
print('WEEK 6 KEY PLAYERS - PROJECTION vs. ACTUAL PERFORMANCE')
print('='*100)
print(f'{"Player":<25} {"Pos":<4} {"Salary":<8} {"DK Proj":<9} {"Actual":<8} {"Own%":<7} {"Leverage":<10}')
print('-'*100)

for player_name, actual_data in key_players.items():
    # Try to find player (handle name variations)
    row = df[df['Name'].str.contains(player_name.replace("'", ""), case=False, na=False)]
    
    if not row.empty:
        r = row.iloc[0]
        print(f"{r['Name']:<25} {r['Pos']:<4} ${int(r['S']):<7,} {r['Proj']:<9.1f} {actual_data['actual_pts']:<8.1f} {actual_data['ownership']:<6.1f}% {actual_data['leverage']:<10.2f}")
    else:
        print(f"{player_name:<25} {'N/A':<4} {'N/A':<8} {'N/A':<9} {actual_data['actual_pts']:<8.1f} {actual_data['ownership']:<6.1f}% {actual_data['leverage']:<10.2f}")

print('\n' + '='*100)
print('KEY INSIGHTS')
print('='*100)

# Analyze projection accuracy
print('\n1. DraftKings Projection Accuracy:')
projection_gaps = []
for player_name, actual_data in key_players.items():
    row = df[df['Name'].str.contains(player_name.replace("'", ""), case=False, na=False)]
    if not row.empty:
        r = row.iloc[0]
        proj = r['Proj']
        actual = actual_data['actual_pts']
        gap = actual - proj
        projection_gaps.append({
            'player': r['Name'],
            'proj': proj,
            'actual': actual,
            'gap': gap,
            'ownership': actual_data['ownership']
        })

projection_gaps_df = pd.DataFrame(projection_gaps).sort_values('gap', ascending=False)
print('\n   Biggest Projection Misses (Actual >> Proj):')
for _, row in projection_gaps_df.head(5).iterrows():
    print(f"   {row['player']:<25} Proj: {row['proj']:5.1f} | Actual: {row['actual']:5.1f} | Gap: +{row['gap']:5.1f} | Own: {row['ownership']:4.1f}%")

print('\n   Biggest Projection Busts (Actual << Proj):')
for _, row in projection_gaps_df.tail(3).iterrows():
    print(f"   {row['player']:<25} Proj: {row['proj']:5.1f} | Actual: {row['actual']:5.1f} | Gap: {row['gap']:5.1f} | Own: {row['ownership']:4.1f}%")

print('\n2. Value vs. Chalk Pattern:')
print('   HIGH LEVERAGE (Low Own + Exceeded Proj):')
high_lev = projection_gaps_df[(projection_gaps_df['ownership'] < 15) & (projection_gaps_df['gap'] > 5)]
for _, row in high_lev.iterrows():
    print(f"   ✅ {row['player']:<25} +{row['gap']:4.1f} pts @ {row['ownership']:4.1f}% own")

print('\n   CHALK BUSTS (High Own + Underperformed):')
chalk_bust = projection_gaps_df[(projection_gaps_df['ownership'] > 20) & (projection_gaps_df['gap'] < -5)]
for _, row in chalk_bust.iterrows():
    print(f"   ❌ {row['player']:<25} {row['gap']:4.1f} pts @ {row['ownership']:4.1f}% own")

