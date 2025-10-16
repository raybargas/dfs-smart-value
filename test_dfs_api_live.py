"""
Manual test script for DFS Salaries API Client with real MySportsFeeds API.

Run this script to verify the DFS Salaries API client works with your actual API key.

Usage:
    python test_dfs_api_live.py

Requirements:
    - MYSPORTSFEEDS_API_KEY in .env file
    - MySportsFeeds subscription with DFS addon
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.api.dfs_salaries_api import DFSSalariesAPIClient, fetch_salaries
from src.api.base_client import APIError


def test_current_week_draftkings():
    """Test fetching current week DraftKings salaries."""
    print("\n" + "="*60)
    print("TEST 1: Fetch Current Week DraftKings Salaries")
    print("="*60)
    
    # Load API key
    load_dotenv()
    api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
    
    if not api_key:
        print("❌ Error: MYSPORTSFEEDS_API_KEY not found in .env file")
        return False
    
    try:
        # Create client
        client = DFSSalariesAPIClient(api_key=api_key, db_path="dfs_optimizer.db")
        
        # Fetch salaries
        print("\n📥 Fetching DraftKings salaries from MySportsFeeds...")
        df = client.fetch_current_week_salaries(site='draftkings')
        
        # Display results
        print(f"\n✅ Success! Fetched {len(df)} players")
        print(f"\n📊 Data Summary:")
        print(f"   - Players: {len(df)}")
        print(f"   - Columns: {list(df.columns)}")
        print(f"   - Salary range: ${df['salary'].min():,} - ${df['salary'].max():,}")
        
        print(f"\n👥 Sample Players (first 5):")
        print(df[['player_name', 'position', 'team', 'salary', 'projection']].head())
        
        # Verify data quality
        print(f"\n🔍 Data Quality Checks:")
        print(f"   - Missing player names: {df['player_name'].isna().sum()}")
        print(f"   - Missing positions: {df['position'].isna().sum()}")
        print(f"   - Missing salaries: {df['salary'].isna().sum()}")
        print(f"   - Invalid salaries (<$2000): {(df['salary'] < 2000).sum()}")
        print(f"   - Invalid salaries (>$10000): {(df['salary'] > 10000).sum()}")
        
        # Position breakdown
        print(f"\n📈 Position Breakdown:")
        print(df['position'].value_counts())
        
        client.close()
        return True
        
    except APIError as e:
        print(f"\n❌ API Error: {e}")
        if "403" in str(e):
            print("\n💡 Tip: Make sure your MySportsFeeds subscription includes the DFS addon")
            print("   Visit: https://www.mysportsfeeds.com/index.php/profile/30329/")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_current_week_fanduel():
    """Test fetching current week FanDuel salaries."""
    print("\n" + "="*60)
    print("TEST 2: Fetch Current Week FanDuel Salaries")
    print("="*60)
    
    # Load API key
    load_dotenv()
    api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
    
    if not api_key:
        print("❌ Error: MYSPORTSFEEDS_API_KEY not found in .env file")
        return False
    
    try:
        # Create client
        client = DFSSalariesAPIClient(api_key=api_key, db_path="dfs_optimizer.db")
        
        # Fetch salaries
        print("\n📥 Fetching FanDuel salaries from MySportsFeeds...")
        df = client.fetch_current_week_salaries(site='fanduel')
        
        # Display results
        print(f"\n✅ Success! Fetched {len(df)} players")
        print(f"\n📊 FanDuel Data Summary:")
        print(f"   - Players: {len(df)}")
        print(f"   - Salary range: ${df['salary'].min():,} - ${df['salary'].max():,}")
        
        print(f"\n👥 Sample Players (first 5):")
        print(df[['player_name', 'position', 'team', 'salary', 'projection']].head())
        
        client.close()
        return True
        
    except APIError as e:
        print(f"\n❌ API Error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        return False


def test_historical_week():
    """Test fetching historical salaries for a past week."""
    print("\n" + "="*60)
    print("TEST 3: Fetch Historical Salaries (Week 6)")
    print("="*60)
    
    # Load API key
    load_dotenv()
    api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
    
    if not api_key:
        print("❌ Error: MYSPORTSFEEDS_API_KEY not found in .env file")
        return False
    
    try:
        # Create client
        client = DFSSalariesAPIClient(api_key=api_key, db_path="dfs_optimizer.db")
        
        # Fetch historical salaries
        print("\n📥 Fetching Week 6 DraftKings salaries (historical)...")
        df = client.fetch_historical_salaries(
            season='2024-2025-regular',
            week=6,
            site='draftkings'
        )
        
        # Display results
        print(f"\n✅ Success! Fetched {len(df)} players for Week 6")
        print(f"\n📊 Historical Data Summary:")
        print(f"   - Players: {len(df)}")
        print(f"   - Salary range: ${df['salary'].min():,} - ${df['salary'].max():,}")
        
        print(f"\n👥 Sample Players (first 5):")
        print(df[['player_name', 'position', 'team', 'salary', 'projection']].head())
        
        client.close()
        return True
        
    except APIError as e:
        print(f"\n❌ API Error: {e}")
        if "404" in str(e):
            print("\n💡 Tip: Week 6 data may not be available yet, or may have been removed")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        return False


def test_convenience_function():
    """Test the convenience fetch_salaries function."""
    print("\n" + "="*60)
    print("TEST 4: Convenience Function")
    print("="*60)
    
    # Load API key
    load_dotenv()
    api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
    
    if not api_key:
        print("❌ Error: MYSPORTSFEEDS_API_KEY not found in .env file")
        return False
    
    try:
        # Test current week
        print("\n📥 Testing convenience function (current week)...")
        df = fetch_salaries(api_key=api_key, site='draftkings')
        
        print(f"✅ Success! Fetched {len(df)} players")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    """Run all manual tests."""
    print("\n" + "="*60)
    print("🧪 DFS SALARIES API - LIVE TESTING")
    print("="*60)
    print("\nThis script tests the DFS Salaries API client with real MySportsFeeds API.")
    print("Make sure you have MYSPORTSFEEDS_API_KEY in your .env file.")
    
    results = []
    
    # Run tests
    results.append(("Current Week DraftKings", test_current_week_draftkings()))
    results.append(("Current Week FanDuel", test_current_week_fanduel()))
    results.append(("Historical Week 6", test_historical_week()))
    results.append(("Convenience Function", test_convenience_function()))
    
    # Summary
    print("\n" + "="*60)
    print("📋 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! DFS Salaries API is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check error messages above for details.")


if __name__ == "__main__":
    main()

