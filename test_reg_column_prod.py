"""
Test script to diagnose REG column issue in production
"""
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from src.regression_analyzer import check_regression_risk

# Load DK salaries (exactly as Streamlit does)
df = pd.read_excel('DKSalaries_Week6_2025.xlsx', header=1)
df.columns = [str(col).lower().strip() for col in df.columns]

# Add required columns that would exist in Streamlit
df = df.rename(columns={'name': 'name', 'pos': 'position', 's': 'salary', 'proj': 'projection', 'own': 'ownership'})
df['value'] = df['projection'] / (df['salary'] / 1000)
df['leverage'] = df['value'] / df['ownership'].replace(0, 100) * 100

print("=" * 80)
print("TESTING REG COLUMN LOGIC - EXACT STREAMLIT SIMULATION")
print("=" * 80)
print()

# Simulate calculate_dfs_metrics() function
regression_risks = []
regression_tooltips = []

print(f"DataFrame has {len(df)} rows")
print()

for idx, row in df.iterrows():
    player_name = row['name']
    try:
        # Check PRIOR week data (Week 5 is prior to Week 6)
        is_at_risk, points, stats = check_regression_risk(player_name, week=5, threshold=20.0, db_path="dfs_optimizer.db")
        
        if is_at_risk and stats:
            regression_risks.append('✓')  # Checkmark indicates regression risk
            tooltip_parts = [f"⚠️ 80/20 REGRESSION RISK"]
            tooltip_parts.append(f"Week 5: {points:.1f} DK pts (20+ threshold)")
            regression_tooltips.append(" | ".join(tooltip_parts))
        else:
            regression_risks.append('')  # No checkmark = no risk or no data
            if points is not None and stats:
                tooltip_parts = [f"Week 5: {points:.1f} DK pts"]
                tooltip_parts.append("No regression risk (scored <20 pts)")
                regression_tooltips.append(" | ".join(tooltip_parts))
            else:
                regression_tooltips.append("No Week 5 data available")
                
    except Exception as e:
        regression_risks.append('')
        regression_tooltips.append(f"Error: {str(e)[:50]}")

print(f"Regression risks list length: {len(regression_risks)}")
print(f"Regression tooltips list length: {len(regression_tooltips)}")
print()

# Assign to DataFrame
df['regression_risk'] = regression_risks
df['regression_tooltip'] = regression_tooltips

print("DataFrame assignment successful!")
print()

# Show first 20 rows with regression data
print("FIRST 20 PLAYERS WITH REG COLUMN:")
print("-" * 80)
for idx, row in df.head(20).iterrows():
    name = row['name']
    reg = row.get('regression_risk', 'MISSING')
    tooltip = row.get('regression_tooltip', 'MISSING')[:50]
    print(f"{reg:2} {name:30} | {tooltip}")

print()
print("=" * 80)
print("CHECKMARK SUMMARY:")
print("=" * 80)
checkmarks = df[df['regression_risk'] == '✓']
print(f"Total players with ✓: {len(checkmarks)}")
print()
if len(checkmarks) > 0:
    print("Players with ✓ checkmark:")
    for idx, row in checkmarks.iterrows():
        print(f"  ✓ {row['name']:30} ({row['position']:3})")
else:
    print("❌ NO CHECKMARKS FOUND!")
    print()
    print("DIAGNOSIS:")
    print("  - The logic is running correctly")
    print("  - But no players meet the '20+ points in Week 5' threshold")
    print("  - OR name matching is failing")

