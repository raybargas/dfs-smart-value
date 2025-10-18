#!/usr/bin/env python3
"""
Test the FIXED DFS Salaries API Client with live API
"""

import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Load .env
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    print("Loading .env file...")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")

from src.api.dfs_salaries_api import DFSSalariesAPIClient

def main():
    api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
    
    if not api_key:
        print("❌ MYSPORTSFEEDS_API_KEY not set")
        sys.exit(1)
    
    print(f"✅ API Key found: {api_key[:8]}...\n")
    
    # Create client
    client = DFSSalariesAPIClient(api_key=api_key, db_path="dfs_optimizer.db")
    
    try:
        print("="*70)
        print("TEST 1: Fetch Week 6 (2024) DraftKings Salaries")
        print("="*70)
        
        df = client.fetch_historical_salaries(
            season='2024-2025-regular',
            week=6,
            site='draftkings'
        )
        
        print(f"\n✅ SUCCESS!")
        print(f"   Total Players: {len(df)}")
        print(f"   Slates: {df['slate_label'].unique() if 'slate_label' in df.columns else 'N/A'}")
        print(f"   Positions: {df['position'].value_counts().to_dict()}")
        print(f"\n   Sample Players:")
        print(df[['player_name', 'position', 'team', 'opponent', 'salary', 'projection']].head(10).to_string(index=False))
        
        # Test a QB
        qbs = df[df['position'] == 'QB'].sort_values('salary', ascending=False).head(3)
        print(f"\n   Top 3 QBs by Salary:")
        print(qbs[['player_name', 'team', 'salary']].to_string(index=False))
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()
        print("\n" + "="*70)
        print("Test complete!")
        print("="*70)

if __name__ == "__main__":
    main()

