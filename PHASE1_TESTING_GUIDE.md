# Phase 1: Testing Guide

**Status**: ✅ ALL CODE COMPLETE - Ready for User Testing  
**Date**: 2025-10-16

---

## 🎯 What to Test

Phase 1 implementation is **100% complete** with all core features built and unit tested (46/46 tests passing). Now it's time for **user acceptance testing** to verify everything works with real data and your MySportsFeeds API.

---

## ✅ Pre-Testing Checklist

### 1. Verify Database Migration
```bash
cd /Users/raybargas/Desktop/Gauntlet_Flow/DFS
python3 migrations/run_migrations.py
```

**Expected Output**:
```
Running Phase 2D migrations...
✓ slates table exists
✓ historical_player_pool table exists
✓ smart_value_profiles_history table exists
✓ injury_patterns table exists
✓ backtest_results table exists
Migration 004 completed successfully
All 17 expected tables found ✓
```

### 2. Verify API Key Setup
```bash
# Set MySportsFeeds API key
export MYSPORTSFEEDS_API_KEY="your_key_here"

# Verify it's set
echo $MYSPORTSFEEDS_API_KEY
```

### 3. Run Unit Tests
```bash
# Test Historical Data Manager
python3 -m pytest tests/test_historical_data_manager.py -v

# Test DFS Salaries API Client
python3 -m pytest tests/test_dfs_salaries_api.py -v

# Run all tests
python3 -m pytest tests/ -v
```

**Expected**: All 46 tests should pass ✅

---

## 🧪 Test Scenarios

### Test 1: Streamlit UI - Auto Fetch Feature ⭐ NEW!
**Goal**: Verify "Fetch Auto" button works in the UI

**Steps**:
1. Start Streamlit app:
   ```bash
   cd /Users/raybargas/Desktop/Gauntlet_Flow/DFS
   streamlit run app.py
   ```

2. Navigate to **Data Ingestion** section

3. Select a week (e.g., Week 7)

4. Click **"🔄 Fetch Auto"** button

5. **Expected Results**:
   - ✅ Spinner appears: "🔄 Fetching Week 7 salaries from MySportsFeeds..."
   - ✅ Success message: "✅ Created slate: 2024-W7-DK-CLASSIC"
   - ✅ Success message: "✅ Fetched 252 players from MySportsFeeds API!"
   - ✅ Data summary displays (total players, positions, salary range)
   - ✅ Player table loads with all columns

6. **If Errors**:
   - ❌ "API Key not found" → Set `MYSPORTSFEEDS_API_KEY` environment variable
   - ❌ "No salary data found" → Week may not be available yet (try previous week)
   - ❌ "Subscription error" → Verify "DFS" addon is active on your MySportsFeeds account

---

### Test 2: Wednesday Automation Script
**Goal**: Verify automated data prep workflow

**Steps**:
1. **Interactive Mode** (Easiest):
   ```bash
   python3 scripts/wednesday_data_prep.py --interactive
   ```
   
   Follow prompts:
   - Week: `7`
   - Season: `2024`
   - Site: `DraftKings`
   - Contest Type: `Classic`
   - Data source: `api`

2. **Direct Mode**:
   ```bash
   python3 scripts/wednesday_data_prep.py --week 7 --season 2024
   ```

3. **Expected Output**:
   ```
   ============================================================
   Wednesday Data Prep - Week 7, 2024 DraftKings
   ============================================================
   INFO - Fetching draftkings salaries for Week 7, 2024
   INFO - Fetched 252 players from draftkings
   INFO - Creating slate for Week 7, 2024 DraftKings
   INFO - Created slate: 2024-W7-DK-CLASSIC
   INFO - Stored 252 players in slate 2024-W7-DK-CLASSIC
   ============================================================
   DATA PREP SUMMARY
   ============================================================
   Slate ID: 2024-W7-DK-CLASSIC
   Players: 252
   Games: 14
   Data Source: mysportsfeeds_draftkings
   Time Elapsed: 2.3s
   ============================================================
   ✅ Ready for optimization! Run Streamlit app to generate lineups.
   ============================================================
   
   ✅ Data prep successful!
   ```

