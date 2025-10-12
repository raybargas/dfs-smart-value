"""
MySportsFeeds API client for injury reports.

API Documentation: https://www.mysportsfeeds.com/data-feeds/api-docs/
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import requests
from requests.auth import HTTPBasicAuth

from .base_client import BaseAPIClient, APIError
from ..database_models import InjuryReport


class MySportsFeedsClient(BaseAPIClient):
    """
    Client for MySportsFeeds API v2.1.
    
    IMPORTANT REQUIREMENTS:
    - Subscription must include the "DETAILED" addon for injury data
    - The injuries endpoint returns CURRENT injuries only (not historical)
    - Authentication uses HTTP Basic Auth (API Key as username, "MYSPORTSFEEDS" as password)
    
    Features:
    - Fetch NFL injury reports
    - Parse practice status and body part
    - Cache results in database (6-hour TTL)
    - Rate limit: varies by plan (free tier limited)
    
    API Documentation: https://www.mysportsfeeds.com/data-feeds/api-docs/
    """
    
    def __init__(self, api_key: str, db_path: str = "dfs_optimizer.db"):
        """
        Initialize MySportsFeeds client.
        
        Args:
            api_key: MySportsFeeds API key
            db_path: Path to SQLite database
        """
        super().__init__(
            api_name="mysportsfeeds",  # Lowercase for database constraint
            base_url="https://api.mysportsfeeds.com/v2.1/pull/nfl",
            api_key=api_key,
            db_path=db_path,
            timeout=10,
            max_retries=2,
            retry_delay=2.0
        )
        
        # Setup database session for InjuryReport table
        engine = create_engine(f'sqlite:///{db_path}')
        Session = sessionmaker(bind=engine)
        self.db_session = Session()
    
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
        
        # MySportsFeeds uses Basic Auth, not query params
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
                
                # Check for errors
                if response.status_code == 429:
                    from .base_client import RateLimitError
                    raise RateLimitError(f"Rate limit exceeded for {self.api_name}")
                
                if not response.ok:
                    error_msg = response.text
                    # Check for subscription/addon issues
                    if response.status_code == 401:
                        raise APIError(
                            f"Authentication failed (401): Check your API key in .env file"
                        )
                    elif response.status_code == 403:
                        raise APIError(
                            f"Access forbidden (403): Your subscription may not include the DETAILED addon required for injury data. "
                            f"Visit https://www.mysportsfeeds.com to upgrade your plan."
                        )
                    else:
                        raise APIError(
                            f"Client error {response.status_code}: {error_msg}"
                        )
                
                return response.json()
                
            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    self.logger.warning(f"Timeout, retrying in {delay}s")
                    time.sleep(delay)
                    continue
                else:
                    raise TimeoutError(f"Request timed out after {self.max_retries} attempts")
            
            except Exception as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    self.logger.warning(f"Error: {e}, retrying in {delay}s")
                    time.sleep(delay)
                    continue
                else:
                    raise
    
    def fetch_injuries(
        self,
        season: int = 2025,
        week: int = 6,
        use_cache: bool = True,
        cache_ttl_hours: int = 6,
        team: Optional[str] = None,
        position: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch NFL injury reports from MySportsFeeds API.
        
        NOTE: The injuries endpoint returns CURRENT injuries only, not historical.
        The season/week parameters are kept for database storage but not sent to API.
        
        Args:
            season: NFL season year (for database storage only)
            week: Week number (for database storage only)
            use_cache: If True, check database cache first
            cache_ttl_hours: Cache time-to-live in hours
            team: Optional team filter (e.g., "SF", "KC")
            position: Optional position filter (e.g., "QB", "RB")
            
        Returns:
            List of injury reports
            
        Example response:
            [
                {
                    'player_id': '12345',
                    'player_name': 'Christian McCaffrey',
                    'team': 'SF',
                    'injury_status': 'Questionable',
                    'practice_status': 'Limited Practice',
                    'body_part': 'Hamstring',
                    'injury_description': 'Hamstring strain',
                    'last_update': '2025-09-10T14:30:00'
                }
            ]
        """
        # Check cache first
        if use_cache:
            cached_data = self._get_cached_injuries(cache_ttl_hours)
            if cached_data:
                self.logger.info(f"Using cached injury data ({len(cached_data)} players)")
                return cached_data
        
        # Fetch fresh data from API
        self.logger.info("Fetching current NFL injuries from MySportsFeeds")
        
        # MySportsFeeds v2.1 injuries endpoint (for CURRENT injuries)
        # Endpoint: /injuries.json
        # Valid params: player, team, position, sort, offset, limit, force
        # This returns "A list of all currently injured players" - NOT historical data
        endpoint = 'injuries.json'
        params = {}
        
        # Add optional filters
        if team:
            params['team'] = team
        if position:
            params['position'] = position
        
        # Force fresh content (avoid 304 responses)
        params['force'] = 'true'
        
        self.logger.info(f"Requesting current injuries (will store as week {week})")
        if params:
            self.logger.info(f"Filters: {params}")
        
        try:
            response_data = self._make_request(endpoint, params=params)
            
            # Parse response
            parsed_injuries = self._parse_injuries_response(response_data, week=week)
            
            # Store in database with specified week
            self._store_injuries(parsed_injuries, week=week)
            
            self.logger.info(f"Fetched and stored {len(parsed_injuries)} injury reports")
            return parsed_injuries
            
        except APIError as e:
            self.logger.error(f"Failed to fetch injuries: {e}")
            # Try to return stale cache as fallback
            cached_data = self._get_cached_injuries(cache_ttl_hours * 4)  # 4x TTL as emergency fallback
            if cached_data:
                self.logger.warning(f"Returning stale cached data ({len(cached_data)} players)")
                return cached_data
            raise
    
    def _parse_injuries_response(self, response_data: Dict[str, Any], week: int = 1) -> List[Dict[str, Any]]:
        """
        Parse raw injury API response from MySportsFeeds v2.1 injuries endpoint.
        
        Args:
            response_data: Raw response from MySportsFeeds API
            week: Week number to associate with injuries (for database storage)
            
        Returns:
            List of parsed injury reports
        """
        parsed_injuries = []
        
        # MySportsFeeds v2.1 injuries endpoint format
        # response_data contains:
        # - 'players': [...] - array of currently injured players with currentInjury field
        # - 'lastUpdatedOn': timestamp of when data was last updated by MySportsFeeds
        
        # Log API data freshness
        api_last_updated = response_data.get('lastUpdatedOn', 'Unknown')
        if api_last_updated != 'Unknown':
            self.logger.info(f"MySportsFeeds injury data last updated: {api_last_updated}")
        
        # Get players array from the response
        players = response_data.get('players', [])
        
        if not players:
            # Fallback: try old format for backward compatibility
            references = response_data.get('references', {})
            players = references.get('playerReferences', [])
        
        self.logger.info(f"Processing {len(players)} total players from API response")
        
        # Iterate through ALL players and extract those with current injuries
        for full_player in players:
            try:
                # Check if player has a current injury
                current_injury = full_player.get('currentInjury')
                if not current_injury:
                    continue  # Skip players without current injuries
                
                # Get player ID
                player_id = str(full_player.get('id', ''))
                
                # Construct full name
                first_name = full_player.get('firstName', '')
                last_name = full_player.get('lastName', '')
                player_name = f"{first_name} {last_name}".strip()
                
                # Team abbreviation
                team_info = full_player.get('currentTeam')
                team = team_info.get('abbreviation', '') if team_info else ''
                
                # SKIP players without a current team (free agents, practice squad, etc.)
                # These players are not relevant for DFS purposes
                if not team:
                    self.logger.info(f"Skipping {player_name} - no current team (free agent/released)")
                    continue
                
                # Position
                position = full_player.get('primaryPosition', '')
                
                # Injury details from currentInjury
                playing_prob = current_injury.get('playingProbability', 'UNKNOWN')
                # Map MySportsFeeds status to common format
                status_map = {
                    'OUT': 'Out',
                    'QUESTIONABLE': 'Questionable',
                    'DOUBTFUL': 'Doubtful',
                    'PROBABLE': 'Probable',
                    'UNKNOWN': 'Unknown'
                }
                injury_status = status_map.get(playing_prob, playing_prob)
                
                body_part = current_injury.get('description', '')
                injury_description = body_part  # Use same value for both
                practice_status = ''  # MySportsFeeds doesn't provide practice status directly
                
                # Last update timestamp
                last_update = datetime.now()
                
                parsed_injuries.append({
                    'player_id': player_id,
                    'player_name': player_name,
                    'team': team,
                    'position': position,
                    'injury_status': injury_status,
                    'practice_status': practice_status,
                    'body_part': body_part,
                    'injury_description': injury_description,
                    'last_update': last_update,
                    'week': week  # Include week for database storage
                })
                
            except Exception as e:
                self.logger.error(f"Error parsing injury for player: {e}")
                continue
        
        # Log filtering summary
        total_processed = len(players)
        injuries_with_teams = len(parsed_injuries)
        filtered_out = total_processed - injuries_with_teams
        
        self.logger.info(f"Injury parsing complete: {injuries_with_teams} players with teams, {filtered_out} filtered (no team)")
        
        return parsed_injuries
    
    def _store_injuries(self, injuries: List[Dict[str, Any]], week: int = 1):
        """
        Store injury reports in injury_reports table.
        
        Args:
            injuries: List of parsed injury reports
            week: Week number to associate with injuries
        """
        try:
            # Use provided week or extract from injury data
            if not week and injuries:
                week = injuries[0].get('week', 1)
            elif not week:
                week = 1
            
            for injury in injuries:
                # Check if player injury already exists (upsert)
                existing = self.db_session.query(InjuryReport).filter_by(
                    week=week,
                    player_name=injury['player_name'],
                    team=injury['team']
                ).first()
                
                if existing:
                    # Update existing record
                    existing.position = injury.get('position', '')
                    existing.injury_status = injury['injury_status']
                    existing.practice_status = injury['practice_status']
                    existing.body_part = injury['body_part']
                    existing.description = injury['injury_description']
                    existing.updated_at = datetime.now()
                else:
                    # Insert new record
                    injury_report = InjuryReport(
                        week=week,
                        player_name=injury['player_name'],
                        team=injury['team'],
                        position=injury.get('position', ''),
                        injury_status=injury['injury_status'],
                        practice_status=injury['practice_status'],
                        body_part=injury['body_part'],
                        description=injury['injury_description'],
                        updated_at=datetime.now()
                    )
                    self.db_session.add(injury_report)
            
            self.db_session.commit()
            self.logger.info(f"Stored {len(injuries)} injury reports in database")
            
        except Exception as e:
            self.logger.error(f"Failed to store injuries: {e}")
            self.db_session.rollback()
            raise
    
    def _get_cached_injuries(self, cache_ttl_hours: int) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached injury reports from database if within TTL.
        
        Args:
            cache_ttl_hours: Cache time-to-live in hours
            
        Returns:
            List of cached injury reports, or None if cache expired/empty
        """
        try:
            cutoff = datetime.now() - timedelta(hours=cache_ttl_hours)
            
            cached_reports = self.db_session.query(InjuryReport).filter(
                InjuryReport.updated_at >= cutoff
            ).all()
            
            if not cached_reports:
                return None
            
            # Convert to dict format
            cached_injuries = []
            for report in cached_reports:
                cached_injuries.append({
                    'player_name': report.player_name,
                    'team': report.team,
                    'position': report.position,
                    'injury_status': report.injury_status,
                    'practice_status': report.practice_status,
                    'body_part': report.body_part,
                    'injury_description': report.description,
                    'last_update': report.updated_at
                })
            
            return cached_injuries
            
        except Exception as e:
            self.logger.error(f"Failed to get cached injuries: {e}")
            return None
    
    def close(self):
        """Close database sessions."""
        super().close()
        try:
            self.db_session.close()
        except Exception as e:
            self.logger.error(f"Error closing db_session: {e}")

