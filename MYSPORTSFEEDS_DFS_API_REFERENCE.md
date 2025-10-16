# MySportsFeeds DFS API Reference

**Last Updated:** October 16, 2025  
**API Version:** v2.1  
**Addon Required:** DFS

---

## Overview

MySportsFeeds provides two DFS endpoints:
1. **Daily DFS** - By specific date (YYYYMMDD)
2. **Weekly DFS** - By NFL week number (1-18) ← **WE USE THIS**

---

## Weekly DFS Endpoint (CURRENT IMPLEMENTATION)

### URL Format
```
https://api.mysportsfeeds.com/v2.1/pull/nfl/{season}/week/{week}/dfs.{format}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `{season}` | string | Yes | Season format: `{start_year}-{end_year}-{type}`<br>Examples: `2025-2026-regular`, `2025-playoff`, `current`, `latest`, `upcoming` |
| `{week}` | integer | Yes | NFL week number (1-18 for regular season) |
| `{format}` | string | Yes | Response format: `json`, `csv`, or `xml` |

### Optional Query Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `team` | Filter by team(s) | `team=dal,phi` |
| `player` | Filter by player(s) | `player=dak-prescott` |
| `position` | Filter by position(s) | `position=qb,wr` |
| `country` | Filter by country | `country=usa` |
| `dfstype` | **Filter by DFS site** | `dfstype=draftkings` or `dfstype=fanduel` |
| `sort` | Sort results | `sort=dfs.salary.D` (descending by salary) |
| `offset` | Starting offset | `offset=0` |
| `limit` | Max results | `limit=100` |
| `force` | Force fresh data | `force=true` (default) |

### DFS Type Values
- `draftkings` ← **WE USE THIS**
- `fanduel`
- (other DFS sites as supported)

### Sort Options
- `player.lastname`
- `player.age`
- `player.birthplace`
- `player.birthdate`
- `player.height`
- `player.weight`
- `player.position`
- `player.injury`
- `player.team`
- `player.number`
- `dfs.salary`
- `dfs.points` (projections)

**Note:** Weekly endpoint returns ALL slates for the entire week (Main, Showdown, Turbo, Late Swap, etc.).

---

## Daily DFS Endpoint (ALTERNATIVE)

### URL Format
```
https://api.mysportsfeeds.com/v2.1/pull/nfl/{season}/date/{date}/dfs.{format}
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `{season}` | string | Yes | Season format: `{start_year}-{end_year}-{type}` |
| `{date}` | string | Yes | Date in YYYYMMDD format (e.g., `20251016`) |
| `{format}` | string | Yes | Response format: `json`, `csv`, or `xml` |

**Note:** Daily endpoint is useful for specific game dates but Weekly endpoint is preferred for weekly DFS contests.

---

## Season Format Details

### Standard Format
```
{start_year}-{end_year}-{season_type}
```

**Examples:**
- `2025-2026-regular` - 2025-2026 regular season
- `2025-playoff` - 2025 playoffs
- `2024-2025-regular` - 2024-2025 regular season

