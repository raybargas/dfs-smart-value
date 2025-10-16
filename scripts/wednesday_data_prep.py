#!/usr/bin/env python3
"""
Wednesday Data Prep Script

Automatically fetches and prepares DFS data for the upcoming week's slate.
Runs every Wednesday when DFS salaries are released.

Purpose:
- Fetch DFS salaries from MySportsFeeds API
- Create slate record for the week
- Store player pool snapshot
- Prepare data for optimization (Thursday/Friday work)

Usage:
    # Fetch current week from API
    python wednesday_data_prep.py --auto
    
    # Fetch specific week
    python wednesday_data_prep.py --week 7 --season 2024
    
    # Manual mode with CSV upload
    python wednesday_data_prep.py --week 7 --csv salaries.csv
    
    # Interactive mode
    python wednesday_data_prep.py --interactive

Schedule:
    Run every Wednesday at 12 PM ET (when DFS salaries release)
    
    Cron: 0 12 * * 3 /path/to/python wednesday_data_prep.py --auto

Author: Agent OS / DFS Historical Intelligence System
Date: 2025-10-16
"""

import sys
import os
import argparse
import pandas as pd
from datetime import datetime, date
from pathlib import Path
import logging

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from historical_data_manager import HistoricalDataManager
from api.dfs_salaries_api import fetch_salaries
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('wednesday_data_prep.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class WednesdayDataPrep:
    """
    Wednesday data preparation and slate creation system.
    
    Fetches DFS salaries and creates historical slate for the upcoming week.
    """
    
    def __init__(self, db_path: str = "dfs_optimizer.db"):
        """
        Initialize data prep system.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.manager = HistoricalDataManager(db_path=db_path)
    
    def fetch_salaries_from_api(
        self,
        week: int,
        season: int,
        site: str = 'draftkings'
    ) -> pd.DataFrame:
        """
        Fetch DFS salaries from MySportsFeeds API.
        
        Args:
            week: Week number (1-18)
            season: Season year
            site: DFS site ('draftkings' or 'fanduel')
            
        Returns:
            DataFrame with player salaries
        """
        logger.info(f"Fetching {site} salaries for Week {week}, {season}")
        
        # Get API key from environment
        api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
        if not api_key:
            raise ValueError(
                "MYSPORTSFEEDS_API_KEY not found in environment. "
                "Set it with: export MYSPORTSFEEDS_API_KEY='your_key'"
            )
        
        # Fetch salaries
        try:
            df = fetch_salaries(
                api_key=api_key,
                week=week,
                season=season,
                site=site,
                db_path=self.db_path
            )
            
            logger.info(f"Fetched {len(df)} players from {site}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch salaries from API: {e}")
            raise
    
    def parse_csv_salaries(self, csv_path: str) -> pd.DataFrame:
        """
        Parse DFS salaries from manual CSV upload.
        
        Expected CSV format:
        - player_name or Name
        - position or Roster Position
        - team or TeamAbbrev
        - salary or Salary
        
        Args:
            csv_path: Path to salaries CSV
            
        Returns:
            DataFrame with standardized columns
        """
        logger.info(f"Parsing CSV salaries from: {csv_path}")
        
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.error(f"Failed to read CSV: {e}")
            raise
        
        # Detect columns
        col_map = {}
        required_fields = ['player_name', 'position', 'team', 'salary']
        
        for field in required_fields:
            # Common column name patterns
            patterns = {
                'player_name': ['player', 'name', 'player name', 'player_name'],
                'position': ['position', 'pos', 'roster position', 'roster_position'],
                'team': ['team', 'teamabbrev', 'team_abbrev', 'tm'],
                'salary': ['salary', 'sal', 'cost', 'price']
            }
            
            found = False
            for col in df.columns:
                col_lower = col.lower().strip()
                if any(pattern in col_lower for pattern in patterns[field]):
                    col_map[field] = col
                    found = True
                    break
            
            if not found:
                raise ValueError(f"Could not find '{field}' column. Columns: {list(df.columns)}")
        
        logger.info(f"Detected columns: {col_map}")
        
        # Rename columns
        df = df.rename(columns={v: k for k, v in col_map.items()})
        
        # Clean data
        df['player_name'] = df['player_name'].str.strip()
        df['position'] = df['position'].str.strip().str.upper()
        df['team'] = df['team'].str.strip().str.upper()
        df['salary'] = pd.to_numeric(df['salary'], errors='coerce')
        
        # Add default values for missing columns
        if 'projection' not in df.columns:
            df['projection'] = 0.0  # Will be filled in later
        if 'opponent' not in df.columns:
            df['opponent'] = ''
        if 'ceiling' not in df.columns:
            df['ceiling'] = None
        if 'ownership' not in df.columns:
            df['ownership'] = None
        
        # Remove invalid rows
        df = df.dropna(subset=['player_name', 'salary'])
        df = df[df['salary'] > 0]
        
        logger.info(f"Parsed {len(df)} valid players")
        
        return df
    
    def extract_games_from_data(self, df: pd.DataFrame) -> list:
        """
        Extract game matchups from player data.
        
        Args:
            df: DataFrame with team and opponent columns
            
        Returns:
            List of game identifiers (e.g., ['KC@BUF', 'SF@LAR'])
        """
        games = set()
        
        if 'opponent' in df.columns and 'team' in df.columns:
            for _, row in df.iterrows():
                team = str(row['team']).strip().upper()
                opp = str(row['opponent']).strip().upper().replace('@', '').replace('VS', '')
                
                if team and opp and team != '' and opp != '':
                    # Create game identifier (home@away format)
                    game = f"{team}@{opp}" if '@' not in str(row['opponent']) else f"{opp}@{team}"
                    games.add(game)
        else:
            # Fallback: Use unique teams
            teams = df['team'].unique().tolist()
            for i in range(0, len(teams), 2):
                if i + 1 < len(teams):
                    games.add(f"{teams[i]}@{teams[i+1]}")
        
        return sorted(list(games))
    
    def create_slate_and_store(
        self,
        week: int,
        season: int,
        site: str,
        contest_type: str,
        player_data: pd.DataFrame,
        projection_source: str = 'pending',
        ownership_source: str = 'pending'
    ) -> str:
        """
        Create slate and store player pool.
        
        Args:
            week: Week number
            season: Season year
            site: DFS site
            contest_type: Contest type
            player_data: DataFrame with player data
            projection_source: Source of projections
            ownership_source: Source of ownership
            
        Returns:
            slate_id: Created slate identifier
        """
        logger.info(f"Creating slate for Week {week}, {season} {site}")
        
        # Extract games
        games = self.extract_games_from_data(player_data)
        logger.info(f"Extracted {len(games)} games: {games}")
        
        # Create slate
        try:
            slate_id = self.manager.create_slate(
                week=week,
                season=season,
                site=site,
                contest_type=contest_type,
                games=games,
                slate_date=date.today()
            )
            logger.info(f"Created slate: {slate_id}")
        except ValueError as e:
            if "already exists" in str(e):
                logger.warning(f"Slate already exists, will update player pool")
                slate_id = self.manager._generate_slate_id(week, season, site, contest_type)
            else:
                raise
        
        # Store player pool
        try:
            count = self.manager.store_player_pool_snapshot(
                slate_id=slate_id,
                player_data=player_data,
                smart_value_profile=None,  # Not calculated yet
                projection_source=projection_source,
                ownership_source=ownership_source
            )
            logger.info(f"Stored {count} players in slate {slate_id}")
        except Exception as e:
            logger.error(f"Failed to store player pool: {e}")
            raise
        
        return slate_id
    
    def process_week(
        self,
        week: int,
        season: int,
        site: str = 'DraftKings',
        contest_type: str = 'Classic',
        csv_path: str = None,
        use_api: bool = True
    ) -> dict:
        """
        Complete Wednesday data prep workflow.
        
        Args:
            week: Week number
            season: Season year
            site: DFS site
            contest_type: Contest type
            csv_path: Optional path to CSV (manual mode)
            use_api: Whether to use API (vs. CSV)
            
        Returns:
            Dict with prep summary
        """
        start_time = datetime.now()
        
        logger.info("="*60)
        logger.info(f"Wednesday Data Prep - Week {week}, {season} {site}")
        logger.info("="*60)
        
        # Fetch or parse data
        if use_api:
            try:
                site_lower = site.lower().replace('draft', 'draft').replace('kings', 'kings')
                if 'fanduel' in site_lower:
                    site_lower = 'fanduel'
                else:
                    site_lower = 'draftkings'
                    
                player_data = self.fetch_salaries_from_api(
                    week=week,
                    season=season,
                    site=site_lower
                )
                data_source = f"mysportsfeeds_{site_lower}"
            except Exception as e:
                logger.error(f"API fetch failed: {e}")
                return {
                    'success': False,
                    'error': f"API fetch error: {e}"
                }
        else:
            if not csv_path:
                return {
                    'success': False,
                    'error': "CSV path required for manual mode"
                }
            try:
                player_data = self.parse_csv_salaries(csv_path)
                data_source = "manual_csv"
            except Exception as e:
                logger.error(f"CSV parse failed: {e}")
                return {
                    'success': False,
                    'error': f"CSV parse error: {e}"
                }
        
        # Create slate and store
        try:
            slate_id = self.create_slate_and_store(
                week=week,
                season=season,
                site=site,
                contest_type=contest_type,
                player_data=player_data,
                projection_source=data_source,
                ownership_source='pending'
            )
        except Exception as e:
            logger.error(f"Slate creation failed: {e}")
            return {
                'success': False,
                'error': f"Slate creation error: {e}"
            }
        
        # Get metadata
        metadata = self.manager.get_slate_metadata(slate_id)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        summary = {
            'success': True,
            'slate_id': slate_id,
            'week': week,
            'season': season,
            'site': site,
            'player_count': metadata['player_count'],
            'games': metadata['games'],
            'data_source': data_source,
            'elapsed_seconds': round(elapsed, 2),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info("="*60)
        logger.info("DATA PREP SUMMARY")
        logger.info("="*60)
        logger.info(f"Slate ID: {summary['slate_id']}")
        logger.info(f"Players: {summary['player_count']}")
        logger.info(f"Games: {len(summary['games'])}")
        logger.info(f"Data Source: {summary['data_source']}")
        logger.info(f"Time Elapsed: {summary['elapsed_seconds']}s")
        logger.info("="*60)
        logger.info("✅ Ready for optimization! Run Streamlit app to generate lineups.")
        logger.info("="*60)
        
        return summary
    
    def close(self):
        """Close resources."""
        try:
            self.manager.close()
        except Exception as e:
            logger.error(f"Error closing manager: {e}")


def interactive_mode():
    """Interactive mode for manual data prep."""
    print("\n" + "="*60)
    print("WEDNESDAY DATA PREP - INTERACTIVE MODE")
    print("="*60)
    
    # Get inputs
    week = int(input("Enter week number (1-18): "))
    season = int(input("Enter season year (e.g., 2024): "))
    site = input("Enter DFS site (DraftKings/FanDuel) [DraftKings]: ").strip() or "DraftKings"
    contest_type = input("Enter contest type (Classic/Showdown) [Classic]: ").strip() or "Classic"
    
    mode = input("Fetch from API or use CSV? (api/csv) [api]: ").strip().lower() or "api"
    
    csv_path = None
    if mode == 'csv':
        csv_path = input("Enter path to salaries CSV: ").strip()
        if not os.path.exists(csv_path):
            print(f"\n❌ Error: CSV file not found: {csv_path}")
            return
    
    # Confirm
    print("\n" + "-"*60)
    print(f"Week: {week}")
    print(f"Season: {season}")
    print(f"Site: {site}")
    print(f"Contest Type: {contest_type}")
    print(f"Data Source: {'MySportsFeeds API' if mode == 'api' else csv_path}")
    print("-"*60)
    
    confirm = input("\nProceed with data prep? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Aborted.")
        return
    
    # Process
    prep = WednesdayDataPrep()
    try:
        summary = prep.process_week(
            week=week,
            season=season,
            site=site,
            contest_type=contest_type,
            csv_path=csv_path,
            use_api=(mode == 'api')
        )
        
        if summary['success']:
            print("\n✅ Data prep successful!")
        else:
            print(f"\n❌ Data prep failed: {summary.get('error', 'Unknown error')}")
    
    finally:
        prep.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Wednesday Data Prep - Fetch and prepare DFS data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python wednesday_data_prep.py --interactive
  
  # Fetch from API (auto-detect current week)
  python wednesday_data_prep.py --auto
  
  # Fetch specific week from API
  python wednesday_data_prep.py --week 7 --season 2024
  
  # Manual CSV mode
  python wednesday_data_prep.py --week 7 --csv salaries.csv
        """
    )
    
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Run in interactive mode')
    parser.add_argument('--auto', '-a', action='store_true',
                        help='Auto-fetch current week from API')
    parser.add_argument('--week', '-w', type=int,
                        help='Week number (1-18)')
    parser.add_argument('--season', '-s', type=int, default=2024,
                        help='Season year (default: 2024)')
    parser.add_argument('--csv', '-c', type=str,
                        help='Path to salaries CSV (manual mode)')
    parser.add_argument('--site', type=str, default='DraftKings',
                        choices=['DraftKings', 'FanDuel'],
                        help='DFS site (default: DraftKings)')
    parser.add_argument('--contest-type', type=str, default='Classic',
                        help='Contest type (default: Classic)')
    parser.add_argument('--db', type=str, default='dfs_optimizer.db',
                        help='Database path (default: dfs_optimizer.db)')
    
    args = parser.parse_args()
    
    # Interactive mode
    if args.interactive:
        interactive_mode()
        return
    
    # Auto mode (current week)
    if args.auto:
        # Use current week (simplified - should query API for current week)
        week = args.week or 7  # Placeholder
        logger.info(f"Auto mode: Using week {week}")
        
        prep = WednesdayDataPrep(db_path=args.db)
        try:
            summary = prep.process_week(
                week=week,
                season=args.season,
                site=args.site,
                contest_type=args.contest_type,
                use_api=True
            )
            
            if summary['success']:
                print("\n✅ Data prep successful!")
                sys.exit(0)
            else:
                print(f"\n❌ Data prep failed: {summary.get('error')}")
                sys.exit(1)
        finally:
            prep.close()
        return
    
    # Manual mode
    if not args.week:
        parser.print_help()
        print("\n❌ Error: --week required (or use --interactive/--auto)")
        sys.exit(1)
    
    use_api = not bool(args.csv)
    
    if args.csv and not os.path.exists(args.csv):
        print(f"❌ Error: CSV file not found: {args.csv}")
        sys.exit(1)
    
    prep = WednesdayDataPrep(db_path=args.db)
    try:
        summary = prep.process_week(
            week=args.week,
            season=args.season,
            site=args.site,
            contest_type=args.contest_type,
            csv_path=args.csv,
            use_api=use_api
        )
        
        if summary['success']:
            print("\n✅ Data prep successful!")
            sys.exit(0)
        else:
            print(f"\n❌ Data prep failed: {summary.get('error')}")
            sys.exit(1)
    finally:
        prep.close()


if __name__ == '__main__':
    main()

