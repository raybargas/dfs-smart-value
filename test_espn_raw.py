"""
Direct ESPN API test - show raw response.
"""

import requests
import json

url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"

print("="*80)
print("ESPN API RAW RESPONSE TEST")
print("="*80 + "\n")

print(f"📡 Requesting: {url}\n")

try:
    response = requests.get(url, timeout=10)
    
    print(f"✅ Status: {response.status_code}")
    print(f"✅ Size: {len(response.content)} bytes\n")
    
    if response.status_code == 200:
        data = response.json()
        
        print("📦 Response structure:")
        print(f"   Top-level keys: {list(data.keys())}\n")
        
        # Pretty print first part of response
        print("📄 Full raw response (first 2000 chars):\n")
        print(json.dumps(data, indent=2)[:2000])
        print("...\n")
        
        # Check injuries array
        if 'injuries' in data:
            injuries = data['injuries']
            print(f"✅ Found 'injuries' key with {len(injuries)} teams\n")
            
            # Show first team as example
            if injuries:
                first_team = injuries[0]
                print("📋 Example team structure:")
                print(json.dumps(first_team, indent=2)[:1000])
                print("...\n")
        else:
            print("❌ No 'injuries' key in response\n")
        
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

