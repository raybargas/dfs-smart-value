"""
Test full ESPN integration with Kyler Murray case.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.api.espn_api import ESPNAPIClient

def test_espn_integration():
    """Test ESPN integration with full context and affected players."""
    
    print("="*80)
    print("ESPN INTEGRATION TEST — KYLER MURRAY CASE")
    print("="*80 + "\n")
    
    client = ESPNAPIClient()
    
    try:
        print("📡 Fetching all NFL injuries from ESPN...")
        injuries = client.fetch_injuries()
        
        print(f"✅ Fetched {len(injuries)} injury reports\n")
        
        # Find Kyler Murray
        kyler = next((inj for inj in injuries if 'kyler murray' in inj['player_name'].lower()), None)
        
        if kyler:
            print("="*80)
            print("✅ KYLER MURRAY FOUND — FULL DATA")
            print("="*80 + "\n")
            
            print(f"Player: {kyler['player_name']}")
            print(f"Team: {kyler['team']}")
            print(f"Position: {kyler['position']}")
            print(f"Status: {kyler['injury_status']}")
            print(f"Body Part: {kyler['body_part']}")
            print(f"Source: {kyler['source']}")
            print(f"ESPN Date: {kyler.get('espn_date', 'N/A')}\n")
            
            print("="*80)
            print("📝 SHORT COMMENT")
            print("="*80)
            print(kyler.get('short_comment', 'N/A'))
            print()
            
            print("="*80)
            print("📖 LONG COMMENT (FULL CONTEXT)")
            print("="*80)
            print(kyler.get('long_comment', 'N/A'))
            print()
            
            print("="*80)
            print("👥 AFFECTED PLAYERS")
            print("="*80)
            affected = kyler.get('affected_players', [])
            if affected:
                for player in affected:
                    print(f"  • {player}")
            else:
                print("  (none detected)")
            print()
            
            # Test the display format
            print("="*80)
            print("🎨 TABLE DISPLAY FORMAT")
            print("="*80)
            print(f"Player: {kyler['player_name']}")
            print(f"Team: {kyler['team']}")
            print(f"Position: {kyler['position']}")
            print(f"Status: {kyler['injury_status']}")
            print(f"Injury: {kyler['body_part']}")
            short = kyler.get('short_comment', '')
            context = short[:80] + '...' if len(short) > 80 else short
            print(f"Context: {context}")
            affected_str = ', '.join(affected) if affected else '—'
            print(f"Affected: {affected_str}")
            
        else:
            print("❌ Kyler Murray not found!")
        
        client.close()
        
        # Show some stats
        print("\n" + "="*80)
        print("📊 OVERALL STATISTICS")
        print("="*80)
        
        # Count by status
        status_counts = {}
        affected_count = 0
        qbs = []
        
        for inj in injuries:
            status = inj.get('injury_status', 'Unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
            
            if inj.get('affected_players'):
                affected_count += 1
            
            if inj.get('position') == 'QB':
                qbs.append(inj['player_name'])
        
        print(f"\nTotal injuries: {len(injuries)}")
        print(f"Injuries with affected players: {affected_count}")
        print(f"\nStatus breakdown:")
        for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {status}: {count}")
        
        print(f"\nInjured QBs: {len(qbs)}")
        for qb in sorted(qbs):
            print(f"  • {qb}")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_espn_integration()

