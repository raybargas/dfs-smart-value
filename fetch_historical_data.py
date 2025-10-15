#!/usr/bin/env python3
"""
Historical Data Fetcher

This script helps fetch and store historical data for multiple weeks
to enable historical roster builds and analysis.
"""

import sys
import os
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.db_init import fetch_vegas_lines, fetch_injury_reports
from src.data_cache import save_vegas_lines_to_cache, save_injury_reports_to_cache
import streamlit as st


def fetch_week_data(week: int, api_key: str = None) -> bool:
    """
    Fetch and store data for a specific week.
    
    Args:
        week: NFL week number
        api_key: Optional API key for The Odds API
    
    Returns:
        True if successful, False otherwise
    """
    print(f"🔄 Fetching data for Week {week}...")
    
    success = True
    
    # Fetch Vegas lines
    print(f"📊 Fetching Vegas lines for Week {week}...")
    vegas_success = fetch_vegas_lines(week, api_key)
    if vegas_success:
        print(f"✅ Vegas lines fetched for Week {week}")
    else:
        print(f"❌ Failed to fetch Vegas lines for Week {week}")
        success = False
    
    # Fetch injury reports
    print(f"🏥 Fetching injury reports for Week {week}...")
    injury_success = fetch_injury_reports(week)
    if injury_success:
        print(f"✅ Injury reports fetched for Week {week}")
    else:
        print(f"❌ Failed to fetch injury reports for Week {week}")
        success = False
    
    # Save to cache
    if success:
        print(f"💾 Saving Week {week} to cache...")
        vegas_cached = save_vegas_lines_to_cache(week)
        injury_cached = save_injury_reports_to_cache(week)
        
        if vegas_cached and injury_cached:
            print(f"✅ Week {week} data cached successfully")
        else:
            print(f"⚠️ Partial cache save for Week {week}")
    
    return success


def fetch_multiple_weeks(weeks: list, api_key: str = None) -> dict:
    """
    Fetch data for multiple weeks.
    
    Args:
        weeks: List of week numbers to fetch
        api_key: Optional API key for The Odds API
    
    Returns:
        Dictionary with results for each week
    """
    results = {}
    
    for week in weeks:
        print(f"\n{'='*50}")
        print(f"Processing Week {week}")
        print(f"{'='*50}")
        
        try:
            success = fetch_week_data(week, api_key)
            results[week] = {
                'success': success,
                'message': 'Success' if success else 'Failed'
            }
        except Exception as e:
            print(f"❌ Error processing Week {week}: {str(e)}")
            results[week] = {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    return results


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch historical DFS data')
    parser.add_argument('--weeks', nargs='+', type=int, required=True,
                       help='Week numbers to fetch (e.g., --weeks 1 2 3)')
    parser.add_argument('--api-key', type=str,
                       help='The Odds API key (optional, uses env var if not provided)')
    
    args = parser.parse_args()
    
    # Get API key from args or environment
    api_key = args.api_key or os.getenv('THE_ODDS_API_KEY')
    
    if not api_key:
        print("⚠️ Warning: No API key provided. Vegas lines may not be fetched.")
        print("Set THE_ODDS_API_KEY environment variable or use --api-key")
    
    # Fetch data for specified weeks
    results = fetch_multiple_weeks(args.weeks, api_key)
    
    # Print summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    
    successful_weeks = []
    failed_weeks = []
    
    for week, result in results.items():
        if result['success']:
            successful_weeks.append(week)
            print(f"✅ Week {week}: {result['message']}")
        else:
            failed_weeks.append(week)
            print(f"❌ Week {week}: {result['message']}")
    
    print(f"\nSuccessful: {len(successful_weeks)} weeks")
    print(f"Failed: {len(failed_weeks)} weeks")
    
    if successful_weeks:
        print(f"Successfully fetched data for weeks: {', '.join(map(str, successful_weeks))}")
    
    if failed_weeks:
        print(f"Failed to fetch data for weeks: {', '.join(map(str, failed_weeks))}")


if __name__ == "__main__":
    main()
