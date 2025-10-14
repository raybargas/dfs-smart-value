"""
Test script to directly call MySportsFeeds API and check for Kyler Murray.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.api.mysportsfeeds_api import MySportsFeedsClient

def test_kyler_murray():
    """Test if Kyler Murray is in MySportsFeeds injury data."""
    
    # Load .env file
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get API key from environment
    api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
    
    if not api_key:
        print("❌ MYSPORTSFEEDS_API_KEY not found in environment")
        return
    
    print(f"✅ API Key found: {api_key[:10]}...")
    print("\n" + "="*80)
    print("TESTING MYSPORTSFEEDS API CALL")
    print("="*80 + "\n")
    
    # Create client
    client = MySportsFeedsClient(api_key=api_key, db_path="dfs_optimizer.db")
    
    try:
        # Fetch current injuries
        print("📡 Calling MySportsFeeds API (injuries.json)...")
        injuries = client.fetch_injuries(
            season=2025,
            week=6,
            use_cache=False,
            cache_ttl_hours=6
        )
        
        print(f"✅ API call successful! Received {len(injuries)} injury reports\n")
        
        # Search for Kyler Murray
        kyler = None
        for injury in injuries:
            if 'murray' in injury['player_name'].lower() and 'kyler' in injury['player_name'].lower():
                kyler = injury
                break
        
        print("="*80)
        print("SEARCHING FOR KYLER MURRAY")
        print("="*80 + "\n")
        
        if kyler:
            print("✅ FOUND KYLER MURRAY!")
            print(f"\nPlayer: {kyler['player_name']}")
            print(f"Team: {kyler['team']}")
            print(f"Position: {kyler.get('position', 'N/A')}")
            print(f"Status: {kyler['injury_status']}")
            print(f"Body Part: {kyler['body_part']}")
            print(f"Description: {kyler['injury_description']}")
            print(f"Last Update: {kyler['last_update']}")
        else:
            print("❌ KYLER MURRAY NOT FOUND IN API RESPONSE")
            print("\n📋 Checking Arizona Cardinals players in response:\n")
            
            ari_players = [
                inj for inj in injuries 
                if inj['team'] == 'ARI'
            ]
            
            if ari_players:
                print(f"Found {len(ari_players)} Arizona Cardinals injuries:")
                for inj in sorted(ari_players, key=lambda x: x['player_name']):
                    print(f"  • {inj['player_name']} ({inj.get('position', '?')}) - {inj['injury_status']}")
            else:
                print("No Arizona Cardinals injuries found")
            
            # Check all QBs
            print("\n📋 All QB injuries in response:\n")
            qb_injuries = [
                inj for inj in injuries 
                if inj.get('position', '') == 'QB'
            ]
            
            if qb_injuries:
                print(f"Found {len(qb_injuries)} QB injuries:")
                for inj in sorted(qb_injuries, key=lambda x: x['player_name']):
                    print(f"  • {inj['player_name']} ({inj['team']}) - {inj['injury_status']} ({inj['body_part']})")
            else:
                print("No QB injuries found")
        
        client.close()
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_kyler_murray()

