# MySportsFeeds DFS API - Test Findings

**Date**: 2025-10-16  
**Tests Run**: 15+ endpoint variations

---

## ✅ **WORKING ENDPOINT**

### **URL Format**
```
https://api.mysportsfeeds.com/v2.1/pull/nfl/{year}-regular/week/{week}/dfs.json
```

### **Example**
```
GET https://api.mysportsfeeds.com/v2.1/pull/nfl/2024-regular/week/6/dfs.json?dfstype=draftkings
```

### **Parameters**
- `dfstype`: Filter by DFS site (`draftkings`, `fanduel`, etc.)

### **Authentication**
- HTTP Basic Auth
- Username: API Key
- Password: `"MYSPORTSFEEDS"`

---

## ❌ **WHAT DOESN'T WORK**

| Endpoint Format | Status | Note |
|-----------------|--------|------|
| `daily_dfs.json` | 404 | Old endpoint, removed |
| `{year}-{year+1}-regular/week/{week}/dfs.json` | 500 | Wrong year format |
| `current/week/current/dfs.json` | 500 | "current" keyword broken |
| `{year}-regular/week/current/dfs.json` | 500 | "current" week keyword broken |
| `{year}-regular/week/{future_week}/dfs.json` | Timeout | Data not available yet |

---

## 📊 **RESPONSE STRUCTURE**

### **JSON Path to Players**
```
response['sources'][0]['slates'][i]['players']
```

### **Response Hierarchy**
```json
{
  "lastUpdatedOn": "2025-10-16T16:06:08.134Z",
  "sources": [
    {
      "source": "DraftKings",
      "slates": [
        {
          "forDate": "2024-10-09T04:00:00.000Z",
          "forWeek": 6,
          "identifier": 114773,
          "label": "Featured",
          "type": "Classic",
          "minGameStart": "2024-10-13T17:00:00.000Z",
          "games": [ ... ],
          "contests": [ ... ],
          "players": [ ... ]  ← PLAYER DATA HERE
        }
      ]
    }
  ],
  "references": { ... }
}
```

### **Player Object Structure**
```json
{
  "sourceId": "332/12345",
  "sourceFirstName": "Patrick",
  "sourceLastName": "Mahomes",
  "sourceTeam": "KC",
  "sourcePosition": "QB",
  "rosterSlots": ["QB"],
  "salary": 8000,
  "fantasyPoints": 24.5,  // Can be null
  "team": {
    "id": 51,
    "abbreviation": "KC"
  },
  "player": {
    "id": 12345,
    "firstName": "Patrick",
    "lastName": "Mahomes",
    "position": "QB",
    "jerseyNumber": 15
  },
  "game": {
    "id": 134401,
    "week": 6,
    "startTime": "2024-10-13T20:25:00.000Z",
    "awayTeamAbbreviation": "KC",
    "homeTeamAbbreviation": "BUF"
  }
}
```

### **Key Fields for Our Use**
- `sourceFirstName` + `sourceLastName` → Player name
- `sourcePosition` → Position (QB, RB, WR, TE, DST)
- `sourceTeam` or `team.abbreviation` → Team
- `salary` → DFS salary
- `fantasyPoints` → Projected points (can be null)
- `player.id` → MySportsFeeds player ID
- `game` → Game info for opponent lookup

---

## 🔧 **REQUIRED CODE CHANGES**

### **1. Fix Endpoint Format**
**OLD** ❌:
```python
endpoint = f"{season}/week/{week}/dfs.json"  # "2024-2025-regular/week/6/dfs.json"
```

**NEW** ✅:
```python
# Extract year from season (e.g., "2024-2025-regular" → "2024")
year = season.split('-')[0]
endpoint = f"{year}-regular/week/{week}/dfs.json"  # "2024-regular/week/6/dfs.json"
```

### **2. Fix Response Parsing**
**OLD** ❌:
```python
# Looking for wrong keys
if 'dfsSlates' in data:
    ...
```

**NEW** ✅:
```python
# Correct path to player data
if 'sources' in data:
    for source in data['sources']:
        if 'slates' in source:
            for slate in source['slates']:
                if 'players' in slate:
                    for player in slate['players']:
                        # Parse player data
                        name = f"{player.get('sourceFirstName', '')} {player.get('sourceLastName', '')}".strip()
                        position = player.get('sourcePosition')
                        team = player.get('sourceTeam') or player.get('team', {}).get('abbreviation')
                        salary = player.get('salary')
                        projection = player.get('fantasyPoints')  # Can be null
                        ...
```

### **3. Handle "Current" Week**
Since `"current"` keyword doesn't work, we need to:
1. Use specific year + week numbers
2. OR implement logic to determine current week

**Recommendation**: For `fetch_current_week_salaries()`, add a `week` parameter and require user to specify it.

---

## 📝 **IMPLEMENTATION CHECKLIST**

- [ ] Update `fetch_current_week_salaries()` endpoint format
- [ ] Update `fetch_historical_salaries()` endpoint format  
- [ ] Fix year format: `"2024-2025-regular"` → `"2024-regular"`
- [ ] Update `_parse_dfs_response()` to use correct JSON path
- [ ] Update `_parse_dfs_response()` to handle new field names
- [ ] Handle `fantasyPoints` being null (use 0.0 as default)
- [ ] Add `dfstype` query parameter
- [ ] Update unit tests to match new structure
- [ ] Test with live API

---

## 📊 **TEST RESULTS SUMMARY**

- ✅ **Week 6 DraftKings**: 490 players, 33 slates
- ❌ **Week 7**: Timeout (data not available yet)
- ❌ **"current" keywords**: 500 errors (MySportsFeeds issue)
- ✅ **Data structure**: Fully mapped
- ✅ **Authentication**: Working correctly
- ✅ **Query params**: `dfstype=draftkings` works

---

## 🚀 **NEXT STEPS**

1. Update `src/api/dfs_salaries_api.py` with correct endpoint format
2. Update `_parse_dfs_response()` method with correct JSON parsing
3. Add unit tests for new response structure
4. Test with live API
5. Update Streamlit UI code if needed
6. Push to GitHub
7. Test in deployed Streamlit app

---

## 📁 **TEST FILES CREATED**

- `test_mysportsfeeds_dfs_endpoint.py` - Initial endpoint tests
- `test_mysportsfeeds_dfs_endpoint2.py` - Additional format tests
- `test_mysportsfeeds_dfs_final.py` - Confirmation tests
- `test_mysportsfeeds_structure.py` - Response structure inspection
- `dfs_response_sample.json` - Full API response sample

---

**Status**: Ready to implement fixes ✅