### Special Keywords
- `current` - Current in-progress season (returns 400 if offseason)
- `latest` - Most recent season (whether in progress or not)
- `upcoming` - Next season (only if schedule is available but season hasn't started)

**Important:** For the 2025-2026 NFL season (Sept 2025 - Feb 2026), use `2025-2026-regular`.

---

## Response Structure

### DFS Response Format
```json
{
  "sources": [
    {
      "source": "DraftKings",
      "slates": [
        {
          "label": "Sunday Main",
          "type": "Classic",
          "forWeek": 7,
          "players": [
            {
              "sourceFirstName": "Patrick",
              "sourceLastName": "Mahomes",
              "sourcePosition": "QB",
              "sourceTeam": "KC",
              "salary": 7800,
              "fantasyPoints": 22.4,
              "player": {
                "id": 12345
              },
              "game": {
                "awayTeamAbbreviation": "SF",
                "homeTeamAbbreviation": "KC"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

### Key Response Fields

| Field Path | Type | Description |
|------------|------|-------------|
| `sources[].source` | string | DFS site name (e.g., "DraftKings") |
| `sources[].slates[]` | array | Multiple slates (Main, Showdown, Turbo, etc.) |
| `slates[].label` | string | Slate name (e.g., "Sunday Main") |
| `slates[].type` | string | Slate type (e.g., "Classic", "Showdown") |
| `slates[].forWeek` | integer | NFL week number |
| `slates[].players[]` | array | All players in the slate |
| `players[].sourceFirstName` | string | Player first name |
| `players[].sourceLastName` | string | Player last name |
| `players[].sourcePosition` | string | Position (QB, RB, WR, TE, DST) |
| `players[].sourceTeam` | string | Team abbreviation |
| `players[].salary` | integer | DFS salary |
| `players[].fantasyPoints` | float | Projected fantasy points (may be null) |
| `players[].player.id` | integer | MySportsFeeds player ID (null for DST) |
| `players[].game.awayTeamAbbreviation` | string | Away team |
| `players[].game.homeTeamAbbreviation` | string | Home team |

---

## Authentication

### HTTP Basic Auth
```
Username: {YOUR_API_KEY}
Password: MYSPORTSFEEDS
```

### Example (Python requests)
```python
from requests.auth import HTTPBasicAuth

auth = HTTPBasicAuth(api_key, "MYSPORTSFEEDS")
response = requests.get(url, auth=auth, params=params)
```

---

## Current Implementation (DFS Lineup Optimizer)

### What We Use
- **Endpoint:** Weekly DFS (`/week/{week}/dfs.json`)
- **Season:** `2025-2026-regular`
- **Format:** JSON
- **Filter:** `dfstype=draftkings`
- **Week:** User-selected (default: 7)

### Example API Call
```
GET https://api.mysportsfeeds.com/v2.1/pull/nfl/2025-2026-regular/week/7/dfs.json?dfstype=draftkings
Authorization: Basic {base64(api_key:MYSPORTSFEEDS)}
```

### Response Processing
1. Extract `sources[0].slates[]` array (all slates for the week)
2. Identify largest slate (most players) = Main Sunday slate
3. Filter to players with `projection > 0`
4. Remove duplicate players (same player in multiple slates)
5. Parse opponent from `game.awayTeamAbbreviation` and `game.homeTeamAbbreviation`
6. Handle DST players (player.id = null)

---

## Known Issues & Solutions

### Issue 1: DST Players Have No ID
**Problem:** `player.id` is `null` for defense/special teams  
**Solution:** Use `{player_name}_{team}` as unique identifier (e.g., `Chiefs_KC`)

### Issue 2: Multiple Slates Per Week
**Problem:** API returns 30+ slates (Main, Showdown, Turbo, Late, etc.)  
**Solution:** Filter to largest slate (by player count) = Main Sunday slate

### Issue 3: Opponent Field May Be Missing
**Problem:** Some players don't have `game` data  
**Solution:** Make `opponent` column nullable in database

### Issue 4: Projection May Be Null
**Problem:** `fantasyPoints` can be `null` for some players  
**Solution:** Default to `0.0` if null, filter out players with projection = 0

---

## Rate Limits & Throttling

- **Force Parameter:** Set `force=true` (default) for fresh data
- **Force=false:** Avoids throttling but may return cached/stale data
- **304 Response:** No new data since last request (use `force=true` to override)

---

## Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 200 | Success | Data returned successfully |
| 304 | Not Modified | Use `force=true` to get fresh data |
| 400 | Bad Request | Check season format, week number, or date |
| 401 | Unauthorized | Verify API key is correct |
| 403 | Forbidden | Verify DFS addon is active in subscription |
| 404 | Not Found | Season/week/date doesn't exist |
| 429 | Rate Limited | Wait and retry with exponential backoff |
| 500 | Server Error | MySportsFeeds API issue, retry later |

---

## Testing & Validation

### Test Current Week
```bash
curl -X GET \
  'https://api.mysportsfeeds.com/v2.1/pull/nfl/2025-2026-regular/week/7/dfs.json?dfstype=draftkings' \
  -u '{YOUR_API_KEY}:MYSPORTSFEEDS'
```

### Test Specific Date (Daily)
```bash
curl -X GET \
  'https://api.mysportsfeeds.com/v2.1/pull/nfl/2025-2026-regular/date/20251016/dfs.json?dfstype=draftkings' \
  -u '{YOUR_API_KEY}:MYSPORTSFEEDS'
```

### Verify Response
- Check `sources` array is not empty
- Check `slates` array has multiple entries
- Check `players` array in each slate
- Verify salary and projection fields

---

## Additional Resources

- **MySportsFeeds API Docs:** https://www.mysportsfeeds.com/data-feeds/api-docs/
- **DFS Addon Page:** https://www.mysportsfeeds.com/pricing/
- **API Support:** support@mysportsfeeds.com
- **Subscription Management:** https://www.mysportsfeeds.com/my-account/

---

## Changelog

**2025-10-16:**
- Initial documentation created
- Confirmed season format: `2025-2026-regular`
- Confirmed endpoint: `/week/{week}/dfs.json`
- Documented response structure and filtering logic

