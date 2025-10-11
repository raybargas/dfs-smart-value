#!/usr/bin/env python3
"""
Test script for MySportsFeeds Injury History API endpoint.
This endpoint accepts season and date parameters (unlike the injuries endpoint).

Usage:
    python3 test_injury_history.py
"""

import os
import sys
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

def test_injury_history(season="current", date=None):
    """Test MySportsFeeds Injury History API endpoint."""
    
    print("=" * 70)
    print("MySportsFeeds Injury History API Test")
    print("=" * 70)
    print()
    
    # Check for API key
    api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
    if not api_key:
        print("❌ ERROR: MYSPORTSFEEDS_API_KEY not found in .env file")
        return False
    
    print(f"✓ API Key found: {api_key[:10]}...{api_key[-4:]}")
    print()
    
    # Test the injury_history endpoint
    print("Testing injury_history endpoint...")
    print("-" * 70)
    
    url = "https://api.mysportsfeeds.com/v2.1/pull/nfl/injury_history.json"
    
    # Build parameters
    params = {
        'force': 'true'  # Force fresh content
    }
    
    # Add season parameter
    if season:
        params['season'] = season
    
    # Add date parameter (defaults to last week if not specified)
    if date:
        params['date'] = date
    else:
        # Try last week's date (7 days ago)
        last_week = datetime.now() - timedelta(days=7)
        params['date'] = last_week.strftime('%Y%m%d')
    
    print(f"URL: {url}")
    print(f"Params: {json.dumps(params, indent=2)}")
    print(f"Auth: HTTP Basic Auth")
    print()
    
    try:
        # Make the request
        print("Sending request...")
        response = requests.get(
            url,
            params=params,
            auth=HTTPBasicAuth(api_key, "MYSPORTSFEEDS"),
            timeout=10
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print()
        
        # Handle different status codes
        if response.status_code == 200:
            print("✅ SUCCESS! Injury history endpoint working.")
            print()
            
            # Parse response
            data = response.json()
            
            # Print full response structure
            print("Response structure:")
            print(json.dumps(data, indent=2)[:2000])  # First 2000 chars
            print()
            
            # Try to extract injury data
            injuries = data.get('injuries', [])
            references = data.get('references', {})
            
            print(f"Total injury records found: {len(injuries)}")
            print()
            
            if injuries:
                print("Sample injury history data (first 5 records):")
                print("-" * 70)
                for i, injury in enumerate(injuries[:5], 1):
                    player = injury.get('player', {})
                    player_id = player.get('id', 'N/A')
                    
                    # Try to get player name from references
                    player_info = references.get('playerReferences', [])
                    player_name = "Unknown"
                    for p in player_info:
                        if str(p.get('id')) == str(player_id):
                            first = p.get('firstName', '')
                            last = p.get('lastName', '')
                            player_name = f"{first} {last}".strip()
                            break
                    
                    status = injury.get('playingProbability', 'UNKNOWN')
                    description = injury.get('description', 'N/A')
                    
                    print(f"{i}. Player ID: {player_id} - {player_name}")
                    print(f"   Status: {status}")
                    print(f"   Description: {description}")
                    print()
            else:
                print("⚠️  No injury history found for the specified date/season")
                print()
                print("Try different parameters:")
                print("  - season='current' or 'latest'")
                print("  - season='2024-2025-regular'")
                print("  - Different date in YYYYMMDD format")
            
            return True
            
        elif response.status_code == 400:
            print("❌ BAD REQUEST (400)")
            print()
            print("Response body:")
            print(response.text)
            print()
            print("Possible causes:")
            print("- Invalid season identifier")
            print("- No data available for specified date/season")
            print("- Season not yet started (if using 'current')")
            print()
            return False
            
        elif response.status_code == 401:
            print("❌ AUTHENTICATION FAILED (401)")
            print()
            print("Check your API key at https://www.mysportsfeeds.com/account/")
            return False
            
        elif response.status_code == 403:
            print("❌ ACCESS FORBIDDEN (403)")
            print()
            print("⚠️  YOUR SUBSCRIPTION DOES NOT INCLUDE THE REQUIRED 'DETAILED' ADDON")
            print()
            print("Visit https://www.mysportsfeeds.com/account/ to upgrade")
            return False
            
        elif response.status_code == 429:
            print("❌ RATE LIMIT EXCEEDED (429)")
            return False
            
        else:
            print(f"❌ ERROR: Unexpected status code {response.status_code}")
            print()
            print("Response body:")
            print(response.text[:1000])
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print()
    print("Testing with different season/date combinations...")
    print()
    
    # Test 1: Current season, last week
    print("\n" + "=" * 70)
    print("TEST 1: Current season, last week's date")
    print("=" * 70)
    test_injury_history(season="current")
    
    # Test 2: Latest season, last week
    print("\n" + "=" * 70)
    print("TEST 2: Latest season, last week's date")
    print("=" * 70)
    test_injury_history(season="latest")
    
    # Test 3: Specific 2024 season
    print("\n" + "=" * 70)
    print("TEST 3: 2024-2025-regular season, last week's date")
    print("=" * 70)
    test_injury_history(season="2024-2025-regular")
    
    print("\n" + "=" * 70)
    print("Tests completed!")
    print("=" * 70)

