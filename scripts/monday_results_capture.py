#!/usr/bin/env python3
"""
Monday Results Capture Script

Automatically fetches contest results and updates actual fantasy points
for the previous week's slate. Runs every Monday after games complete.

Purpose:
- Fetch contest standings from DFS sites (manual CSV for now, API later)
- Parse actual fantasy points scored by players
- Update historical_player_pool table with actual_points
- Log capture process for audit trail

Usage:
    # Manual mode: Provide CSV file from DFS site
    python monday_results_capture.py --week 6 --season 2024 --csv contest-standings.csv
    
    # Interactive mode: Prompt for inputs
    python monday_results_capture.py --interactive
    
    # Automated mode: Fetch from DFS API (Phase 2 feature)
    python monday_results_capture.py --week 6 --season 2024 --auto

Schedule:
    Run every Monday at 2 PM ET (after SNF/MNF games complete)
    
    Cron: 0 14 * * 1 /path/to/python monday_results_capture.py --auto

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
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from historical_data_manager import HistoricalDataManager
from database_models import create_session

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monday_results_capture.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MondayResultsCapture:
    """
    Monday results capture and update system.
    
    Fetches contest results and updates actual fantasy points for historical analysis.
    """
    
    def __init__(self, db_path: str = "dfs_optimizer.db"):
        """
        Initialize results capture system.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.manager = HistoricalDataManager(db_path=db_path)
        
    def parse_csv_results(self, csv_path: str) -> pd.DataFrame:
        """
        Parse contest results from CSV file.
        
        Expected CSV format from DraftKings/FanDuel:
        - Player Name
        - Position
        - Team
        - Fantasy Points (or FPTS)
        - Salary
        
        Args:
            csv_path: Path to contest results CSV
            
        Returns:
            DataFrame with player_name and actual_points
        """
        logger.info(f"Parsing CSV results from: {csv_path}")
        
        # Read CSV
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.error(f"Failed to read CSV: {e}")
            raise
        
        # Detect column names (different sites use different names)
        player_col = None
        points_col = None
        
        # Common column name patterns
        player_patterns = ['player', 'name', 'player name', 'player_name']
        points_patterns = ['fpts', 'fantasy points', 'points', 'actual', 'fantasy_points', 'actual_points']
        
        for col in df.columns:
            col_lower = col.lower().strip()
            
            if not player_col:
                for pattern in player_patterns:
                    if pattern in col_lower:
                        player_col = col
                        break
            
            if not points_col:
                for pattern in points_patterns:
                    if pattern in col_lower:
                        points_col = col
                        break
        
        if not player_col or not points_col:
            logger.error(f"Could not find player or points columns. Columns: {list(df.columns)}")
            raise ValueError(f"CSV must contain player name and fantasy points columns")
        
        logger.info(f"Detected columns: player='{player_col}', points='{points_col}'")
        
        # Extract relevant data
        results = df[[player_col, points_col]].copy()
        results.columns = ['player_name', 'actual_points']
        
        # Clean data
        results['player_name'] = results['player_name'].str.strip()
        results['actual_points'] = pd.to_numeric(results['actual_points'], errors='coerce')
        
        # Remove any rows with missing data
        results = results.dropna()
        
        logger.info(f"Parsed {len(results)} player results")
        
        return results
    
    def match_players_to_slate(
        self,
        results_df: pd.DataFrame,
        slate_id: str
    ) -> dict:
        """
        Match player names from results to historical player pool.
        
        Handles common name variations (Jr., Sr., etc.) and reports unmatched players.
        
        Args:
            results_df: DataFrame with player_name and actual_points
            slate_id: Slate identifier
            
        Returns:
            Dict mapping player_name to actual_points
        """
        logger.info(f"Matching {len(results_df)} players to slate {slate_id}")
        
        # Get players from slate
        historical_snapshot = self.manager.load_historical_snapshot(
            slate_id=slate_id,
            include_actuals=False
        )
        
        slate_players = set(historical_snapshot['player_name'].str.strip())
        
        # Match players
        matched = {}
        unmatched = []
        
        for idx, row in results_df.iterrows():
            player_name = row['player_name']
            actual_points = row['actual_points']
            
            # Exact match
            if player_name in slate_players:
                matched[player_name] = actual_points
            else:
                # Try fuzzy match (handle Jr., Sr., III, etc.)
                base_name = player_name.replace(' Jr.', '').replace(' Sr.', '').replace(' III', '').replace(' II', '').strip()
                
                found = False
                for slate_player in slate_players:
                    slate_base = slate_player.replace(' Jr.', '').replace(' Sr.', '').replace(' III', '').replace(' II', '').strip()
                    
                    if base_name == slate_base:
                        matched[slate_player] = actual_points
                        found = True
                        break
                
                if not found:
                    unmatched.append(player_name)
        
        logger.info(f"Matched {len(matched)}/{len(results_df)} players")
        
        if unmatched:
            logger.warning(f"Unmatched players ({len(unmatched)}): {unmatched[:10]}")
        
        return matched
    
    def update_slate_actuals(
        self,
        slate_id: str,
        actuals: dict
    ) -> int:
        """
        Update actual fantasy points for a slate.
        
        Args:
            slate_id: Slate identifier
            actuals: Dict mapping player_name to actual_points
            
        Returns:
            Number of players updated
        """
        logger.info(f"Updating {len(actuals)} players in slate {slate_id}")
        
        count = self.manager.update_actual_points(
            slate_id=slate_id,
            actuals=actuals
        )
        
        logger.info(f"Successfully updated {count} players")
        
        return count
    
    def process_results(
        self,
        week: int,
        season: int,
        csv_path: str,
        site: str = 'DraftKings',
        contest_type: str = 'Classic'
    ) -> dict:
        """
        Complete results capture workflow.
        
        Args:
            week: Week number
            season: Season year
            csv_path: Path to contest results CSV
            site: DFS site
            contest_type: Contest type
            
        Returns:
            Dict with capture summary
        """
        start_time = datetime.now()
        
        logger.info("="*60)
        logger.info(f"Monday Results Capture - Week {week}, {season} {site}")
        logger.info("="*60)
        
        # Generate slate ID
        slate_id = self.manager._generate_slate_id(
            week=week,
            season=season,
            site=site,
            contest_type=contest_type
        )
        
        # Verify slate exists
        metadata = self.manager.get_slate_metadata(slate_id)
        if not metadata:
            logger.error(f"Slate {slate_id} not found. Create slate first!")
            return {
                'success': False,
                'error': f"Slate {slate_id} not found"
            }
        
        logger.info(f"Found slate: {slate_id} ({metadata['player_count']} players)")
        
        # Parse CSV results
        try:
            results_df = self.parse_csv_results(csv_path)
        except Exception as e:
            logger.error(f"Failed to parse CSV: {e}")
            return {
                'success': False,
                'error': f"CSV parse error: {e}"
            }
        
        # Match players
        actuals = self.match_players_to_slate(results_df, slate_id)
        
        if not actuals:
            logger.error("No players matched. Check player names in CSV.")
            return {
                'success': False,
                'error': "No players matched"
            }
        
        # Update database
        try:
            count = self.update_slate_actuals(slate_id, actuals)
        except Exception as e:
            logger.error(f"Failed to update database: {e}")
            return {
                'success': False,
                'error': f"Database update error: {e}"
            }
        
        # Calculate summary stats
        total_points = sum(actuals.values())
        avg_points = total_points / len(actuals) if actuals else 0
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        summary = {
            'success': True,
            'slate_id': slate_id,
            'week': week,
            'season': season,
            'site': site,
            'players_in_slate': metadata['player_count'],
            'players_updated': count,
            'total_points': round(total_points, 2),
            'avg_points': round(avg_points, 2),
            'elapsed_seconds': round(elapsed, 2),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info("="*60)
        logger.info("RESULTS CAPTURE SUMMARY")
        logger.info("="*60)
        logger.info(f"Slate ID: {summary['slate_id']}")
        logger.info(f"Players Updated: {summary['players_updated']}/{summary['players_in_slate']}")
        logger.info(f"Total Points: {summary['total_points']}")
        logger.info(f"Average Points: {summary['avg_points']}")
        logger.info(f"Time Elapsed: {summary['elapsed_seconds']}s")
        logger.info("="*60)
        
        return summary
    
    def close(self):
        """Close resources."""
        try:
            self.manager.close()
        except Exception as e:
            logger.error(f"Error closing manager: {e}")


def interactive_mode():
    """
    Interactive mode for manual results capture.
    """
    print("\n" + "="*60)
    print("MONDAY RESULTS CAPTURE - INTERACTIVE MODE")
    print("="*60)
    
    # Get inputs
    week = int(input("Enter week number (1-18): "))
    season = int(input("Enter season year (e.g., 2024): "))
    site = input("Enter DFS site (DraftKings/FanDuel) [DraftKings]: ").strip() or "DraftKings"
    contest_type = input("Enter contest type (Classic/Showdown) [Classic]: ").strip() or "Classic"
    csv_path = input("Enter path to contest results CSV: ").strip()
    
    # Validate inputs
    if not os.path.exists(csv_path):
        print(f"\nError: CSV file not found: {csv_path}")
        return
    
    if not 1 <= week <= 18:
        print(f"\nError: Invalid week {week}. Must be 1-18.")
        return
    
    # Confirm
    print("\n" + "-"*60)
    print(f"Week: {week}")
    print(f"Season: {season}")
    print(f"Site: {site}")
    print(f"Contest Type: {contest_type}")
    print(f"CSV: {csv_path}")
    print("-"*60)
    
    confirm = input("\nProceed with results capture? (yes/no): ").strip().lower()
    
    if confirm != 'yes':
        print("Aborted.")
        return
    
    # Process results
    capture = MondayResultsCapture()
    try:
        summary = capture.process_results(
            week=week,
            season=season,
            csv_path=csv_path,
            site=site,
            contest_type=contest_type
        )
        
        if summary['success']:
            print("\n✅ Results capture successful!")
        else:
            print(f"\n❌ Results capture failed: {summary.get('error', 'Unknown error')}")
    
    finally:
        capture.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monday Results Capture - Update actual fantasy points",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python monday_results_capture.py --interactive
  
  # Manual CSV mode
  python monday_results_capture.py --week 6 --season 2024 --csv results.csv
  
  # Specify DFS site
  python monday_results_capture.py --week 6 --season 2024 --csv results.csv --site FanDuel
  
  # Automated mode (Phase 2 feature)
  python monday_results_capture.py --week 6 --season 2024 --auto
        """
    )
    
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Run in interactive mode')
    parser.add_argument('--week', '-w', type=int,
                        help='Week number (1-18)')
    parser.add_argument('--season', '-s', type=int, default=2024,
                        help='Season year (default: 2024)')
    parser.add_argument('--csv', '-c', type=str,
                        help='Path to contest results CSV')
    parser.add_argument('--site', type=str, default='DraftKings',
                        choices=['DraftKings', 'FanDuel'],
                        help='DFS site (default: DraftKings)')
    parser.add_argument('--contest-type', type=str, default='Classic',
                        help='Contest type (default: Classic)')
    parser.add_argument('--auto', '-a', action='store_true',
                        help='Automated mode - fetch from DFS API (Phase 2)')
    parser.add_argument('--db', type=str, default='dfs_optimizer.db',
                        help='Database path (default: dfs_optimizer.db)')
    
    args = parser.parse_args()
    
    # Interactive mode
    if args.interactive:
        interactive_mode()
        return
    
    # Auto mode (not implemented yet)
    if args.auto:
        print("❌ Automated mode not yet implemented (Phase 2 feature)")
        print("Use --csv mode for now:")
        print(f"  python {sys.argv[0]} --week {args.week or 'N'} --season {args.season} --csv /path/to/results.csv")
        sys.exit(1)
    
    # Manual CSV mode
    if not args.week or not args.csv:
        parser.print_help()
        print("\n❌ Error: --week and --csv are required for manual mode")
        print("Or use --interactive for guided setup")
        sys.exit(1)
    
    if not os.path.exists(args.csv):
        print(f"❌ Error: CSV file not found: {args.csv}")
        sys.exit(1)
    
    # Process results
    capture = MondayResultsCapture(db_path=args.db)
    try:
        summary = capture.process_results(
            week=args.week,
            season=args.season,
            csv_path=args.csv,
            site=args.site,
            contest_type=args.contest_type
        )
        
        if summary['success']:
            print("\n✅ Results capture successful!")
            sys.exit(0)
        else:
            print(f"\n❌ Results capture failed: {summary.get('error', 'Unknown error')}")
            sys.exit(1)
    
    finally:
        capture.close()


if __name__ == '__main__':
    main()

