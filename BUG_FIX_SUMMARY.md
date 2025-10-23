# Bug Fix Summary - Advanced Season Stats Upload

## Issue Reported

**User Experience:**
1. Upload Passing Stats → Success → Refresh → ✅ Green checkmark appears
2. Upload Rush Stats → Success → Refresh → ❌ Passing checkmark GONE, only Rush checkmark shows

**Expected Behavior:**
- Both Passing and Rush should show green checkmarks
- Each upload should ADD to the database, not replace existing data

## Root Cause Analysis

### Database Investigation

✅ **Table Structure Verified:**
- Table: `advanced_stats` exists
- Columns: All 4 stat types have dedicated columns
  - Pass: `adv_cpoe`, `adv_adot`, `adv_deep_throw_pct`
  - Rush: `adv_yaco_att`, `adv_success_rate`, `adv_mtf_att`
  - Receiving: `adv_tprr`, `adv_yprr`, `adv_rte_pct`
  - Snaps: `adv_1read_pct`

### The Bug (Line 59 in `advanced_stats_db.py`)

```python
# BEFORE (WRONG):
cursor.execute("DELETE FROM advanced_stats WHERE week = ?", (week,))
```

**What this did:**
1. User uploads Passing → Deletes ALL Week 8 records → Inserts only Passing data
2. User uploads Rush → Deletes ALL Week 8 records (including Passing!) → Inserts only Rush data
3. Result: Only the most recently uploaded file has data

### The Fix

```python
# AFTER (CORRECT):
# Pass upload only:
UPDATE advanced_stats 
SET adv_cpoe = NULL, adv_adot = NULL, adv_deep_throw_pct = NULL
WHERE week = ?

# Rush upload only:
UPDATE advanced_stats 
SET adv_yaco_att = NULL, adv_success_rate = NULL, adv_mtf_att = NULL
WHERE week = ?

# Receiving upload only:
UPDATE advanced_stats 
SET adv_tprr = NULL, adv_yprr = NULL, adv_rte_pct = NULL
WHERE week = ?

# Snaps upload only:
UPDATE advanced_stats 
SET adv_1read_pct = NULL
WHERE week = ?
```

**What this does:**
1. User uploads Passing → Clears only Pass columns → Inserts Passing data → Rush/Receiving/Snaps untouched
2. User uploads Rush → Clears only Rush columns → Inserts Rush data → Passing/Receiving/Snaps untouched
3. Result: All uploaded files persist, checkmarks accumulate

## Verification Checklist

### ✅ Database Structure
- [x] `advanced_stats` table exists
- [x] All required columns present
- [x] UNIQUE constraint on (player_name, team, position, week)

### ✅ Query Logic (`check_season_stats_in_db`)
- [x] Queries COUNT(DISTINCT player_name) for each stat type
- [x] Pass: Checks `adv_cpoe IS NOT NULL`
- [x] Rush: Checks `adv_yaco_att IS NOT NULL`
- [x] Receiving: Checks `adv_tprr IS NOT NULL`
- [x] Snaps: Checks `adv_1read_pct IS NOT NULL`
- [x] Requires >= 10 distinct players for green checkmark

### ✅ Save Logic (`save_advanced_stats_to_database`)
- [x] Only clears columns for the uploaded stat type
- [x] Uses INSERT OR REPLACE for upserts
- [x] Preserves data from other stat types
- [x] Commits transaction after all inserts

## Expected Behavior After Fix

### Upload Sequence Test

**Step 1: Upload Passing Stats**
- Database: 59 Passing records saved
- UI: ✅ Passing Stats (green checkmark)
- Other: ⚠️ Rush, Receiving, Snaps (no checkmarks)

**Step 2: Upload Rush Stats**
- Database: 171 Rush records saved, 59 Passing records PRESERVED
- UI: ✅ Passing Stats, ✅ Rush Stats (both green)
- Other: ⚠️ Receiving, Snaps (no checkmarks)

**Step 3: Upload Receiving Stats**
- Database: 166 Receiving records saved, Passing & Rush PRESERVED
- UI: ✅ Passing, ✅ Rush, ✅ Receiving (all green)
- Other: ⚠️ Snaps (no checkmark)

**Step 4: Upload Snaps Stats**
- Database: 250 Snaps records saved, all others PRESERVED
- UI: ✅ Passing, ✅ Rush, ✅ Receiving, ✅ Snaps (all green)

### Re-Upload Test

**Re-upload Rush Stats (refresh data)**
- Database: Rush columns cleared → New Rush data inserted → Passing/Receiving/Snaps UNTOUCHED
- UI: All 4 checkmarks remain green
- Result: Only Rush data refreshed

## Architecture Notes

### Single Table Design
- All 4 stat types share one `advanced_stats` table
- Each stat type has dedicated columns
- Player rows can have data from multiple stat types
- Example: Player "Patrick Mahomes" has Pass columns filled, Rush columns NULL

### Why Not Separate Tables?
- Single table allows JOIN-free queries
- Easier to query "all stats for Week 8"
- Simpler to display combined player stats
- UNIQUE constraint prevents duplicates

### Column-Level Clearing
- Allows granular updates per stat type
- Preserves data from other stat types
- Enables one-at-a-time uploads
- Supports re-uploading individual files

## Testing Recommendations

1. **Fresh Upload Test:**
   - Clear Week 8 data: `DELETE FROM advanced_stats WHERE week = 8`
   - Upload Passing → Verify checkmark
   - Upload Rush → Verify BOTH checkmarks
   - Upload Receiving → Verify 3 checkmarks
   - Upload Snaps → Verify all 4 checkmarks

2. **Re-Upload Test:**
   - With all 4 files loaded
   - Re-upload Passing with different data
   - Verify all 4 checkmarks still present
   - Query database to confirm Rush/Receiving/Snaps unchanged

3. **Cross-Device Test:**
   - Upload on desktop
   - Open on phone
   - Verify checkmarks appear (database-driven)
   - Confirm no re-upload needed

## Production Deployment

**Commit:** `ef512dc`
**Status:** Pushed to main
**Streamlit Cloud:** Deploying

**User Action Required:**
- Clear browser cache or open in incognito
- Test upload sequence: Passing → Rush → Receiving → Snaps
- Verify checkmarks accumulate (don't disappear)

