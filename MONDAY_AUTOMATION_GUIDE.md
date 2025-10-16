# Monday Automation Guide

## Purpose
The Monday Automation script (`scripts/monday_results_capture.py`) automatically captures contest results after games complete and updates actual fantasy points in the historical database.

This enables:
- ✅ Accurate backtesting with real outcomes
- ✅ Smart Value profile performance tracking
- ✅ Season-long trend analysis
- ✅ Injury pattern learning (future feature)

---

## Quick Start

### Interactive Mode (Easiest)
```bash
cd /Users/raybargas/Desktop/Gauntlet_Flow/DFS
python3 scripts/monday_results_capture.py --interactive
```

Follow the prompts to:
1. Enter week number
2. Enter season year
3. Enter DFS site (DraftKings/FanDuel)
4. Enter path to results CSV
5. Confirm and run

### Manual Mode
```bash
python3 scripts/monday_results_capture.py \
  --week 6 \
  --season 2024 \
  --csv /path/to/contest-standings.csv \
  --site DraftKings
```

### Automated Mode (Phase 2)
```bash
# Coming soon - will fetch results via DFS API
python3 scripts/monday_results_capture.py --week 6 --auto
```

---

## CSV Format Requirements

The script auto-detects column names from popular DFS sites:

### DraftKings Format
```csv
Rank,EntryId,EntryName,Player,FPTS
1,123456,User1,Patrick Mahomes,28.4
2,123457,User2,Travis Kelce,14.2
```

### FanDuel Format
```csv
Player,Position,Team,Fantasy Points,Salary
Patrick Mahomes,QB,KC,28.4,8500
Travis Kelce,TE,KC,14.2,7200
```

### Custom Format
Any CSV with these columns (case-insensitive):
- **Player Name**: `Player`, `Name`, `Player Name`, `player_name`
- **Fantasy Points**: `FPTS`, `Fantasy Points`, `Points`, `Actual`, `actual_points`

---

## Workflow

### Monday Morning Process
1. **Download Contest Results**
   - Log into DraftKings/FanDuel
   - Navigate to contest standings
   - Export to CSV

2. **Run Automation Script**
   ```bash
   python3 scripts/monday_results_capture.py \
     --week 6 \
     --season 2024 \
     --csv ~/Downloads/contest-standings.csv
   ```

3. **Verify Results**
   - Check `monday_results_capture.log` for summary
   - Script reports:
     - Players matched: `247/250`
     - Total points: `3,542.6`
     - Average points: `14.3`

4. **Handle Unmatched Players**
   - Script logs unmatched player names
   - Usually caused by name variations (Jr., Sr., III)
   - Script attempts fuzzy matching automatically
   - Manual fixes only needed for unusual cases

---

## Scheduling

### Cron Job (Automated Weekly Run)
```bash
# Run every Monday at 2:00 PM ET (after SNF/MNF)
0 14 * * 1 cd /path/to/DFS && /usr/bin/python3 scripts/monday_results_capture.py --auto
```

### GitHub Actions (Cloud Automation)
```yaml
name: Monday Results Capture
on:
  schedule:
    - cron: '0 14 * * 1'  # Monday 2 PM ET
  workflow_dispatch:  # Manual trigger

jobs:
  capture:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Monday Capture
        run: python3 scripts/monday_results_capture.py --auto
```

---

## Troubleshooting

### Error: "Slate not found"
**Cause**: No historical slate exists for this week/site.

**Solution**: Create slate first using Wednesday automation:
```bash
python3 scripts/wednesday_data_prep.py --week 6 --season 2024
```

### Error: "No players matched"
**Cause**: Player names in CSV don't match slate.

**Solutions**:
1. Verify CSV is from correct week/site
2. Check player name format (exact match required)
3. Use `--site` flag to specify correct DFS platform

### Error: "Could not find player or points columns"
**Cause**: CSV format not recognized.

**Solution**: Ensure CSV has columns:
- Player name: `Player`, `Name`, `Player Name`
- Fantasy points: `FPTS`, `Fantasy Points`, `Points`

---

## Architecture

### Data Flow
```
Contest Results CSV
        ↓
    Parse CSV
        ↓
  Match Players → Historical Player Pool
        ↓
  Update Actuals → database (historical_player_pool)
        ↓
   Log Results → monday_results_capture.log
```

