#!/usr/bin/env python3
"""
Fetch Last Week's Game Data

Quick script to fetch and store last week's NFL game boxscores.
80/20 rule: Start with the most recent, valuable data first.

Usage:
    python3 fetch_last_week.py [--week 5] [--season 2024-2025-regular]
"""

import os
import sys
import argparse
from dotenv import load_dotenv
from src.api.boxscore_api import BoxscoreAPIClient

# Load environment variables
load_dotenv()


def main():
    parser = argparse.ArgumentParser(description='Fetch last week\'s NFL game data')
    parser.add_argument('--week', type=int, default=5, help='Week number to fetch (default: 5)')
    parser.add_argument('--season', default='2024-regular', help='Season (default: 2024-regular)')
    parser.add_argument('--game', type=str, help='Fetch single game by ID (e.g., 20241006-BAL-CIN)')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("📊 Fetch Last Week's Game Data")
    print("=" * 70)
    print()
    
    # Check API key
    api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
    if not api_key:
        print("❌ ERROR: MYSPORTSFEEDS_API_KEY not found in .env file")
        print()
        print("Please add your MySportsFeeds API key to the .env file:")
        print("MYSPORTSFEEDS_API_KEY=your_api_key_here")
        sys.exit(1)
    
    print(f"✓ API Key found: {api_key[:10]}...{api_key[-4:]}")
    print()
    
    # Initialize client
    print("Initializing BoxscoreAPI client...")
    client = BoxscoreAPIClient(api_key=api_key)
    print("✓ Client initialized")
    print()
    
    try:
        if args.game:
            # Fetch single game
            print(f"📥 Fetching single game: {args.game}")
            print("-" * 70)
            
            boxscore = client.fetch_boxscore(args.game, args.season)
            
            print(f"✅ Game: {boxscore['away_team']} @ {boxscore['home_team']}")
            print(f"   Score: {boxscore['away_score']} - {boxscore['home_score']}")
            print(f"   Players: {len(boxscore['player_stats'])} players recorded stats")
            print()
            
            # Store in database
            print("💾 Storing in database...")
            if client.store_boxscore(boxscore):
                print("✅ Data stored successfully!")
            else:
                print("❌ Failed to store data")
            print()
            
            # Show top performers
            print("Top Performers:")
            print("-" * 70)
            
            # Sort by total yards
            players_with_yards = [
                p for p in boxscore['player_stats']
                if p['pass_yards'] > 0 or p['rush_yards'] > 0 or p['receiving_yards'] > 0
            ]
            
            for player in sorted(
                players_with_yards,
                key=lambda p: p['pass_yards'] + p['rush_yards'] + p['receiving_yards'],
                reverse=True
            )[:10]:
                total_yards = player['pass_yards'] + player['rush_yards'] + player['receiving_yards']
                total_tds = player['pass_touchdowns'] + player['rush_touchdowns'] + player['receiving_touchdowns']
                
                print(f"{player['player_name']:25} ({player['team']}, {player['position']})")
                if player['pass_yards'] > 0:
                    print(f"  Passing: {player['pass_completions']}/{player['pass_attempts']}, {player['pass_yards']} yds, {player['pass_touchdowns']} TD")
                if player['rush_yards'] > 0:
                    print(f"  Rushing: {player['rush_attempts']} att, {player['rush_yards']} yds, {player['rush_touchdowns']} TD")
                if player['receiving_yards'] > 0:
                    print(f"  Receiving: {player['receptions']}/{player['targets']}, {player['receiving_yards']} yds, {player['receiving_touchdowns']} TD")
            
        else:
            # Fetch full week
            print(f"📥 Fetching all games for {args.season} Week {args.week}")
            print("-" * 70)
            print()
            
            print("Step 1: Getting game schedule...")
            games = client.fetch_weekly_schedule(args.season, args.week)
            
            if not games:
                print("❌ No games found for this week")
                sys.exit(1)
            
            print(f"✓ Found {len(games)} games")
            for game in games:
                print(f"  - {game}")
            print()
            
            print(f"Step 2: Fetching boxscores... (this may take a few minutes)")
            print("-" * 70)
            
            boxscores = client.fetch_week_boxscores(args.season, args.week)
            
            if not boxscores:
                print("❌ Failed to fetch any boxscores")
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
            print("✅ SUCCESS! Data fetched and stored")
            print("=" * 70)
            print()
            print(f"Stored {stored_count}/{len(boxscores)} games in database")
            
            # Summary
            print(f"Games fetched: {len(boxscores)}")
            print()
            
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
            print("📊 Data is ready to use for player analysis!")
            print()
            print("Next steps:")
            print("  1. Run the migration to create database tables")
            print("  2. Use this data to enrich your uploaded player CSV")
            print("  3. Analyze trends: targets, snap counts, game scripts")
        
        client.close()
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