4. **Verify Database**:
   ```python
   from src.historical_data_manager import HistoricalDataManager
   
   manager = HistoricalDataManager()
   
   # Check slate was created
   metadata = manager.get_slate_metadata('2024-W7-DK-CLASSIC')
   print(f"Slate: {metadata['slate_id']}")
   print(f"Players: {metadata['player_count']}")
   print(f"Games: {metadata['games']}")
   
   # Load snapshot
   df = manager.load_historical_snapshot('2024-W7-DK-CLASSIC')
   print(f"\nSnapshot columns: {list(df.columns)}")
   print(f"Sample players:\n{df[['player_name', 'position', 'salary']].head()}")
   ```

---

### Test 3: Monday Automation Script
**Goal**: Verify automated results capture workflow

**Prerequisites**: 
- Must have a slate created first (Test 2)
- Need contest results CSV from DraftKings/FanDuel

**Steps**:
1. **Get Contest Results CSV**:
   - Log into DraftKings account
   - Navigate to completed contest
   - Export standings to CSV

2. **Run Monday Automation** (Interactive):
   ```bash
   python3 scripts/monday_results_capture.py --interactive
   ```
   
   Follow prompts:
   - Week: `7`
   - Season: `2024`
   - Site: `DraftKings`
   - Contest Type: `Classic`
   - CSV path: `/path/to/contest-standings.csv`

3. **Run Monday Automation** (Direct):
   ```bash
   python3 scripts/monday_results_capture.py \
     --week 7 \
     --season 2024 \
     --csv /path/to/contest-standings.csv
   ```

4. **Expected Output**:
   ```
   ============================================================
   Monday Results Capture - Week 7, 2024 DraftKings
   ============================================================
   INFO - Found slate: 2024-W7-DK-CLASSIC (252 players)
   INFO - Parsing CSV results from: contest-standings.csv
   INFO - Detected columns: player='Player', points='FPTS'
   INFO - Parsed 247 player results
   INFO - Matching 247 players to slate 2024-W7-DK-CLASSIC
   INFO - Matched 247/247 players
   INFO - Successfully updated 247 players
   ============================================================
   RESULTS CAPTURE SUMMARY
   ============================================================
   Slate ID: 2024-W7-DK-CLASSIC
   Players Updated: 247/252
   Total Points: 3542.6
   Average Points: 14.3
   Time Elapsed: 1.2s
   ============================================================
   
   ✅ Results capture successful!
   ```

5. **Verify Actual Points Updated**:
   ```python
   from src.historical_data_manager import HistoricalDataManager
   
   manager = HistoricalDataManager()
   
   # Load snapshot with actuals
   df = manager.load_historical_snapshot('2024-W7-DK-CLASSIC', include_actuals=True)
   
   # Check actual points
   print("\nPlayers with actual points:")
   print(df[['player_name', 'projection', 'actual_points']].head(10))
   
   # Calculate projection accuracy
   df_with_actuals = df[df['actual_points'].notna()]
   df_with_actuals['error'] = df_with_actuals['actual_points'] - df_with_actuals['projection']
   print(f"\nAvg projection error: {df_with_actuals['error'].mean():.2f}")
   print(f"RMSE: {(df_with_actuals['error']**2).mean()**0.5:.2f}")
   ```

---

### Test 4: End-to-End Workflow (Complete Cycle) ⭐ CRITICAL
**Goal**: Verify full weekly workflow from data prep → optimization → results capture

**Scenario**: Simulate Week 7 DFS workflow

#### Step 1: Wednesday - Data Prep
```bash
# Fetch salaries and create slate
python3 scripts/wednesday_data_prep.py --week 7 --season 2024
```

**Verify**:
- ✅ Slate created: `2024-W7-DK-CLASSIC`
- ✅ Player pool stored (252 players)
- ✅ Games extracted and stored

