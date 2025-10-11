"""
MySportsFeeds Boxscore API Client

Fetches historical game boxscores and player stats from MySportsFeeds v2.1.
Focus: Current season, recent weeks only (80/20 rule).

API Documentation: https://www.mysportsfeeds.com/data-feeds/api-docs/
Endpoint: /pull/nfl/{season}/games/{game}/boxscore.json
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import requests
from requests.auth import HTTPBasicAuth

from .base_client import BaseAPIClient, APIError
from ..database_models import create_session


class BoxscoreAPIClient(BaseAPIClient):
    """
    Client for MySportsFeeds Boxscore API.
    
    IMPORTANT REQUIREMENTS:
    - Subscription must include the "DETAILED" addon
    - Game ID format: YYYYMMDD-AWAY-HOME (e.g., "20241006-KC-NO")
    - Season format: "2024-2025-regular" or "2024-playoff"
    
    Features:
    - Fetch game boxscores by game ID
    - Fetch all games for a specific week
    - Parse player and team statistics
    - Store in database for historical analysis
    """
    
    def __init__(self, api_key: str, db_path: str = "dfs_optimizer.db"):
        """
        Initialize BoxscoreAPI client.
        
        Args:
            api_key: MySportsFeeds API key
            db_path: Path to SQLite database
        """
        super().__init__(
            api_name="mysportsfeeds",
            base_url="https://api.mysportsfeeds.com/v2.1/pull/nfl",
            api_key=api_key,
            db_path=db_path,
            timeout=30,  # Boxscores can be large
            max_retries=2,
            retry_delay=2.0
        )
        
        # Setup database session for storing boxscores
        self.db_path = db_path
        self.db_session = create_session(db_path)
    
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
                
                # Check for errors
                if response.status_code == 429:
                    from .base_client import RateLimitError
                    raise RateLimitError(f"Rate limit exceeded for {self.api_name}")
                
                if response.status_code == 404:
                    raise APIError(f"Game not found (404): {endpoint}")
                
                if response.status_code == 401:
                    raise APIError(f"Authentication failed (401): Check your API key")
                
                if response.status_code == 403:
                    raise APIError(
                        f"Access forbidden (403): Your subscription may not include the DETAILED addon. "
                        f"Visit https://www.mysportsfeeds.com to upgrade."
                    )
                
                if not response.ok:
                    raise APIError(f"Error {response.status_code}: {response.text[:200]}")
                
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
    
    def fetch_weekly_schedule(
        self,
        season: str = "2024-regular",
        week: int = 6
    ) -> List[str]:
        """
        Get list of game IDs for a specific week.
        
        This is a helper to get the games we need to fetch boxscores for.
        Uses the weekly schedule endpoint to get game IDs.
        
        Args:
            season: Season identifier (e.g., "2024-2025-regular")
            week: Week number (1-18)
            
        Returns:
            List of game IDs in format YYYYMMDD-AWAY-HOME
        """
        endpoint = f"{season}/week/{week}/games.json"
        params = {'force': 'true'}
        
        self.logger.info(f"Fetching schedule for {season} week {week}")
        
        try:
            response_data = self._make_request(endpoint, params=params)
            
            games = response_data.get('games', [])
            game_ids = []
            
            for game in games:
                schedule = game.get('schedule', {})
                away_team = schedule.get('awayTeam', {}).get('abbreviation', '')
                home_team = schedule.get('homeTeam', {}).get('abbreviation', '')
                start_time = schedule.get('startTime', '')
                
                # Extract date from startTime (format: 2024-10-06T13:00:00.000Z)
                if start_time and away_team and home_team:
                    date_str = start_time.split('T')[0].replace('-', '')  # YYYYMMDD
                    game_id = f"{date_str}-{away_team}-{home_team}"
                    game_ids.append(game_id)
            
            self.logger.info(f"Found {len(game_ids)} games for week {week}")
            return game_ids
            
        except Exception as e:
            self.logger.error(f"Failed to fetch schedule: {e}")
            return []
    
    def fetch_boxscore(
        self,
        game_id: str,
        season: str = "2024-regular"
    ) -> Dict[str, Any]:
        """
        Fetch boxscore for a single game.
        
        Args:
            game_id: Game ID in format YYYYMMDD-AWAY-HOME (e.g., "20241006-KC-NO")
            season: Season identifier (e.g., "2024-2025-regular")
            
        Returns:
            Dict containing parsed game and player stats
            
        Example:
            client.fetch_boxscore("20241006-KC-NO", "2024-2025-regular")
        """
        endpoint = f"{season}/games/{game_id}/boxscore.json"
        params = {
            'force': 'true'
            # Note: Don't specify playerstats/teamstats - returns all stats by default
        }
        
        self.logger.info(f"Fetching boxscore for game {game_id}")
        
        try:
            response_data = self._make_request(endpoint, params=params)
            
            # Parse the boxscore
            parsed_data = self._parse_boxscore(response_data, game_id, season)
            
            self.logger.info(f"Successfully fetched boxscore for {game_id}")
            return parsed_data
            
        except APIError as e:
            self.logger.error(f"Failed to fetch boxscore for {game_id}: {e}")
            raise
    
    def fetch_week_boxscores(
        self,
        season: str = "2024-regular",
        week: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Fetch all boxscores for a specific week.
        
        This is the main method you'll use to get last week's data.
        
        Args:
            season: Season identifier
            week: Week number
            
        Returns:
            List of parsed boxscore data
        """
        self.logger.info(f"Fetching all boxscores for {season} week {week}")
        
        # Get schedule first
        game_ids = self.fetch_weekly_schedule(season, week)
        
        if not game_ids:
            self.logger.warning(f"No games found for week {week}")
            return []
        
        # Fetch each boxscore
        boxscores = []
        for i, game_id in enumerate(game_ids, 1):
            try:
                self.logger.info(f"Fetching game {i}/{len(game_ids)}: {game_id}")
                boxscore = self.fetch_boxscore(game_id, season)
                boxscores.append(boxscore)
                
                # Small delay to avoid rate limiting
                if i < len(game_ids):
                    import time
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Failed to fetch {game_id}: {e}")
                continue
        
        self.logger.info(f"Successfully fetched {len(boxscores)}/{len(game_ids)} boxscores")
        return boxscores
    
    def _parse_boxscore(
        self,
        response_data: Dict[str, Any],
        game_id: str,
        season: str
    ) -> Dict[str, Any]:
        """
        Parse boxscore response into structured data.
        
        Returns dict with:
        - game_info: Game-level data
        - player_stats: List of player stat dicts
        - team_stats: List of team stat dicts
        """
        game_info = {
            'game_id': game_id,
            'season': season,
            'player_stats': [],
            'team_stats': []
        }
        
        # Parse game-level info
        game = response_data.get('game', {})
        
        game_info['game_date'] = game.get('startTime', '').split('T')[0]
        game_info['home_team'] = game.get('homeTeam', {}).get('abbreviation', '')
        game_info['away_team'] = game.get('awayTeam', {}).get('abbreviation', '')
        game_info['week'] = game.get('week', 0)
        
        # Get final score by summing all quarters
        scoring_quarters = response_data.get('scoring', {}).get('quarters', [])
        game_info['away_score'] = sum(q.get('awayScore', 0) for q in scoring_quarters)
        game_info['home_score'] = sum(q.get('homeScore', 0) for q in scoring_quarters)
        
        # Parse player stats from stats.away.players and stats.home.players
        stats = response_data.get('stats', {})
        
        # Get stats from both teams
        for team_key in ['away', 'home']:
            team_abbr = game_info['away_team'] if team_key == 'away' else game_info['home_team']
            team_players = stats.get(team_key, {}).get('players', [])
            
            for player_entry in team_players:
                player_info = player_entry.get('player', {})
                player_stats_list = player_entry.get('playerStats', [])
                
                # Get the first playerStats entry (there's usually only one)
                player_stats = player_stats_list[0] if player_stats_list else {}
                
                player_data = {
                    'game_id': game_id,
                    'player_id': str(player_info.get('id', '')),
                    'player_name': f"{player_info.get('firstName', '')} {player_info.get('lastName', '')}".strip(),
                    'team': team_abbr,
                    'position': player_info.get('position', ''),
                    
                    # Passing
                    'pass_attempts': player_stats.get('passing', {}).get('passAttempts', 0),
                    'pass_completions': player_stats.get('passing', {}).get('passCompletions', 0),
                    'pass_yards': player_stats.get('passing', {}).get('passYards', 0),
                    'pass_touchdowns': player_stats.get('passing', {}).get('passTD', 0),
                    'pass_interceptions': player_stats.get('passing', {}).get('passInt', 0),
                    
                    # Rushing
                    'rush_attempts': player_stats.get('rushing', {}).get('rushAttempts', 0),
                    'rush_yards': player_stats.get('rushing', {}).get('rushYards', 0),
                    'rush_touchdowns': player_stats.get('rushing', {}).get('rushTD', 0),
                    
                    # Receiving
                    'targets': player_stats.get('receiving', {}).get('targets', 0),
                    'receptions': player_stats.get('receiving', {}).get('receptions', 0),
                    'receiving_yards': player_stats.get('receiving', {}).get('recYards', 0),
                    'receiving_touchdowns': player_stats.get('receiving', {}).get('recTD', 0),
                }
                
                game_info['player_stats'].append(player_data)
        
        return game_info
    
    def store_boxscore(self, boxscore_data: Dict[str, Any]) -> bool:
        """
        Store boxscore data in the database.
        
        Args:
            boxscore_data: Parsed boxscore dict from fetch_boxscore
            
        Returns:
            bool: True if successful
        """
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Store game info
            cursor.execute("""
                INSERT OR REPLACE INTO game_boxscores 
                (game_id, season, week, game_date, home_team, away_team, home_score, away_score, game_status, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'final', CURRENT_TIMESTAMP)
            """, (
                boxscore_data['game_id'],
                boxscore_data['season'],
                boxscore_data['week'],
                boxscore_data['game_date'],
                boxscore_data['home_team'],
                boxscore_data['away_team'],
                boxscore_data['home_score'],
                boxscore_data['away_score']
            ))
            
            # Store player stats
            for player in boxscore_data['player_stats']:
                cursor.execute("""
                    INSERT OR REPLACE INTO player_game_stats
                    (game_id, player_id, player_name, team, position,
                     pass_attempts, pass_completions, pass_yards, pass_touchdowns, pass_interceptions,
                     rush_attempts, rush_yards, rush_touchdowns,
                     targets, receptions, receiving_yards, receiving_touchdowns,
                     fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    player['game_id'],
                    player['player_id'],
                    player['player_name'],
                    player['team'],
                    player['position'],
                    player['pass_attempts'],
                    player['pass_completions'],
                    player['pass_yards'],
                    player['pass_touchdowns'],
                    player['pass_interceptions'],
                    player['rush_attempts'],
                    player['rush_yards'],
                    player['rush_touchdowns'],
                    player['targets'],
                    player['receptions'],
                    player['receiving_yards'],
                    player['receiving_touchdowns']
                ))
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Stored {len(boxscore_data['player_stats'])} player stats for game {boxscore_data['game_id']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store boxscore: {e}")
            return False
    
    def close(self):
        """Close database session."""
        super().close()
        try:
            if hasattr(self, 'db_session'):
                self.db_session.close()
        except Exception as e:
            self.logger.error(f"Error closing db_session: {e}")


if __name__ == "__main__":
    # Quick test
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
    if api_key:
        client = BoxscoreAPIClient(api_key=api_key)
        
        # Test: Get last week's schedule
        print("Testing schedule fetch...")
        games = client.fetch_weekly_schedule("2024-2025-regular", 5)
        print(f"Found {len(games)} games")
        for game in games[:3]:
            print(f"  - {game}")

