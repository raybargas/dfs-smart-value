# Database Update Guide

## Overview

The DFS Optimizer uses a SQLite database (`dfs_optimizer.db`) to store player data. This database contains two types of data:

1. **Season-level stats** (from your Excel file): Snaps, trends, momentum, season ceiling
2. **Game-by-game stats** (from MySportsFeeds API): Individual game performances for regression risk

## Updating with New Weekly Data

When you receive updated weekly data (e.g., "2025 Stats thru week 6.xlsx"), follow these steps:

### 1. Save the Excel File

Place the new Excel file in the `DFS/` directory:
```bash
/Users/raybargas/Desktop/Gauntlet_Flow/DFS/2025 Stats thru week 6.xlsx
```

### 2. Run the Import Script

```bash
cd /Users/raybargas/Desktop/Gauntlet_Flow/DFS
python3 scripts/import_season_data.py "2025 Stats thru week 6.xlsx"
```

**Expected Output:**
```
✅ Loaded 1696 player records from Excel
✅ Import complete!
   - New records: 50
   - Updated records: 1646
   - Total: 1696
💾 Database updated: dfs_optimizer.db
```

### 3. Test Locally

Run the Streamlit app locally to verify the data:
```bash
streamlit run app.py
```

Check that:
- ✅ Player stats are current
- ✅ Season ceiling values are updated
- ✅ Regression risk indicators show for Week X-1 players

### 4. Commit and Deploy

```bash
git add dfs_optimizer.db
git commit -m "Update season stats through week 6"
git push origin main
```

Streamlit Cloud will automatically redeploy with the updated database.

---

## Database Structure

### `season_stats` Table

| Column | Description | Source |
|--------|-------------|--------|
| `player_name` | Player's full name | Excel: "Name" |
| `position` | Position (QB, RB, WR, TE, DST) | Excel: "Position" |
| `team` | Team abbreviation | Excel: "Team" |
| `games_played` | Games played this season | Excel: "Games" |
| `snap_percentage_avg` | Average snap % | Excel: "Snap %" |
| `snap_percentage_std` | Snap % volatility | Excel: "Snap % Std" |
| `snap_percentage_trend` | Snap % change (W1→WX) | Excel: "Snap Trend" |
| `fantasy_points_avg` | Average fantasy points per game | Excel: "FP/G" |
| `fantasy_points_std` | FP volatility | Excel: "FP Std" |
| `fantasy_points_trend` | FP momentum | Excel: "FP Trend" |
| `season_ceiling` | Best weekly score | Excel: "Season Ceiling" |
| `last_updated` | Timestamp of last import | Auto-generated |
| `data_source` | Excel filename imported from | Auto-generated |

### `game_boxscores` & `player_game_stats` Tables

These tables store game-by-game performance data for regression risk analysis. They are populated via the MySportsFeeds API (not from Excel).

**Current Status:** Week 5 data is available in the database.

---

## Troubleshooting

### "No Week X data available" in tooltips

**Cause:** The `player_game_stats` table is missing game-by-game data for Week X.

**Solution:** The app needs to fetch this data from the MySportsFeeds API. This is separate from the season stats import. Contact your developer to run the API fetch script for Week X.

### Import script shows 0 records

**Check:**
1. Is the Excel file in the correct location?
2. Does it have a sheet named "Snaps"?
3. Does the "Snaps" sheet have a "Name" column?

### Database too large for Git

**Current size:** ~10-20 MB (acceptable for Git)

**If it exceeds 50 MB:** Consider using Git LFS or switching to a remote database solution.

---

## Weekly Workflow Summary

```
📥 Receive Excel file
   ↓
📋 Save to DFS/ directory  
   ↓
⚙️  Run: python3 scripts/import_season_data.py "2025 Stats thru week X.xlsx"
   ↓
🧪 Test locally
   ↓
✅ Commit: git add dfs_optimizer.db && git commit -m "Update week X stats"
   ↓
🚀 Deploy: git push origin main
   ↓
🎉 Streamlit Cloud auto-deploys
```

---

## Notes

- **The database file IS committed to Git** (exception added to `.gitignore`)
- **Season stats** (Excel) and **game stats** (API) are separate data sources
- **Regression risk** requires game-by-game data from the API, not Excel
- **Updates are cumulative**: Each import updates existing players and adds new ones

