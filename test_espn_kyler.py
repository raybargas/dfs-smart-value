"""
Test ESPN API for Kyler Murray injury data.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.api.espn_api import ESPNAPIClient

def test_espn_kyler():
    """Test if ESPN has Kyler Murray injury data."""
    
    print("="*80)
    print("ESPN API TEST - KYLER MURRAY")
    print("="*80 + "\n")
    
    client = ESPNAPIClient()
    
    try:
        # Fetch all NFL injuries
        print("📡 Fetching all NFL injuries from ESPN...")
        injuries = client.fetch_injuries()
        
        print(f"✅ Received {len(injuries)} injury reports\n")
        
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
            print("✅ FOUND KYLER MURRAY IN ESPN API!")
            print(f"\nPlayer: {kyler['player_name']}")
            print(f"Team: {kyler['team']}")
            print(f"Position: {kyler['position']}")
            print(f"Status: {kyler['injury_status']}")
            print(f"Body Part: {kyler['body_part']}")
            print(f"Description: {kyler['injury_description']}")
            print(f"Source: {kyler['source']}")
            print(f"Last Update: {kyler['last_update']}")
        else:
            print("❌ KYLER MURRAY NOT FOUND IN ESPN API")
            
            # Show Arizona Cardinals
            print("\n📋 Arizona Cardinals injuries in ESPN:\n")
            ari_injuries = [
                inj for inj in injuries 
                if inj['team'] == 'ARI'
            ]
            
            if ari_injuries:
                print(f"Found {len(ari_injuries)} Arizona Cardinals injuries:")
                for inj in sorted(ari_injuries, key=lambda x: x['player_name']):
                    print(f"  • {inj['player_name']} ({inj['position']}) - {inj['injury_status']} ({inj['body_part']})")
            else:
                print("No Arizona Cardinals injuries found")
            
            # Show all QBs
            print("\n📋 All QB injuries in ESPN:\n")
            qb_injuries = [
                inj for inj in injuries 
                if inj['position'] == 'QB'
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
    test_espn_kyler()

