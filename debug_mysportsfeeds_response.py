#!/usr/bin/env python3
"""
Debug script to inspect MySportsFeeds DFS API response structure.

This will show us exactly what fields are available so we can extract
the season and week information correctly.
"""

import os
import sys
import json
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from api.dfs_salaries_api import DFSSalariesAPIClient


def main():
    """Fetch and inspect MySportsFeeds response."""
    # Get API key from environment
    api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
    
    if not api_key:
        print("❌ MYSPORTSFEEDS_API_KEY not set")
        print("Set it with: export MYSPORTSFEEDS_API_KEY='your_key_here'")
        sys.exit(1)
    
    print("🔍 Inspecting MySportsFeeds DFS API Response Structure")
    print("=" * 70)
    
    # Initialize client
    client = DFSSalariesAPIClient(api_key=api_key)
    
    # Make raw API request
    season = 2025
    week = 7
    year = str(season).split('-')[0]
    next_year = int(year) + 1
    season_str = f"{year}-{next_year}-regular"
    
    endpoint = f"{season_str}/week/{week}/dfs.json"
    params = {'dfstype': 'draftkings'}
    
    print(f"\n📡 Endpoint: {endpoint}")
    print(f"📋 Params: {params}")
    print()
    
    try:
        response_data = client._make_request(endpoint, params=params)
        
        print("✅ API Response Received")
        print("=" * 70)
        
        # Show top-level keys
        print("\n🔑 Top-level keys:")
        print(json.dumps(list(response_data.keys()), indent=2))
        
        # Inspect sources
        if 'sources' in response_data:
            print(f"\n📊 Sources: {len(response_data['sources'])} found")
            
            for idx, source in enumerate(response_data['sources'][:1]):  # Just first source
                print(f"\n  Source {idx}:")
                print(f"    Keys: {list(source.keys())}")
                
                if 'source' in source:
                    print(f"    Name: {source['source']}")
                
                if 'slates' in source:
                    print(f"\n  📋 Slates: {len(source['slates'])} found")
                    
                    # Show first slate in detail
                    if source['slates']:
                        first_slate = source['slates'][0]
                        print(f"\n  First Slate Details:")
                        print(f"    Keys: {list(first_slate.keys())}")
                        
                        # Show all slate-level fields
                        for key, value in first_slate.items():
                            if key != 'players':  # Skip player array
                                print(f"    {key}: {value}")
                        
                        # Show player count
                        if 'players' in first_slate:
                            print(f"    players: [{len(first_slate['players'])} players]")
                            
                            # Show first player structure
                            if first_slate['players']:
                                first_player = first_slate['players'][0]
                                print(f"\n  First Player Keys:")
                                print(f"    {list(first_player.keys())}")
        
        # Save full response to file for inspection
        output_file = Path(__file__).parent / "mysportsfeeds_response_debug.json"
        with open(output_file, 'w') as f:
            json.dump(response_data, f, indent=2)
        
        print(f"\n💾 Full response saved to: {output_file}")
        print("\nYou can inspect the full structure in that file.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