#### Step 2: Thursday/Friday - Optimization (Existing Workflow)
1. Open Streamlit app: `streamlit run app.py`
2. Navigate to **Data Ingestion** (already loaded from Step 1)
3. Navigate to **Player Selection** → Select players
4. Navigate to **Optimization Config** → Configure settings
5. Navigate to **Lineup Generation** → Generate lineups
6. Export lineups to CSV

**Verify**:
- ✅ Optimization uses Week 7 data
- ✅ Smart Value scores calculated
- ✅ Lineups generated successfully
- ✅ Lineups exported to CSV

#### Step 3: Monday - Results Capture
**Wait for Sunday/Monday games to complete, then:**

1. Download contest standings from DraftKings
2. Run results capture:
   ```bash
   python3 scripts/monday_results_capture.py --week 7 --csv standings.csv
   ```

**Verify**:
- ✅ Player names matched (247/252 typical)
- ✅ Actual points updated in database
- ✅ Summary shows correct statistics

#### Step 4: Backtesting (NEW CAPABILITY!)
**Now you can replay Week 7 with different Smart Value profiles:**

```python
from src.historical_data_manager import HistoricalDataManager
from src.smart_value_calculator import calculate_smart_value

manager = HistoricalDataManager()

# Load Week 7 snapshot
df = manager.load_historical_snapshot('2024-W7-DK-CLASSIC', include_actuals=True)

# Test different Smart Value profiles
profiles = ['GPP_Contrarian_v1', 'GPP_Balanced_v2', 'Cash_Conservative_v1']

for profile in profiles:
    # Re-calculate Smart Value with this profile
    df_test = df.copy()
    df_test = calculate_smart_value(df_test, profile_name=profile)
    
    # Generate lineups (use existing optimizer)
    # Compare actual results
    # Track which profile performed best
    
    print(f"Profile: {profile}")
    print(f"Top 10 Smart Value players:")
    print(df_test.nlargest(10, 'smart_value')[['player_name', 'smart_value', 'actual_points']])
    print()
```

**Verify**:
- ✅ Can load exact historical snapshot
- ✅ Can re-calculate Smart Value with different profiles
- ✅ Can compare profile performance (actual results)
- ✅ **Foundation for Phase 2 backtesting engine ready!**

---

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'src'"
**Solution**: Run scripts from DFS directory:
```bash
cd /Users/raybargas/Desktop/Gauntlet_Flow/DFS
python3 scripts/wednesday_data_prep.py --help
```

### Issue: "MYSPORTSFEEDS_API_KEY not found"
**Solution**: Set environment variable:
```bash
export MYSPORTSFEEDS_API_KEY="your_key_here"
```

Add to `~/.zshrc` or `~/.bash_profile` for persistence:
```bash
echo 'export MYSPORTSFEEDS_API_KEY="your_key_here"' >> ~/.zshrc
source ~/.zshrc
```

### Issue: "No salary data found for this week"
**Causes**:
1. **Week not available yet** - DFS sites release salaries Wednesday morning
2. **Season parameter wrong** - Verify season year (2024, 2025, etc.)
3. **Site parameter mismatch** - Try both `draftkings` and `fanduel`

**Solution**: Try previous week or check MySportsFeeds documentation

### Issue: "Slate already exists"
**This is expected behavior!** The script prevents duplicate slates.

**To recreate slate**:
```python
from src.historical_data_manager import HistoricalDataManager

manager = HistoricalDataManager()
manager.delete_slate('2024-W7-DK-CLASSIC')
# Now run Wednesday script again
```

### Issue: "Unmatched players" in Monday results
**Expected behavior** - some players may have name variations.

**Check logs**: `monday_results_capture.log` shows unmatched player names

**Common causes**:
- Jr., Sr., III suffixes differ
- Team abbreviations changed (LAR vs LA)
- DST/Defense names vary

**Solution**: Script handles most variations automatically. For persistent issues, add manual mapping in `monday_results_capture.py`.

---

## 📊 Expected Test Results

