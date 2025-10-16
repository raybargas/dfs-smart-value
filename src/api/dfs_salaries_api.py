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
            timeout=15,
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
        site: str = 'draftkings',
        slate_type: str = 'classic',
        use_cache: bool = True
    ) -> pd.DataFrame:
        """
        Fetch current week DFS salaries.
        
        Args:
            site: DFS site ('draftkings', 'fanduel', etc.)
            slate_type: Slate type ('classic', 'showdown', etc.)
            use_cache: Whether to use cached results
            
        Returns:
            DataFrame with columns: player_id, player_name, position, team, 
                                   opponent, salary, projection (if available)
        
        Raises:
            APIError: If API request fails
            ValueError: If site not supported
        """
        # Validate site
        site = site.lower()
        if site not in self.SUPPORTED_SITES:
            raise ValueError(
                f"Unsupported site '{site}'. Must be one of: {', '.join(self.SUPPORTED_SITES)}"
            )
        
        # Check cache
        cache_key = f"current_{site}_{slate_type}"
        if use_cache and cache_key in self._cache:
            cached_data, cached_at = self._cache[cache_key]
            if datetime.now() - cached_at < self._cache_ttl:
                self.logger.info(f"Using cached data for {site} (cached {cached_at})")
                return cached_data
        
        # Fetch from API
        endpoint = "daily_dfs.json"
        self.logger.info(f"Fetching current week salaries from MySportsFeeds for {site}...")
        
        try:
            response_data = self._make_request(endpoint)
            
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
            season: Season string (e.g., '2024-2025-regular')
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
        
        # Construct endpoint
        endpoint = f"{season}/week/{week}/dfs.json"
        self.logger.info(f"Fetching historical salaries for {season} Week {week} ({site})...")
        
        try:
            response_data = self._make_request(endpoint)
            
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
        Parse MySportsFeeds DFS API response into DataFrame.
        
        Response structure:
        {
            "lastUpdatedOn": "2024-10-15T10:30:00.000Z",
            "dfsPlayers": [
                {
                    "dfsSource": "DRAFTKINGS",
                    "player": {
                        "id": 12345,
                        "firstName": "Patrick",
                        "lastName": "Mahomes",
                        "position": "QB",
                        "currentTeam": {"abbreviation": "KC"}
                    },
                    "salary": 8500,
                    "fantasyPointsProjection": 24.5
                },
                ...
            ]
        }
        
        Args:
            response_data: Raw API response
            site: DFS site to filter by
            
        Returns:
            DataFrame with parsed player data
        """
        # Get dfsPlayers array
        dfs_players = response_data.get('dfsPlayers', [])
        
        if not dfs_players:
            self.logger.warning("No DFS players found in response")
            return pd.DataFrame(columns=[
                'player_id', 'player_name', 'position', 'team',
                'opponent', 'salary', 'projection'
            ])
        
        # Map site names (API uses uppercase)
        site_map = {
            'draftkings': 'DRAFTKINGS',
            'fanduel': 'FANDUEL',
            'fantasydraft': 'FANTASYDRAFT',
            'yahoo': 'YAHOO'
        }
        api_site_name = site_map.get(site.lower(), site.upper())
        
        # Parse players
        parsed_players = []
        for dfs_player in dfs_players:
            # Skip if wrong site
            if dfs_player.get('dfsSource') != api_site_name:
                continue
            
            player = dfs_player.get('player', {})
            team_info = player.get('currentTeam', {})
            
            # Build player record
            player_record = {
                'player_id': str(player.get('id', '')),
                'player_name': f"{player.get('firstName', '')} {player.get('lastName', '')}".strip(),
                'position': player.get('position', ''),
                'team': team_info.get('abbreviation', ''),
                'opponent': '',  # Not provided in DFS endpoint, need to join with schedule
                'salary': dfs_player.get('salary', 0),
                'projection': dfs_player.get('fantasyPointsProjection')
            }
            
            parsed_players.append(player_record)
        
        # Create DataFrame
        df = pd.DataFrame(parsed_players)
        
        # Convert salary to integer
        if not df.empty:
            df['salary'] = df['salary'].astype(int)
            
            # Handle DST naming (change from "DEN" to "Broncos D/ST" or similar)
            # This maintains consistency with manual uploads
            
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
    site: str = 'draftkings',
    week: Optional[int] = None,
    season: str = '2024-2025-regular',
    db_path: str = "dfs_optimizer.db"
) -> pd.DataFrame:
    """
    Convenience function to fetch DFS salaries.
    
    Args:
        api_key: MySportsFeeds API key
        site: DFS site ('draftkings', 'fanduel', etc.)
        week: Week number for historical data (None = current week)
        season: Season string (only used if week provided)
        db_path: Path to SQLite database
        
    Returns:
        DataFrame with salary data
    
    Example:
        # Current week
        df = fetch_salaries(api_key, site='draftkings')
        
        # Historical week
        df = fetch_salaries(api_key, site='draftkings', week=10)
    """
    client = DFSSalariesAPIClient(api_key, db_path)
    
    try:
        if week is None:
            return client.fetch_current_week_salaries(site=site)
        else:
            return client.fetch_historical_salaries(season=season, week=week, site=site)
    finally:
        client.close()

