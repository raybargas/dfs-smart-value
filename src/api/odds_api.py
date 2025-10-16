"""
The Odds API client for fetching Vegas lines, spreads, and totals.

API Documentation: https://the-odds-api.com/liveapi/guides/v4/
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .base_client import BaseAPIClient, APIError

try:
    from ..database_models import VegasLine
except ImportError:
    from database_models import VegasLine


class OddsAPIClient(BaseAPIClient):
    """
    Client for The Odds API.
    
    Features:
    - Fetch NFL odds (spreads, totals, moneylines)
    - Calculate implied team totals (ITT)
    - Cache results in database (24-hour TTL)
    - Rate limit: 500 calls/month on free tier
    """
    
    def __init__(self, api_key: str, db_path: str = "dfs_optimizer.db"):
        """
        Initialize Odds API client.
        
        Args:
            api_key: The Odds API key (get from https://the-odds-api.com)
            db_path: Path to SQLite database
        """
        super().__init__(
            api_name="The Odds API",
            base_url="https://api.the-odds-api.com/v4",
            api_key=api_key,
            db_path=db_path,
            timeout=10,
            max_retries=2,
            retry_delay=2.0
        )
        
        # Setup database session for VegasLine table
        engine = create_engine(f'sqlite:///{db_path}')
        Session = sessionmaker(bind=engine)
        self.db_session = Session()
    
    def fetch_nfl_odds(
        self,
        markets: str = "spreads,totals",
        regions: str = "us",
        odds_format: str = "american",
        use_cache: bool = True,
        cache_ttl_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Fetch NFL odds from The Odds API.
        
        Args:
            markets: Comma-separated markets (spreads, totals, h2h)
            regions: Comma-separated regions (us, uk, eu, au)
            odds_format: Odds format (american, decimal, fractional)
            use_cache: If True, check database cache first
            cache_ttl_hours: Cache time-to-live in hours
            
        Returns:
            List of game odds with spreads, totals, and ITT calculations
            
        Example response:
            [
                {
                    'game_id': 'nfl_gb_chi_2025_wk1',
                    'home_team': 'Green Bay Packers',
                    'away_team': 'Chicago Bears',
                    'commence_time': '2025-09-10T18:15:00Z',
                    'spread_home': -3.5,
                    'spread_away': 3.5,
                    'total': 45.5,
                    'itt_home': 24.5,  # (45.5 / 2) + (3.5 / 2)
                    'itt_away': 21.0   # (45.5 / 2) - (3.5 / 2)
                }
            ]
        """
        # Check cache first
        if use_cache:
            cached_data = self._get_cached_odds(cache_ttl_hours)
            if cached_data:
                self.logger.info(f"Using cached odds data ({len(cached_data)} games)")
                return cached_data
        
        # Fetch fresh data from API
        self.logger.info("Fetching fresh odds data from The Odds API")
        
        params = {
            'sport': 'americanfootball_nfl',
            'regions': regions,
            'markets': markets,
            'oddsFormat': odds_format
        }
        
        try:
            response_data = self._make_request('sports/americanfootball_nfl/odds', params=params)
            
            # Parse response and calculate ITT
            parsed_games = self._parse_odds_response(response_data)
            
            # Store in database
            self._store_odds(parsed_games)
            
            self.logger.info(f"Fetched and stored {len(parsed_games)} games")
            return parsed_games
            
        except APIError as e:
            self.logger.error(f"Failed to fetch odds: {e}")
            # Try to return stale cache as fallback
            cached_data = self._get_cached_odds(cache_ttl_hours * 7)  # 7x TTL as emergency fallback
            if cached_data:
                self.logger.warning(f"Returning stale cached data ({len(cached_data)} games)")
                return cached_data
            raise
    
    def _parse_odds_response(self, response_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse raw odds API response and calculate ITT.
        
        Args:
            response_data: Raw response from The Odds API
            
        Returns:
            List of parsed game odds with ITT calculations
        """
        parsed_games = []
        
        for game in response_data:
            try:
                game_id = game.get('id', '')
                home_team = game.get('home_team', '')
                away_team = game.get('away_team', '')
                commence_time = game.get('commence_time', '')
                
                # Extract bookmaker data (use first available bookmaker)
                bookmakers = game.get('bookmakers', [])
                if not bookmakers:
                    self.logger.warning(f"No bookmakers for game {game_id}")
                    continue
                
                bookmaker = bookmakers[0]  # Use first bookmaker (usually consensus)
                markets = bookmaker.get('markets', [])
                
                # Extract spreads and totals
                spread_data = next((m for m in markets if m['key'] == 'spreads'), None)
                totals_data = next((m for m in markets if m['key'] == 'totals'), None)
                
                # Parse spread
                spread_home = None
                spread_away = None
                if spread_data:
                    outcomes = spread_data.get('outcomes', [])
                    for outcome in outcomes:
                        if outcome['name'] == home_team:
                            spread_home = outcome.get('point')
                        elif outcome['name'] == away_team:
                            spread_away = outcome.get('point')
                
                # Parse total
                total = None
                if totals_data:
                    outcomes = totals_data.get('outcomes', [])
                    if outcomes:
                        total = outcomes[0].get('point')  # Over/Under point is the same
                
                # Calculate ITT
                itt_home, itt_away = self._calculate_itt(total, spread_home)
                
                parsed_games.append({
                    'game_id': game_id,
                    'home_team': home_team,
                    'away_team': away_team,
                    'sport_key': game.get('sport_key', 'americanfootball_nfl'),
                    'commence_time': commence_time,
                    'spread_home': spread_home,
                    'spread_away': spread_away,
                    'total': total,
                    'itt_home': itt_home,
                    'itt_away': itt_away,
                    'last_update': datetime.now()
                })
                
            except Exception as e:
                self.logger.error(f"Error parsing game {game.get('id', 'unknown')}: {e}")
                continue
        
        return parsed_games
    
    def _calculate_itt(
        self,
        total: Optional[float],
        spread_home: Optional[float]
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Calculate Implied Team Total (ITT) for home and away teams.
        
        Formula:
        - When home is favored (negative spread): Home gets more points
        - Home Team ITT = (Total / 2) + (abs(Spread) / 2)
        - Away Team ITT = (Total / 2) - (abs(Spread) / 2)
        
        Example:
        - Total = 45.5, Home Spread = -3.5 (home favored)
        - Home ITT = 22.75 + 1.75 = 24.5
        - Away ITT = 22.75 - 1.75 = 21.0
        
        Args:
            total: Game total (over/under)
            spread_home: Home team spread (negative = favored)
            
        Returns:
            Tuple of (itt_home, itt_away)
        """
        if total is None or spread_home is None:
            return None, None
        
        # When home team has negative spread, they're favored (should get higher ITT)
        # Use absolute value to ensure correct direction
        spread_adjustment = abs(spread_home) / 2
        
        if spread_home < 0:
            # Home is favored (negative spread) - home gets MORE points
            itt_home = (total / 2) + spread_adjustment
            itt_away = (total / 2) - spread_adjustment
        else:
            # Away is favored (positive home spread) - away gets MORE points
            itt_home = (total / 2) - spread_adjustment
            itt_away = (total / 2) + spread_adjustment
        
        # Round to 1 decimal place
        itt_home = round(itt_home, 1)
        itt_away = round(itt_away, 1)
        
        return itt_home, itt_away
    
    def _calculate_nfl_week(self, commence_time_str: str) -> int:
        """
        Calculate NFL week from game start time.
        NFL 2025 season starts September 4, 2025.
        
        Args:
            commence_time_str: ISO format datetime string
            
        Returns:
            NFL week number (1-18)
        """
        try:
            # Parse the commence time
            game_date = datetime.fromisoformat(commence_time_str.replace('Z', '+00:00'))
            
            # NFL 2025 season start (Week 1 Thursday)
            season_start = datetime(2025, 9, 4, tzinfo=game_date.tzinfo)
            
            # Calculate weeks since start
            days_since_start = (game_date - season_start).days
            week = (days_since_start // 7) + 1
            
            # Clamp to valid range (1-18)
            return max(1, min(18, week))
        except Exception as e:
            self.logger.warning(f"Could not parse game date {commence_time_str}: {e}")
            return 1  # Default to week 1 if parsing fails
    
    def _store_odds(self, games: List[Dict[str, Any]]):
        """
        Store odds data in vegas_lines table.
        
        Args:
            games: List of parsed game odds
        """
        try:
            for game in games:
                # Calculate week from game start time
                week = self._calculate_nfl_week(game['commence_time'])
                # Check if game already exists (upsert)
                existing = self.db_session.query(VegasLine).filter_by(
                    week=week,
                    game_id=game['game_id']
                ).first()
                
                if existing:
                    # Update existing record
                    existing.home_spread = game['spread_home']
                    existing.away_spread = game['spread_away']
                    existing.total = game['total']
                    existing.home_itt = game['itt_home']
                    existing.away_itt = game['itt_away']
                    existing.fetched_at = datetime.now()
                else:
                    # Insert new record
                    vegas_line = VegasLine(
                        week=week,
                        game_id=game['game_id'],
                        home_team=game['home_team'],
                        away_team=game['away_team'],
                        home_spread=game['spread_home'],
                        away_spread=game['spread_away'],
                        total=game['total'],
                        home_itt=game['itt_home'],
                        away_itt=game['itt_away'],
                        fetched_at=datetime.now()
                    )
                    self.db_session.add(vegas_line)
            
            self.db_session.commit()
            self.logger.info(f"Stored {len(games)} games in database")
            
        except Exception as e:
            self.logger.error(f"Failed to store odds: {e}")
            self.db_session.rollback()
            raise
    
    def _get_cached_odds(self, cache_ttl_hours: int) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached odds from database if within TTL.
        
        Args:
            cache_ttl_hours: Cache time-to-live in hours
            
        Returns:
            List of cached game odds, or None if cache expired/empty
        """
        try:
            cutoff = datetime.now() - timedelta(hours=cache_ttl_hours)
            
            cached_lines = self.db_session.query(VegasLine).filter(
                VegasLine.fetched_at >= cutoff
            ).all()
            
            if not cached_lines:
                return None
            
            # Convert to dict format
            cached_games = []
            for line in cached_lines:
                cached_games.append({
                    'game_id': line.game_id,
                    'home_team': line.home_team,
                    'away_team': line.away_team,
                    'spread_home': line.home_spread,
                    'spread_away': line.away_spread,
                    'total': line.total,
                    'itt_home': line.home_itt,
                    'itt_away': line.away_itt,
                    'last_update': line.fetched_at
                })
            
            return cached_games
            
        except Exception as e:
            self.logger.error(f"Failed to get cached odds: {e}")
            return None
    
    def close(self):
        """Close database sessions."""
        super().close()
        try:
            self.db_session.close()
        except Exception as e:
            self.logger.error(f"Error closing db_session: {e}")

