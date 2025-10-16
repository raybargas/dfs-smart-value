"""
MySportsFeeds DFS Salaries API Client

Fetches DraftKings and FanDuel salary data for NFL players.

API Documentation: https://www.mysportsfeeds.com/data-feeds/api-docs/
Endpoint: /daily_dfs.json or /week/{week}/dfs.json

REQUIREMENTS:
- Subscription must include the "DFS" addon
- Authentication uses HTTP Basic Auth (API Key as username, "MYSPORTSFEEDS" as password)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import requests
from requests.auth import HTTPBasicAuth

from .base_client import BaseAPIClient, APIError, RateLimitError, TimeoutError


class DFSSalariesAPIClient(BaseAPIClient):
    """
    Client for MySportsFeeds DFS Salaries API.
    
    Fetches DraftKings and FanDuel salary data for NFL players.
    
    Features:
    - Fetch current week salaries (DK, FD, or both)
    - Fetch historical salaries for backtesting
    - Parse and format salary data into DataFrame
    - Cache results in database (24-hour TTL)
    - Support multiple DFS sites
    
    Supported Sites:
    - DraftKings ('draftkings')
    - FanDuel ('fanduel')
    - FantasyDraft ('fantasydraft')
    - Yahoo ('yahoo')
    """
    
    # Supported DFS sites
    SUPPORTED_SITES = ['draftkings', 'fanduel', 'fantasydraft', 'yahoo']
    
    def __init__(self, api_key: str, db_path: str = "dfs_optimizer.db"):
        """
        Initialize DFS Salaries API client.
        
        Args:
            api_key: MySportsFeeds API key
            db_path: Path to SQLite database
        """
        super().__init__(
            api_name="mysportsfeeds_dfs",
            base_url="https://api.mysportsfeeds.com/v2.1/pull/nfl",
            api_key=api_key,
            db_path=db_path,
            timeout=30,  # Increased for large responses (490+ players, 33+ slates)
            max_retries=3,
            retry_delay=2.0
        )
        
        # Setup database session
        engine = create_engine(f'sqlite:///{db_path}')
        Session = sessionmaker(bind=engine)
        self.db_session = Session()
        
        # Cache for API responses
        self._cache = {}
        self._cache_ttl = timedelta(hours=24)
    
    def _make_request(
        self,
        endpoint: str,
        method: str = 'GET',
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Override base class to use Basic Auth for MySportsFeeds.
        
        MySportsFeeds uses HTTP Basic Auth:
        - Username: API Key
        - Password: "MYSPORTSFEEDS"
        """
        import time
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # MySportsFeeds uses Basic Auth
        auth = HTTPBasicAuth(self.api_key, "MYSPORTSFEEDS") if self.api_key else None
        
        # Attempt request with retries
        for attempt in range(self.max_retries):
            start_time = time.time()
            
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=headers,
                    json=data,
                    auth=auth,
                    timeout=self.timeout
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Log API call
                self._log_api_call(
                    endpoint=endpoint,
                    response_status=response.status_code,
                    response_size_kb=len(response.content) / 1024,
                    duration_ms=duration_ms,
                    error_message=None if response.ok else response.text[:500]
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    raise RateLimitError(f"Rate limit exceeded for {self.api_name}")
                
                # Handle authentication errors
                if response.status_code == 401:
                    raise APIError(
                        f"Authentication failed (401): Check your MYSPORTSFEEDS_API_KEY in .env file"
                    )
                
                # Handle subscription/addon issues
                if response.status_code == 403:
                    raise APIError(
                        f"Access forbidden (403): Your subscription may not include the DFS addon required for salary data. "
                        f"Visit https://www.mysportsfeeds.com to upgrade your plan."
                    )
                
                # Handle not found errors
                if response.status_code == 404:
                    raise APIError(
                        f"Not found (404): The requested data may not be available yet. "
                        f"Endpoint: {endpoint}"
                    )
                
                # Handle other errors
                if not response.ok:
                    raise APIError(
                        f"API error {response.status_code}: {response.text[:500]}"
                    )
                
                return response.json()
                
            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    self.logger.warning(f"Timeout, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    raise TimeoutError(f"Request timed out after {self.max_retries} attempts")
            
            except (APIError, RateLimitError):
                # Don't retry these errors
                raise
            
            except Exception as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    self.logger.warning(f"Error: {e}, retrying in {delay}s")
                    time.sleep(delay)
                    continue
                else:
                    raise APIError(f"Request failed: {e}")
        
        # Should not reach here
        raise APIError("Max retries exceeded")
    
    def fetch_current_week_salaries(
        self,
        week: int,
        season: str = '2024',
        site: str = 'draftkings',
        slate_type: str = 'classic',
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch current week DFS salaries.
        
        Note: MySportsFeeds "current" keyword doesn't work reliably, so we require
        explicit week and season parameters.
        
        Args:
            week: Week number (1-18)
            season: Season year (e.g., '2024') or full season string
            site: DFS site ('draftkings', 'fanduel', etc.)
            slate_type: Slate type ('classic', 'showdown', etc.) - for cache key only
            use_cache: Whether to use cached results
            
        Returns:
            DataFrame with columns: player_id, player_name, position, team, 
                                   opponent, salary, projection (if available)
        
        Raises:
            APIError: If API request fails
            ValueError: If site not supported or invalid week
        """
        # Validate site
        site = site.lower()
        if site not in self.SUPPORTED_SITES:
            raise ValueError(
                f"Unsupported site '{site}'. Must be one of: {', '.join(self.SUPPORTED_SITES)}"
            )
        
        # Validate week
        if not 1 <= week <= 18:
            raise ValueError(f"Invalid week {week}. Must be between 1 and 18.")
        
        # Check cache
        cache_key = f"{season}_week{week}_{site}_{slate_type}"
        if use_cache and cache_key in self._cache:
            cached_data, cached_at = self._cache[cache_key]
            if datetime.now() - cached_at < self._cache_ttl:
                self.logger.info(f"Using cached data for {site} Week {week} (cached {cached_at})")
                return cached_data
        
        # Extract year from season
        year = season.split('-')[0]  # Handle both "2024" and "2024-2025-regular"
        
        # Fetch from API
        endpoint = f"{year}-regular/week/{week}/dfs.json"
        params = {'dfstype': site}  # Filter by DFS site
        self.logger.info(f"Fetching Week {week} salaries from MySportsFeeds for {site}...")
        
        try:
            response_data = self._make_request(endpoint, params=params)
            
            # Parse response
            df = self._parse_dfs_response(response_data, site)
            
            # Cache result
            self._cache[cache_key] = (df, datetime.now())
            
            self.logger.info(f"✅ Fetched {len(df)} players for {site}")
            return df
            
        except APIError as e:
            self.logger.error(f"Failed to fetch salaries: {e}")
            raise
    
    def fetch_historical_salaries(
        self,
        season: str = '2024-2025-regular',
        week: int = 10,
        site: str = 'draftkings'
    ) -> pd.DataFrame:
        """
        Fetch historical DFS salaries for a specific week.
        
        Used for backtesting - load exact salaries from past weeks.
        
        Args:
            season: Season string (e.g., '2024-2025-regular' or '2024')
            week: Week number (1-18)
            site: DFS site ('draftkings', 'fanduel', etc.)
            
        Returns:
            DataFrame with columns: player_id, player_name, position, team,
                                   opponent, salary, projection (if available)
        
        Raises:
            APIError: If API request fails
            ValueError: If site not supported or invalid week
        """
        # Validate site
        site = site.lower()
        if site not in self.SUPPORTED_SITES:
            raise ValueError(
                f"Unsupported site '{site}'. Must be one of: {', '.join(self.SUPPORTED_SITES)}"
            )
        
        # Validate week
        if not 1 <= week <= 18:
            raise ValueError(f"Invalid week {week}. Must be between 1 and 18.")
        
        # Extract year from season (MySportsFeeds wants "2024-regular", not "2024-2025-regular")
        year = season.split('-')[0]  # "2024-2025-regular" → "2024"
        
        # Construct endpoint
        endpoint = f"{year}-regular/week/{week}/dfs.json"
        params = {'dfstype': site}  # Filter by DFS site
        self.logger.info(f"Fetching historical salaries for {year} Week {week} ({site})...")
        
        try:
            response_data = self._make_request(endpoint, params=params)
            
            # Parse response
            df = self._parse_dfs_response(response_data, site)
            
            self.logger.info(f"✅ Fetched {len(df)} players for Week {week}")
            return df
            
        except APIError as e:
            self.logger.error(f"Failed to fetch historical salaries: {e}")
            raise
    
    def _parse_dfs_response(
        self,
        response_data: Dict[str, Any],
        site: str = 'draftkings'
    ) -> pd.DataFrame:
        """
        Parse MySportsFeeds DFS API response into a DataFrame.
        
        Correct response structure (as of 2025-10-16):
            response['sources'][0]['slates'][i]['players']
        
        Args:
            response_data: Raw JSON response from API
            site: DFS site name (for tagging)
            
        Returns:
            DataFrame with standardized columns:
                - player_id: MySportsFeeds player ID (can be None for DST)
                - player_name: Full player name
                - position: Position (QB, RB, WR, TE, DST)
                - team: Team abbreviation
                - opponent: Opponent team abbreviation
                - salary: DFS salary
                - projection: Projected fantasy points (0.0 if None)
                - site: DFS site name
                - slate_type: Slate type/label
            
        Raises:
            APIError: If response format is invalid
        """
        players = []
        
        # Navigate to player data
        if 'sources' not in response_data:
            self.logger.warning("No 'sources' found in response")
            return pd.DataFrame(columns=[
                'player_id', 'player_name', 'position', 'team',
                'opponent', 'salary', 'projection'
            ])
        
        # Iterate through sources (usually just one: DraftKings or FanDuel)
        for source in response_data.get('sources', []):
            source_name = source.get('source', 'Unknown')
            
            if 'slates' not in source:
                self.logger.warning(f"No slates found in source '{source_name}'")
                continue
            
            # Iterate through slates (Featured, Classic, Showdown, etc.)
            for slate in source.get('slates', []):
                slate_label = slate.get('label', 'Unknown')
                slate_type = slate.get('type', 'Classic').lower()
                slate_week = slate.get('forWeek')
                
                if 'players' not in slate:
                    self.logger.warning(f"No players in slate '{slate_label}'")
                    continue
                
                # Iterate through players
                for player in slate.get('players', []):
                    # Extract player info
                    first_name = player.get('sourceFirstName', '')
                    last_name = player.get('sourceLastName', '')
                    
                    # Build player name
                    if last_name:
                        player_name = f"{first_name} {last_name}".strip()
                    else:
                        # For DST, only sourceFirstName is set (e.g., "Broncos")
                        player_name = first_name.strip()
                    
                    # Skip if no valid name
                    if not player_name:
                        continue
                    
                    # Get MySportsFeeds player ID (can be None for DST)
                    player_obj = player.get('player')
                    player_id = player_obj.get('id') if player_obj else None
                    
                    # Get position
                    position = player.get('sourcePosition', '')
                    
                    # Get team (try sourceTeam first, then team.abbreviation)
                    team = player.get('sourceTeam')
                    if not team and 'team' in player:
                        team = player['team'].get('abbreviation', '')
                    
                    # Get salary (required field)
                    salary = player.get('salary')
                    if salary is None:
                        continue  # Skip players without salary
                    
                    # Get projection (can be null)
                    projection = player.get('fantasyPoints')
                    
                    # Get opponent from game info
                    opponent = None
                    game = player.get('game')
                    if game:
                        away_team = game.get('awayTeamAbbreviation')
                        home_team = game.get('homeTeamAbbreviation')
                        
                        if team == away_team:
                            opponent = home_team
                        elif team == home_team:
                            opponent = away_team
                    
                    players.append({
                        'player_id': player_id,
                        'player_name': player_name,
                        'position': position,
                        'team': team,
                        'opponent': opponent,
                        'salary': salary,
                        'projection': projection if projection is not None else 0.0,
                        'site': site,
                        'slate_type': slate_type,
                        'slate_label': slate_label,
                        'week': slate_week
                    })
        
        if not players:
            self.logger.warning("No players found in DFS response")
            return pd.DataFrame(columns=[
                'player_id', 'player_name', 'position', 'team',
                'opponent', 'salary', 'projection'
            ])
        
        df = pd.DataFrame(players)
        
        # Clean up data types
        df['salary'] = pd.to_numeric(df['salary'], errors='coerce')
        df['projection'] = pd.to_numeric(df['projection'], errors='coerce').fillna(0.0)
        
        self.logger.info(f"Parsed {len(df)} players from {len(df['slate_label'].unique())} slates")
        
        return df
    
    def get_supported_sites(self) -> List[str]:
        """
        Get list of supported DFS sites.
        
        Returns:
            List of supported site names
        """
        return self.SUPPORTED_SITES.copy()
    
    def close(self):
        """Close database session."""
        try:
            self.db_session.close()
            super().close()
        except Exception as e:
            self.logger.error(f"Error closing session: {e}")


# Convenience function
def fetch_salaries(
    api_key: str,
    week: int,
    site: str = 'draftkings',
    season: str = '2024',
    db_path: str = "dfs_optimizer.db"
) -> pd.DataFrame:
    """
    Convenience function to fetch DFS salaries.
    
    Note: MySportsFeeds "current" keyword doesn't work, so week is required.
    
    Args:
        api_key: MySportsFeeds API key
        week: Week number (1-18, required)
        site: DFS site ('draftkings', 'fanduel', etc.)
        season: Season year (e.g., '2024') or full season string
        db_path: Path to SQLite database
        
    Returns:
        DataFrame with salary data
    
    Example:
        # Week 7 salaries
        df = fetch_salaries(api_key, week=7, site='draftkings')
        
        # Historical week (same method now)
        df = fetch_salaries(api_key, week=6, site='fanduel', season='2024')
    """
    client = DFSSalariesAPIClient(api_key, db_path)
    
    try:
        # All fetches use the same method now (historical = current with explicit week)
        return client.fetch_historical_salaries(season=season, week=week, site=site)
    finally:
        client.close()

