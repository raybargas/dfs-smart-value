"""
Historical Data Manager

Manages storage and retrieval of complete weekly DFS data snapshots.
Enables "time travel" to replay any past week with different Smart Value profiles.

Key Features:
- Create slate records (multi-site, multi-contest support)
- Store complete player pool snapshots per week
- Update actual results (Monday automation)
- Load exact historical snapshots for backtesting
- Query available weeks for UI

Usage:
    manager = HistoricalDataManager()
    
    # Create slate
    slate_id = manager.create_slate(
        week=6, season=2024, site='DraftKings',
        contest_type='Classic', games=['KC@BUF', 'SF@LAR']
    )
    
    # Store player pool
    manager.store_player_pool_snapshot(
        slate_id=slate_id,
        player_data=df,
        smart_value_profile='GPP_Balanced_v3.0',
        projection_source='manual',
        ownership_source='fantasylabs'
    )
    
    # Later: Load for backtesting
    df = manager.load_historical_snapshot(slate_id='2024-W6-DK-CLASSIC')
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, date
import pandas as pd
import json
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

try:
    from .database_models import (
        Slate, HistoricalPlayerPool, SmartValueProfileHistory,
        create_session
    )
except ImportError:
    from database_models import (
        Slate, HistoricalPlayerPool, SmartValueProfileHistory,
        create_session
    )


class HistoricalDataManager:
    """
    Manages historical DFS data storage and retrieval.
    
    Stores complete weekly snapshots of player pools including:
    - Salaries (from DFS sites)
    - Projections (user uploads or APIs)
    - Ownership estimates
    - Smart Value scores
    - Actual results (fetched post-game)
    
    Enables:
    - Backtesting different Smart Value profiles
    - Season-long trend analysis
    - Profile performance tracking
    - "Time travel" to any past week
    """
    
    def __init__(self, db_path: str = "dfs_optimizer.db"):
        """
        Initialize Historical Data Manager.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        
        # Setup database session
        engine = create_engine(f'sqlite:///{db_path}')
        Session = sessionmaker(bind=engine)
        self.session = Session()
    
    def create_slate(
        self,
        week: int,
        season: int,
        site: str,
        contest_type: str,
        games: List[str],
        slate_date: Optional[date] = None
    ) -> str:
        """
        Create a slate record.
        
        Args:
            week: NFL week number (1-18)
            season: Season year (e.g., 2024)
            site: DFS site ('DraftKings', 'FanDuel')
            contest_type: Contest type ('Classic', 'Showdown', 'Thanksgiving')
            games: List of game identifiers (e.g., ['KC@BUF', 'SF@LAR'])
            slate_date: Date of the slate (defaults to today)
            
        Returns:
            slate_id: Unique slate identifier (e.g., '2024-W6-DK-CLASSIC')
            
        Raises:
            ValueError: If slate already exists
        """
        # Validate inputs
        if not 1 <= week <= 18:
            raise ValueError(f"Invalid week {week}. Must be between 1 and 18.")
        
        if season < 2020 or season > 2030:
            raise ValueError(f"Invalid season {season}. Must be between 2020 and 2030.")
        
        # Generate slate ID
        slate_id = self._generate_slate_id(week, season, site, contest_type)
        
        # Check if slate already exists
        existing_slate = self.session.query(Slate).filter(
            Slate.slate_id == slate_id
        ).first()
        
        if existing_slate:
            raise ValueError(
                f"Slate {slate_id} already exists. Use update method to modify."
            )
        
        # Create slate record
        slate = Slate(
            slate_id=slate_id,
            week=week,
            season=season,
            site=site,
            contest_type=contest_type,
            slate_date=slate_date or date.today(),
            games_in_slate=json.dumps(games),
            created_at=datetime.now()
        )
        
        try:
            self.session.add(slate)
            self.session.commit()
            return slate_id
        except IntegrityError as e:
            self.session.rollback()
            raise ValueError(f"Failed to create slate: {e}")
    
    def store_player_pool_snapshot(
        self,
        slate_id: str,
        player_data: pd.DataFrame,
        smart_value_profile: Optional[str] = None,
        projection_source: str = 'manual',
        ownership_source: str = 'manual'
    ) -> int:
        """
        Store complete player pool snapshot for a slate.
        
        Args:
            slate_id: Slate identifier
            player_data: DataFrame with player data
            smart_value_profile: Profile used for Smart Value (e.g., 'GPP_Balanced_v3.0')
            projection_source: Source of projections ('manual', 'rotogrinders_v1', etc.)
            ownership_source: Source of ownership ('manual', 'fantasylabs', etc.)
            
        Returns:
            int: Number of players stored
            
        Raises:
            ValueError: If slate doesn't exist or required columns missing
        """
        # Verify slate exists
        slate = self.session.query(Slate).filter(Slate.slate_id == slate_id).first()
        if not slate:
            raise ValueError(f"Slate {slate_id} not found. Create slate first.")
        
        # Validate required columns
        required_cols = ['player_name', 'position', 'team', 'salary', 'projection']
        missing_cols = [col for col in required_cols if col not in player_data.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        # Prepare player records
        players_stored = 0
        
        for idx, row in player_data.iterrows():
            # Generate player_id if not provided or is nan
            raw_player_id = row.get('player_id')
            if pd.isna(raw_player_id) or raw_player_id is None or str(raw_player_id).lower() == 'nan':
                # Use player_name_team as unique identifier (for DST and players without IDs)
                player_id = f"{row['player_name']}_{row['team']}"
            else:
                player_id = str(raw_player_id)
            
            # Create player record
            # Handle opponent field (can be None/NaN for some players)
            opponent_value = row.get('opponent')
            if pd.isna(opponent_value) or opponent_value is None or opponent_value == '':
                opponent_value = None
            
            player = HistoricalPlayerPool(
                slate_id=slate_id,
                player_id=player_id,
                player_name=row['player_name'],
                position=row['position'],
                team=row['team'],
                opponent=opponent_value,
                salary=int(row['salary']),
                projection=float(row['projection']),
                ceiling=float(row['ceiling']) if pd.notna(row.get('ceiling')) else None,
                ownership=float(row['ownership']) if pd.notna(row.get('ownership')) else None,
                actual_points=None,  # Filled in Monday
                smart_value=float(row['smart_value']) if pd.notna(row.get('smart_value')) else None,
                smart_value_profile=smart_value_profile,
                projection_source=projection_source,
                ownership_source=ownership_source,
                data_source='mysportsfeeds_dfs' if 'mysportsfeeds' in projection_source else 'manual_upload',
                fetched_at=datetime.now()
            )
            
            try:
                self.session.add(player)
                players_stored += 1
            except Exception as e:
                print(f"Warning: Failed to store player {row['player_name']}: {e}")
                continue
        
        # Commit all players
        try:
            self.session.commit()
            return players_stored
        except Exception as e:
            self.session.rollback()
            raise ValueError(f"Failed to store player pool: {e}")
    
    def update_actual_points(
        self,
        slate_id: str,
        actuals: Dict[str, float]
    ) -> int:
        """
        Update actual fantasy points for players (Monday automation).
        
        Args:
            slate_id: Slate identifier
            actuals: Dict mapping player_name to actual_points
            
        Returns:
            int: Number of players updated
            
        Example:
            actuals = {
                'Patrick Mahomes': 28.4,
                'Travis Kelce': 14.2,
                ...
            }
            manager.update_actual_points(slate_id, actuals)
        """
        # Get all players for this slate
        players = self.session.query(HistoricalPlayerPool).filter(
            HistoricalPlayerPool.slate_id == slate_id
        ).all()
        
        if not players:
            raise ValueError(f"No players found for slate {slate_id}")
        
        # Update actual points
        updated_count = 0
        for player in players:
            if player.player_name in actuals:
                player.actual_points = actuals[player.player_name]
                updated_count += 1
        
        # Commit updates
        try:
            self.session.commit()
            return updated_count
        except Exception as e:
            self.session.rollback()
            raise ValueError(f"Failed to update actual points: {e}")
    
    def load_historical_snapshot(
        self,
        slate_id: str,
        include_actuals: bool = True
    ) -> pd.DataFrame:
        """
        Load exact historical snapshot for backtesting.
        
        Returns the player pool exactly as it was, enabling perfect replay
        with different Smart Value profiles.
        
        Args:
            slate_id: Slate identifier
            include_actuals: Whether to include actual_points column
            
        Returns:
            DataFrame with all player data from that slate
            
        Raises:
            ValueError: If slate not found
        """
        # Query players for this slate
        players = self.session.query(HistoricalPlayerPool).filter(
            HistoricalPlayerPool.slate_id == slate_id
        ).all()
        
        if not players:
            raise ValueError(f"No data found for slate {slate_id}")
        
        # Convert to DataFrame
        data = []
        for player in players:
            record = {
                'player_id': player.player_id,
                'player_name': player.player_name,
                'position': player.position,
                'team': player.team,
                'opponent': player.opponent,
                'salary': player.salary,
                'projection': player.projection,
                'ceiling': player.ceiling,
                'ownership': player.ownership,
                'smart_value': player.smart_value,
                'smart_value_profile': player.smart_value_profile,
                'projection_source': player.projection_source,
                'ownership_source': player.ownership_source,
                'data_source': player.data_source
            }
            
            if include_actuals:
                record['actual_points'] = player.actual_points
            
            data.append(record)
        
        df = pd.DataFrame(data)
        return df
    
    def get_available_weeks(
        self,
        season: int = 2024,
        site: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of available weeks with historical data.
        
        Args:
            season: Season year
            site: Optional site filter ('DraftKings', 'FanDuel')
            
        Returns:
            List of dicts with slate metadata
            
        Example:
            [
                {'week': 6, 'slate_id': '2024-W6-DK-CLASSIC', 'player_count': 250},
                {'week': 7, 'slate_id': '2024-W7-DK-CLASSIC', 'player_count': 248},
                ...
            ]
        """
        # Query slates
        query = self.session.query(Slate).filter(Slate.season == season)
        
        if site:
            query = query.filter(Slate.site == site)
        
        slates = query.order_by(Slate.week).all()
        
        # Get player counts
        result = []
        for slate in slates:
            player_count = self.session.query(HistoricalPlayerPool).filter(
                HistoricalPlayerPool.slate_id == slate.slate_id
            ).count()
            
            result.append({
                'week': slate.week,
                'slate_id': slate.slate_id,
                'site': slate.site,
                'contest_type': slate.contest_type,
                'slate_date': slate.slate_date,
                'player_count': player_count,
                'games': json.loads(slate.games_in_slate) if slate.games_in_slate else []
            })
        
        return result
    
    def get_slate_metadata(self, slate_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific slate.
        
        Args:
            slate_id: Slate identifier
            
        Returns:
            Dict with slate metadata or None if not found
        """
        slate = self.session.query(Slate).filter(Slate.slate_id == slate_id).first()
        
        if not slate:
            return None
        
        player_count = self.session.query(HistoricalPlayerPool).filter(
            HistoricalPlayerPool.slate_id == slate_id
        ).count()
        
        return {
            'slate_id': slate.slate_id,
            'week': slate.week,
            'season': slate.season,
            'site': slate.site,
            'contest_type': slate.contest_type,
            'slate_date': slate.slate_date,
            'player_count': player_count,
            'games': json.loads(slate.games_in_slate) if slate.games_in_slate else [],
            'created_at': slate.created_at
        }
    
    def delete_slate(self, slate_id: str) -> bool:
        """
        Delete a slate and all associated player data.
        
        Args:
            slate_id: Slate identifier
            
        Returns:
            bool: True if deleted, False if not found
        """
        # Delete players first (foreign key constraint)
        self.session.query(HistoricalPlayerPool).filter(
            HistoricalPlayerPool.slate_id == slate_id
        ).delete()
        
        # Delete slate
        result = self.session.query(Slate).filter(
            Slate.slate_id == slate_id
        ).delete()
        
        try:
            self.session.commit()
            return result > 0
        except Exception as e:
            self.session.rollback()
            raise ValueError(f"Failed to delete slate: {e}")
    
    def _generate_slate_id(
        self,
        week: int,
        season: int,
        site: str,
        contest_type: str
    ) -> str:
        """
        Generate unique slate ID.
        
        Format: {season}-W{week}-{SITE_ABBREV}-{TYPE}
        Example: 2024-W6-DK-CLASSIC
        
        Args:
            week: Week number
            season: Season year
            site: DFS site
            contest_type: Contest type
            
        Returns:
            Slate ID string
        """
        # Site abbreviations
        site_abbrev = {
            'draftkings': 'DK',
            'fanduel': 'FD',
            'yahoo': 'YH',
            'fantasydraft': 'FDR'
        }
        
        site_code = site_abbrev.get(site.lower(), site[:3].upper())
        type_code = contest_type.upper()
        
        return f"{season}-W{week}-{site_code}-{type_code}"
    
    def close(self):
        """Close database session."""
        try:
            self.session.close()
        except Exception as e:
            print(f"Error closing session: {e}")


# Convenience functions
def create_slate_from_dfs_data(
    dfs_salaries_df: pd.DataFrame,
    week: int,
    season: int = 2024,
    site: str = 'DraftKings',
    contest_type: str = 'Classic',
    db_path: str = "dfs_optimizer.db"
) -> str:
    """
    Convenience function to create slate from DFS salary data.
    
    Args:
        dfs_salaries_df: DataFrame from DFSSalariesAPIClient
        week: Week number
        season: Season year
        site: DFS site
        contest_type: Contest type
        db_path: Database path
        
    Returns:
        slate_id: Created slate identifier
    
    Example:
        from src.api.dfs_salaries_api import fetch_salaries
        from src.historical_data_manager import create_slate_from_dfs_data
        
        # Fetch salaries
        df = fetch_salaries(api_key, site='draftkings')
        
        # Create slate and store
        slate_id = create_slate_from_dfs_data(df, week=6)
    """
    manager = HistoricalDataManager(db_path)
    
    try:
        # Extract unique teams to get games (simplified)
        teams = dfs_salaries_df['team'].unique().tolist()
        games = [f"Game_{i}" for i in range(len(teams) // 2)]
        
        # Create slate
        slate_id = manager.create_slate(
            week=week,
            season=season,
            site=site,
            contest_type=contest_type,
            games=games
        )
        
        # Store player pool
        manager.store_player_pool_snapshot(
            slate_id=slate_id,
            player_data=dfs_salaries_df,
            projection_source='mysportsfeeds_dfs',
            ownership_source='pending'
        )
        
        return slate_id
        
    finally:
        manager.close()

