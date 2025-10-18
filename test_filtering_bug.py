"""
Test script to isolate the Position SV filtering bug.
Simulates the exact filtering logic used in player_selection.py
"""

import pandas as pd
import sys
from pathlib import Path

# Add parent directory to path
parent_path = Path(__file__).parent
sys.path.insert(0, str(parent_path))

from src.smart_value_calculator import calculate_smart_value

# Create test data matching your player pool
test_data = {
    'name': ['Saquon Barkley', 'Jordan Mason', 'Kareem Hunt', 'Tony Pollard', 'Jonathan Taylor'],
    'position': ['RB', 'RB', 'RB', 'RB', 'RB'],
    'team': ['PHI', 'SF', 'KC', 'TEN', 'IND'],
    'salary': [7700, 6200, 4800, 5400, 8800],
    'projection': [19.9, 14.3, 7.8, 11.3, 23.9],
    'ownership': [6.0, 2.1, 1.4, 1.4, 24.2],
    'opponent': ['@MIN', 'vs PHI', 'vs LV', 'vs NE', '@LAC'],
    'season_ceiling': [36.9, 21.0, 25.4, 23.1, 29.6],
    'game_total': [43.5, 43.5, 45.5, 42.5, 48.5],
    'team_itt': [22.5, 21.0, 28.5, 17.8, 23.5],
}

df = pd.DataFrame(test_data)

# Calculate Smart Value with default balanced weights
print("Calculating Smart Value...")
df = calculate_smart_value(df, profile='balanced', week=7)

# Filter RBs and show both Position SV and Global SV
rb_df = df[df['position'] == 'RB'][['name', 'smart_value', 'smart_value_global']].copy()
rb_df = rb_df.sort_values('smart_value_global', ascending=False)

print("\n=== RB Smart Values ===")
print(rb_df.to_string(index=False))

# Test the filtering logic with threshold 35
threshold = 35
print(f"\n=== Filtering with Threshold {threshold} ===")
for _, row in rb_df.iterrows():
    pos_sv = row['smart_value']
    global_sv = row['smart_value_global']
    passes = pos_sv >= threshold
    print(f"{row['name']:20} | Pos SV: {pos_sv:5.1f} | Global SV: {global_sv:5.1f} | Pass: {passes}")

# Check for logical inconsistencies
print("\n=== Checking for Logic Bugs ===")
sorted_by_global = rb_df.sort_values('smart_value_global', ascending=False)
sorted_by_position = rb_df.sort_values('smart_value', ascending=False)

print("\nGlobal SV Order:", sorted_by_global['name'].tolist())
print("Position SV Order:", sorted_by_position['name'].tolist())

if sorted_by_global['name'].tolist() != sorted_by_position['name'].tolist():
    print("\n⚠️  BUG FOUND: Position SV ranking differs from Global SV ranking for same position!")
    print("This should be IMPOSSIBLE since both use the same raw_score.")
else:
    print("\n✅ Rankings match - Position SV calculation is correct")

