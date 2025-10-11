#!/usr/bin/env python3
"""
Test the updated MySportsFeeds client with injury_history endpoint.
"""

import os
from dotenv import load_dotenv
from src.api.mysportsfeeds_api import MySportsFeedsClient

# Load environment variables
load_dotenv()

def main():
    print("=" * 70)
    print("Testing Updated MySportsFeeds Client")
    print("=" * 70)
    print()
    
    api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
    if not api_key:
        print("❌ ERROR: MYSPORTSFEEDS_API_KEY not found")
        return
    
    print(f"✓ API Key found: {api_key[:10]}...{api_key[-4:]}")
    print()
    
    # Initialize client
    print("Initializing MySportsFeeds client...")
    client = MySportsFeedsClient(api_key=api_key)
    print("✓ Client initialized")
    print()
    
    # Fetch injuries (will use injury_history endpoint now)
    print("Fetching injuries from injury_history endpoint...")
    print("-" * 70)
    
    try:
        injuries = client.fetch_injuries(
            season=2025,
            week=6,
            use_cache=False  # Force fresh API call
        )
        
        print(f"✅ SUCCESS! Fetched {len(injuries)} injury reports")
        print()
        
        if injuries:
            print("Sample injury reports (first 10):")
            print("-" * 70)
            for i, injury in enumerate(injuries[:10], 1):
                print(f"{i}. {injury['player_name']} ({injury['team']}) - {injury.get('position', 'N/A')}")
                print(f"   Status: {injury['injury_status']}")
                print(f"   Body Part: {injury['body_part']}")
                print()
            
            # Count by status
            status_counts = {}
            for injury in injuries:
                status = injury['injury_status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            print()
            print("Injury Status Summary:")
            print("-" * 70)
            for status, count in sorted(status_counts.items()):
                print(f"  {status}: {count}")
        else:
            print("⚠️  No injuries returned")
        
        client.close()
        print()
        print("=" * 70)
        print("✅ Test completed successfully!")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

