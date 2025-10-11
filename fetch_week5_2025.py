#!/usr/bin/env python3
"""
Fetch Week 5 Data from 2025-2026 Season

Uses MySportsFeeds API to fetch current season Week 5 boxscores.
This data will be used for the 80/20 regression rule analysis.

Usage:
    python3 fetch_week5_2025.py
"""

import os
import sys
from dotenv import load_dotenv
from src.api.boxscore_api import BoxscoreAPIClient

# Load environment variables
load_dotenv()


def main():
    print("=" * 70)
    print("📊 Fetch Week 5 Data - 2025-2026 Season")
    print("=" * 70)
    print()
    
    # Check API key
    api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
    if not api_key:
        print("❌ ERROR: MYSPORTSFEEDS_API_KEY not found")
        print()
        print("Please set your MySportsFeeds API key:")
        print()
        print("Option 1 - Environment Variable:")
        print("  export MYSPORTSFEEDS_API_KEY='your_api_key_here'")
        print()
        print("Option 2 - Create .env file in DFS/ directory:")
        print("  echo 'MYSPORTSFEEDS_API_KEY=your_api_key_here' > .env")
        print()
        print("Get your API key from: https://www.mysportsfeeds.com/")
        sys.exit(1)
    
    print(f"✓ API Key found: {api_key[:10]}...{api_key[-4:]}")
    print()
    
    # Initialize client
    print("Initializing MySportsFeeds API client...")
    client = BoxscoreAPIClient(api_key=api_key)
    print("✓ Client initialized")
    print()
    
    # Fetch Week 5 data from 2025 season
    season = "2025-regular"
    week = 5
    
    try:
        print(f"📥 Fetching Week {week} games for {season} season")
        print("-" * 70)
        print()
        
        print("Step 1: Getting game schedule...")
        games = client.fetch_weekly_schedule(season, week)
        
        if not games:
            print("❌ No games found for this week")
            print()
            print("This could mean:")
            print("  - Week 5 hasn't been played yet")
            print("  - Your API subscription doesn't include current season data")
            print("  - The season format is incorrect")
            sys.exit(1)
        
        print(f"✓ Found {len(games)} games")
        for game in games:
            print(f"  - {game}")
        print()
        
        print(f"Step 2: Fetching boxscores... (this may take a few minutes)")
        print("-" * 70)
        
        boxscores = client.fetch_week_boxscores(season, week)
        
        if not boxscores:
            print("❌ Failed to fetch any boxscores")
            print()
            print("This could mean:")
            print("  - API rate limit reached")
            print("  - DETAILED addon not active on your subscription")
            print("  - Network error")
            sys.exit(1)
        
        # Store all boxscores in database
        print()
        print("💾 Storing all games in database...")
        print("-" * 70)
        
        stored_count = 0
        for i, boxscore in enumerate(boxscores, 1):
            print(f"Storing {i}/{len(boxscores)}: {boxscore['away_team']} @ {boxscore['home_team']}...", end=" ")
            if client.store_boxscore(boxscore):
                print("✅")
                stored_count += 1
            else:
                print("❌")
        
        print()
        print("=" * 70)
        print("✅ SUCCESS! Week 5 (2025 season) data fetched and stored")
        print("=" * 70)
        print()
        print(f"Stored {stored_count}/{len(boxscores)} games in database")
        
        # Summary
        total_players = sum(len(b['player_stats']) for b in boxscores)
        print(f"Total player stats: {total_players}")
        print()
        
        print("Games Summary:")
        print("-" * 70)
        for boxscore in boxscores:
            away = boxscore['away_team']
            home = boxscore['home_team']
            away_score = boxscore['away_score']
            home_score = boxscore['home_score']
            
            print(f"{away:4} {away_score:2} @ {home:4} {home_score:2}  ({len(boxscore['player_stats'])} players)")
        
        print()
        print("📊 Fresh data is ready for 80/20 regression analysis!")
        print()
        print("Next steps:")
        print("  1. Restart your Streamlit app")
        print("  2. Load your player data")
        print("  3. Check the 'Reg' column for regression warnings")
        
        client.close()
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

