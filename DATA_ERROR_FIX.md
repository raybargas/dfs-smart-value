# Data Error Fix: KeyError 'opp_rz_targets' - October 17, 2025

## Problem

Application crashed when loading player pool with error:
```
KeyError: 'opp_rz_targets'
File "/Users/raybargas/Desktop/Gauntlet_Flow/DFS/ui/player_selection.py", line 721
```

## Root Cause

**Key Name Mismatch** in sub_weights configuration:

### Two different key names used:
1. `profile_manager.py` DEFAULT_SUB_WEIGHTS used: `'opp_redzone'`
2. `smart_value_calculator.py` expected: `'opp_rz_targets'`
3. `profiles.json` had: `'opp_redzone'`

### Why this caused the error:

When the player selection UI tried to access the slider value:
```python
st.slider(..., st.session_state['smart_value_sub_weights']['opp_redzone'], ...)
```

But if cached session state or profile data used the other key name, it would fail.

The mismatch between profile data and calculator expectations caused inconsistent behavior depending on which data source was loaded first.

## Solution

**Standardized on `'opp_rz_targets'`** across all files:

### Files Modified:

1. **`src/profile_manager.py`** (line 33)
   - Changed: `'opp_redzone': 0.20` 
   - To: `'opp_rz_targets': 0.20`

2. **`ui/player_selection.py`** (line 774)
   - Added backward compatibility: 
   ```python
   st.session_state['smart_value_sub_weights'].get(
       'opp_rz_targets', 
       st.session_state['smart_value_sub_weights'].get('opp_redzone', 0.20)
   )
   ```

3. **`ui/player_selection.py`** (line 832)
   - Changed: `'opp_redzone': opp_rz / opp_total ...`
   - To: `'opp_rz_targets': opp_rz / opp_total ...`

4. **`profiles.json`** (all 6 profiles)
   - Changed all instances of `'opp_redzone'` to `'opp_rz_targets'`

## Why 'opp_rz_targets' was chosen:

1. **Consistency with `smart_value_calculator.py`**: This is the core calculation module and should be the source of truth
2. **Matches other occurrences**: `results.py` already used `'opp_rz_targets'`
3. **More descriptive**: "RZ Targets" (red zone targets) is clearer than "redzone"

## Expected Impact

- ✅ **Fixes KeyError**: No more crashes when loading player pool
- ✅ **Maintains backward compatibility**: Code checks for both key names
- ✅ **Consistent naming**: All files now use the same key
- ✅ **No data loss**: Existing profiles updated to new key name

## Testing

After fix:
1. Clear browser cache / Streamlit session state
2. Restart Streamlit app
3. Load Week 7 data
4. Navigate to Player Selection
5. Verify: Player pool loads without error
6. Verify: Smart Value sliders work correctly
7. Verify: Profiles load without error

## Files Modified

- `DFS/src/profile_manager.py` - Changed DEFAULT_SUB_WEIGHTS key name
- `DFS/ui/player_selection.py` - Changed key name in 2 places, added backward compatibility
- `DFS/profiles.json` - Updated all 6 profiles with new key name

## Commit Message

```
Fix: Standardize sub_weights key name to 'opp_rz_targets'

Problem:
- KeyError when loading player pool
- Inconsistent key names: 'opp_redzone' vs 'opp_rz_targets'
- profile_manager.py, profiles.json used 'opp_redzone'
- smart_value_calculator.py expected 'opp_rz_targets'

Solution:
- Standardized on 'opp_rz_targets' across all files
- Added backward compatibility in player_selection.py
- Updated all profiles with correct key name

Impact:
- Fixes KeyError crash
- Ensures consistent sub_weights handling
- Maintains backward compatibility with cached data
```

