"""
Direct test of MySportsFeeds API with raw HTTP request.
Shows exactly what URL is called and what response is returned.
"""

import os
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import json

load_dotenv()

api_key = os.getenv('MYSPORTSFEEDS_API_KEY')

if not api_key:
    print("❌ No API key found")
    exit(1)

# Exact URL and params as per documentation
url = "https://api.mysportsfeeds.com/v2.1/pull/nfl/injuries.json"
params = {
    'force': 'true'
}

print("="*80)
print("DIRECT MYSPORTSFEEDS API TEST")
print("="*80)
print(f"\n📡 Making request to:")
print(f"   URL: {url}")
print(f"   Params: {params}")
print(f"   Auth: API Key (Basic Auth with 'MYSPORTSFEEDS' password)")
print(f"   API Key: {api_key[:15]}...\n")

# Make request with Basic Auth (username=API_KEY, password="MYSPORTSFEEDS")
auth = HTTPBasicAuth(api_key, "MYSPORTSFEEDS")

try:
    response = requests.get(url, params=params, auth=auth, timeout=30)
    
    print(f"✅ Response received:")
    print(f"   Status: {response.status_code}")
    print(f"   Size: {len(response.content)} bytes\n")
    
    if response.status_code == 200:
        data = response.json()
        
        # Show structure
        print("📦 Response structure:")
        print(f"   Keys: {list(data.keys())}\n")
        
        # Get players array
        players = data.get('players', [])
        print(f"✅ Total players in response: {len(players)}\n")
        
        # Check for Kyler Murray specifically
        print("="*80)
        print("SEARCHING FOR KYLER MURRAY")
        print("="*80 + "\n")
        
        kyler_found = False
        for player in players:
            first = player.get('firstName', '')
            last = player.get('lastName', '')
            full_name = f"{first} {last}".strip()
            
            if 'kyler' in full_name.lower() and 'murray' in full_name.lower():
                kyler_found = True
                print("✅ FOUND KYLER MURRAY IN RAW RESPONSE!")
                print(f"\nRaw player data:")
                print(json.dumps(player, indent=2))
                break
        
        if not kyler_found:
            print("❌ KYLER MURRAY NOT FOUND\n")
            
            # Show Arizona QBs
            print("📋 Arizona Cardinals players with injuries:\n")
            ari_count = 0
            for player in players:
                current_team = player.get('currentTeam', {})
                if current_team and current_team.get('abbreviation') == 'ARI':
                    ari_count += 1
                    first = player.get('firstName', '')
                    last = player.get('lastName', '')
                    pos = player.get('primaryPosition', 'N/A')
                    injury = player.get('currentInjury', {})
                    status = injury.get('playingProbability', 'Unknown') if injury else 'No injury'
                    print(f"  • {first} {last} ({pos}) - {status}")
            
            if ari_count == 0:
                print("  (none found)")
            
            # Show all injured QBs
            print("\n📋 ALL injured QBs in response:\n")
            qb_count = 0
            for player in players:
                pos = player.get('primaryPosition', '')
                if pos == 'QB':
                    qb_count += 1
                    first = player.get('firstName', '')
                    last = player.get('lastName', '')
                    current_team = player.get('currentTeam', {})
                    team_abbr = current_team.get('abbreviation', 'FA') if current_team else 'FA'
                    injury = player.get('currentInjury', {})
                    status = injury.get('playingProbability', 'Unknown') if injury else 'No injury'
                    desc = injury.get('description', '') if injury else ''
                    print(f"  • {first} {last} ({team_abbr}) - {status} ({desc})")
            
            if qb_count == 0:
                print("  (none found)")
        
        # Show lastUpdatedOn from API
        last_updated = data.get('lastUpdatedOn', 'Not provided')
        print(f"\n📅 API lastUpdatedOn: {last_updated}")
        
    elif response.status_code == 401:
        print("❌ 401 Unauthorized - API key may be invalid")
    elif response.status_code == 403:
        print("❌ 403 Forbidden - May not have DETAILED addon subscription")
        print("   Check: https://www.mysportsfeeds.com/data-feeds/api-docs/")
    else:
        print(f"❌ Unexpected status code: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

