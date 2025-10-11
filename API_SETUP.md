# API Setup Guide - DFS Optimizer

## Required API Keys

The DFS Optimizer uses external APIs to fetch real-time contextual data. You'll need API keys for the following services:

### 1. The Odds API (Vegas Lines & Game Totals)

**Purpose:** Fetch NFL point spreads, game totals, and calculate Implied Team Totals (ITT)

**Get Your API Key:**
1. Visit https://the-odds-api.com
2. Sign up for a free account
3. Get your API key from the dashboard
4. Free tier includes: 500 requests/month

**Add to .env file:**
```
ODDS_API_KEY=your_api_key_here
```

### 2. MySportsFeeds API (Injury Reports)

**Purpose:** Fetch NFL injury reports and practice status

**Get Your API Key:**
1. Visit https://www.mysportsfeeds.com
2. Sign up for an account
3. Get your API key from the dashboard
4. **IMPORTANT:** Your subscription must include the "DETAILED" addon to access injury data
5. Free tier may have limited requests per day

**Subscription Requirements:**
- The injuries endpoint requires the **DETAILED addon** to be active on your account
- Without this addon, you'll receive a 403 Forbidden error
- Check your subscription at: https://www.mysportsfeeds.com/account/

**Add to .env file:**
```
MYSPORTSFEEDS_API_KEY=your_api_key_here
```

**Note:** The injuries endpoint returns CURRENT injuries only (not historical data by week)

## Environment Variables Setup

### Create a .env file

In the `/DFS` directory, create a file named `.env` with the following content:

```bash
# The Odds API - for Vegas lines and game totals
ODDS_API_KEY=your_odds_api_key_here

# MySportsFeeds API - for injury reports
MYSPORTSFEEDS_API_KEY=your_mysportsfeeds_api_key_here

# Database configuration (optional)
DB_PATH=sqlite:///./DFS.db
```

### Security Note

**NEVER commit your .env file to version control!**

The `.env` file is already added to `.gitignore` to prevent accidental commits.

## Rate Limiting

The UI includes built-in rate limiting to protect your API quotas:

- **Vegas Lines:** 15-minute cooldown between refreshes
- **Injury Reports:** 15-minute cooldown between refreshes

You can always load cached data from the database without consuming API calls.

## Testing Without API Keys

If you don't have API keys yet, you can still:

1. Use the **"Load Cached Data"** button to view previously fetched data
2. Run the backend tests (they use mock data)
3. Build lineups with uploaded player CSV files (Phase 1 features)

The Narrative Intelligence features will show a warning if API keys are missing.

