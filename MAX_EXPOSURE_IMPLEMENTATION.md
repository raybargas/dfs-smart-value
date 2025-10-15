# Max Player Exposure Implementation

## Overview

The Max Player Exposure feature limits how many lineups any single player can appear in, preventing concentration risk where one bust ruins most of your entries.

## Problem Statement

**Uniqueness ≠ Exposure Control**

The uniqueness constraint only ensures that each *pair* of lineups differs by a certain percentage. It does not limit how often a *single player* appears across all lineups.

### Example Problem:
- 10 lineups with 65% uniqueness (max 3 shared players per pair)
- Javonte Williams appears in 8/10 lineups (80% exposure)
- Each lineup pair is valid (shares ≤3 players)
- But one bust (Javonte) ruins 80% of entries

## Solution: Max Exposure Constraint

A new constraint that explicitly limits how many lineups any single player can appear in, providing direct control over concentration risk.

### UI Control
- **Location**: Optimization Configuration page
- **Control**: Slider (20-100%)
- **Default**: 40% (recommended for tournaments)
- **Tooltip**: "Limits how many lineups any single player can appear in. Lower values reduce concentration risk."

### Example:
- 10 lineups × 40% max exposure = 4 lineups maximum per player
- Javonte Williams would be limited to 4 lineups instead of 8

## Implementation Details

### 1. Optimizer Logic (`optimizer.py`)

**Exposure Tracking:**
```python
# Track player exposure across all lineups
player_exposure_count = {}

# Calculate max lineups per player from exposure percentage
max_lineups_per_player = int(lineup_count * max_exposure_pct)
```

**Constraint Application:**
```python
# Constraint 5b: Max Exposure (limit how many lineups a player can appear in)
if player_exposure_count is not None and max_lineups_per_player is not None:
    for player in players:
        current_exposure = player_exposure_count.get(player.name, 0)
        # If player has reached max exposure, exclude them from this lineup
        if current_exposure >= max_lineups_per_player:
            prob += player_vars[player.name] == 0, f"MaxExposure_{player.name.replace(' ', '_')}"
```

**Post-Lineup Update:**
```python
# Update player exposure counts after each lineup
for player in lineup.players:
    player_exposure_count[player.name] = player_exposure_count.get(player.name, 0) + 1
```

### 2. UI Components

**Optimization Config (`optimization_config.py`):**
```python
max_exposure_pct = st.slider(
    "Max Player Exposure",
    min_value=20,
    max_value=100,
    value=40,
    step=5,
    format="%d%%",
    help="Limits how many lineups any single player can appear in. Lower values reduce concentration risk.\n\nExample: 40% with 10 lineups = max 4 lineups per player\n\nRecommended: 40% for tournaments (diversification)",
    key="max_exposure_pct"
)
```

**Results Display (`results.py`):**
- Shows top 5 most exposed players
- Displays exposure counts (e.g., "Player Name (4/10)")
- Warns if any player exceeds 70% exposure

### 3. Configuration Flow

1. User selects max exposure % in Optimization Config
2. Setting stored in `st.session_state['optimization_config']`
3. Passed to `generate_lineups()` as `max_exposure_pct` parameter
4. Applied as constraint during lineup generation
5. Exposure analysis displayed in Results page

## Testing Results

### Test Scenarios:

**Test 1: No Exposure Limit (100%)**
```
QB0: 10/10 lineups (100%)  ← Problem scenario
DST0: 10/10 lineups (100%)
WR14: 5/10 lineups (50%)
```

**Test 2: Max Exposure = 40% ✅**
```
QB0: 4/10 lineups (40%)  ← Constraint satisfied
RB0: 4/10 lineups (40%)
WR14: 4/10 lineups (40%)
TE0: 4/10 lineups (40%)
✅ CONSTRAINT SATISFIED: No player exceeds 4 lineups
```

**Test 3: Max Exposure = 20%**
```
Error after 7 lineups: Too restrictive for player pool
(Expected - requires very large player pool)
```

## Benefits

1. **Concentration Risk Management**: Prevents one bust from ruining most entries
2. **Diversification**: Forces optimizer to use more players across lineups
3. **Tournament Viability**: More realistic exposure for GPP tournaments
4. **User Control**: Adjustable per contest type/strategy
5. **Transparent**: Clear exposure analysis in results

## Usage Guidelines

### Recommended Settings:

- **GPP Tournaments (Large Field)**: 30-40%
  - Maximum diversification
  - Reduces single-player risk
  
- **Small Tournaments**: 50-60%
  - Balance between concentration and optimization
  
- **Cash Games**: 60-80%
  - Allow optimizer more freedom
  - Focus on highest-projection players
  
- **No Limit**: 100%
  - Pure optimization without exposure constraints
  - Not recommended for multi-entry tournaments

### Warning Thresholds:

- **> 70% exposure**: High concentration risk
- **> 80% exposure**: Very high risk (like Javonte Williams scenario)
- **100% exposure**: Player appears in every lineup

## Files Modified

1. **`src/optimizer.py`**: Core constraint logic
2. **`ui/optimization_config.py`**: UI slider and config storage
3. **`ui/lineup_generation.py`**: Parameter passing
4. **`ui/results.py`**: Exposure analysis display

## Future Enhancements

1. **Position-Specific Exposure**: Different limits per position
2. **Correlated Exposure**: Limit exposure to player stacks
3. **Dynamic Exposure**: Adjust based on ownership projections
4. **Exposure Optimization**: Target specific exposure distributions

## Dependencies

- No new external dependencies
- Uses existing optimizer constraint system
- Integrates with current UI framework