### Database Impact
Updates `historical_player_pool.actual_points`:
```sql
UPDATE historical_player_pool
SET actual_points = 28.4
WHERE slate_id = '2024-W6-DK-CLASSIC'
  AND player_name = 'Patrick Mahomes';
```

### Logging
- **File**: `monday_results_capture.log`
- **Format**: Timestamp + Level + Message
- **Content**:
  - CSV parsing progress
  - Player matching results
  - Database update counts
  - Error details (if any)

---

## Future Enhancements (Phase 2)

### DFS API Integration
- Auto-fetch results from DraftKings API
- No manual CSV download required
- Run fully automated via cron/GitHub Actions

### Slack/Email Notifications
```
✅ Monday Results Captured
Week 6, 2024 DraftKings
247/250 players updated
Avg: 14.3 FPTS
```

### Multi-Contest Support
- Capture results from multiple contests
- Compare performance across contest types
- Showdown vs. Classic analysis

---

## Related Scripts

| Script | Purpose | When to Run |
|--------|---------|-------------|
| `monday_results_capture.py` | Update actual points | Monday after games |
| `wednesday_data_prep.py` | Fetch salaries/projections | Wednesday before slate |
| `historical_data_manager.py` | Core data management | (Library - not run directly) |

---

## Examples

### Example 1: Week 6 DraftKings
```bash
python3 scripts/monday_results_capture.py \
  --week 6 \
  --season 2024 \
  --csv contest-standings-183090259.csv \
  --site DraftKings
```

**Output**:
```
2025-10-16 14:00:01 - INFO - ============================================================
2025-10-16 14:00:01 - INFO - Monday Results Capture - Week 6, 2024 DraftKings
2025-10-16 14:00:01 - INFO - ============================================================
2025-10-16 14:00:01 - INFO - Found slate: 2024-W6-DK-CLASSIC (250 players)
2025-10-16 14:00:01 - INFO - Parsing CSV results from: contest-standings-183090259.csv
2025-10-16 14:00:01 - INFO - Detected columns: player='Player', points='FPTS'
2025-10-16 14:00:01 - INFO - Parsed 247 player results
2025-10-16 14:00:02 - INFO - Matched 247/247 players
2025-10-16 14:00:02 - INFO - Successfully updated 247 players
2025-10-16 14:00:02 - INFO - ============================================================
2025-10-16 14:00:02 - INFO - RESULTS CAPTURE SUMMARY
2025-10-16 14:00:02 - INFO - ============================================================
2025-10-16 14:00:02 - INFO - Slate ID: 2024-W6-DK-CLASSIC
2025-10-16 14:00:02 - INFO - Players Updated: 247/250
2025-10-16 14:00:02 - INFO - Total Points: 3542.6
2025-10-16 14:00:02 - INFO - Average Points: 14.3
2025-10-16 14:00:02 - INFO - Time Elapsed: 1.2s
2025-10-16 14:00:02 - INFO - ============================================================

✅ Results capture successful!
```

### Example 2: Interactive Mode
```bash
$ python3 scripts/monday_results_capture.py --interactive

============================================================
MONDAY RESULTS CAPTURE - INTERACTIVE MODE
============================================================
Enter week number (1-18): 6
Enter season year (e.g., 2024): 2024
Enter DFS site (DraftKings/FanDuel) [DraftKings]: DraftKings
Enter contest type (Classic/Showdown) [Classic]: Classic
Enter path to contest results CSV: /Users/ray/Downloads/contest-standings.csv

------------------------------------------------------------
Week: 6
Season: 2024
Site: DraftKings
Contest Type: Classic
CSV: /Users/ray/Downloads/contest-standings.csv
------------------------------------------------------------

Proceed with results capture? (yes/no): yes

[Processing...]

✅ Results capture successful!
```

---

## Support

**Issues?** Check:
1. `monday_results_capture.log` for detailed error messages
2. Verify slate exists: `python3 -c "from src.historical_data_manager import HistoricalDataManager; m = HistoricalDataManager(); print(m.get_slate_metadata('2024-W6-DK-CLASSIC'))"`
3. Verify CSV format matches requirements above

**Questions?** Open an issue or contact the development team.

---

**Last Updated**: 2025-10-16  
**Script Version**: 1.0  
**Phase**: 1 (Foundation)