### Unit Tests
```
tests/test_historical_data_manager.py ............... [ 50%] ✅ 23 passed
tests/test_dfs_salaries_api.py ..................... [100%] ✅ 23 passed

====== 46 passed in 1.5s ======
```

### Automation Scripts
```
Wednesday Data Prep:
- Slate created: 2024-W7-DK-CLASSIC
- Players stored: 252
- Time: 2-3 seconds

Monday Results Capture:
- Players matched: 247/252 (98%)
- Actual points updated: 247
- Time: 1-2 seconds
```

### Streamlit UI
```
Fetch Auto Button:
- API call successful
- Slate auto-created
- Data loaded into UI
- Player table displays correctly
```

---

## ✅ Success Criteria

Phase 1 is **fully validated** when:

1. ✅ **All unit tests pass** (46/46)
2. ✅ **Wednesday automation works** (fetches salaries, creates slate)
3. ✅ **Monday automation works** (captures results, updates actuals)
4. ✅ **Streamlit UI "Fetch Auto" button works** (integrates Wednesday workflow)
5. ✅ **End-to-end workflow completes** (Wed → Thu/Fri → Mon)
6. ✅ **Historical snapshots load correctly** (backtesting ready)

---

## 📝 Test Results Template

Copy this template to track your testing:

```markdown
# Phase 1 Testing Results

Date: _______
Tester: _______

## Test 1: Streamlit UI - Auto Fetch
- [ ] Button appears correctly
- [ ] API key validation works
- [ ] Fetch succeeds for Week ___
- [ ] Slate created: ___________
- [ ] Data loaded into UI
- [ ] Issues: ___________

## Test 2: Wednesday Automation
- [ ] Script runs successfully
- [ ] Slate created: ___________
- [ ] Players stored: ___________
- [ ] Log file created
- [ ] Issues: ___________

## Test 3: Monday Automation
- [ ] Script runs successfully
- [ ] Players matched: ___/___
- [ ] Actual points updated
- [ ] Log file created
- [ ] Issues: ___________

## Test 4: End-to-End Workflow
- [ ] Step 1 (Wednesday): ✅ Complete
- [ ] Step 2 (Optimization): ✅ Complete
- [ ] Step 3 (Monday): ✅ Complete
- [ ] Step 4 (Backtesting): ✅ Complete
- [ ] Issues: ___________

## Overall Assessment
- [ ] Phase 1 is fully validated
- [ ] Ready to proceed to Phase 2

Notes:
_______________________
```

---

## 🚀 Next Steps After Testing

Once all tests pass:

1. **Document any issues found** (create GitHub issues or notes)
2. **Review Phase 1 Implementation Summary** (`PHASE1_IMPLEMENTATION_SUMMARY.md`)
3. **Prepare for Phase 2: Backtesting Engine**
   - Profile versioning system
   - Parallel profile evaluation
   - Performance metrics dashboard
   - Optimization recommendations

---

## 📞 Support

**Logs to Check**:
- `monday_results_capture.log` - Monday automation details
- `wednesday_data_prep.log` - Wednesday automation details
- `streamlit.log` - Streamlit app errors

**Database Inspection**:
```python
from src.historical_data_manager import HistoricalDataManager

manager = HistoricalDataManager()

# List all slates
weeks = manager.get_available_weeks(season=2024)
print(f"Available weeks: {[w['week'] for w in weeks]}")

# Inspect specific slate
metadata = manager.get_slate_metadata('2024-W7-DK-CLASSIC')
print(metadata)
```

**Questions?** Review documentation:
- `PHASE1_PROGRESS.md` - Detailed progress report
- `PHASE1_IMPLEMENTATION_SUMMARY.md` - Complete implementation summary
- `MONDAY_AUTOMATION_GUIDE.md` - Monday automation guide

---

**Happy Testing! 🚀**

Phase 1 is a **massive upgrade** to your DFS system. Once validated, you'll have:
- ✅ Automated weekly workflows
- ✅ Historical data persistence
- ✅ Backtesting capability
- ✅ Foundation for Smart Value profile optimization

**Let's validate and move to Phase 2!** 🎯

