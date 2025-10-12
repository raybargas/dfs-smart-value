"""
ESPN API client for injury reports (unofficial public API).

ESPN's unofficial API provides fast, up-to-date injury information,
often faster than paid services for breaking news.

API Documentation (community): 
- Endpoint: https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries
- No authentication required
- Free to use (unofficial)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
import time

from .base_client import APIError


class ESPNAPIClient:
    """
    Client for ESPN's unofficial public API.
    
    Features:
    - Fetch NFL injury reports (all teams or specific team)
    - No authentication required
    - Often faster updates than paid APIs for breaking news
    - Free to use (but unofficial/unsupported)
    
    Note: This is an unofficial API - endpoints may change without notice.
    """
    
    def __init__(self):
        """Initialize ESPN API client."""
        self.base_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
        self.timeout = 10
        self.max_retries = 2
        self.retry_delay = 1.0
    
    def fetch_injuries(
        self,
        team: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch NFL injury reports from ESPN.
        
        Args:
            team: Optional team filter (e.g., 'ARI', 'KC')
        
        Returns:
            List of injury reports
            
        Example response:
            [
                {
                    'player_name': 'Kyler Murray',
                    'team': 'ARI',
                    'position': 'QB',
                    'injury_status': 'Out',
                    'body_part': 'Foot',
                    'injury_description': 'Foot',
                    'last_update': datetime object,
                    'source': 'ESPN'
                }
            ]
        """
        endpoint = f"{self.base_url}/injuries"
        params = {}
        
        if team:
            params['team'] = team.upper()
        
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                
                response = requests.get(
                    endpoint,
                    params=params,
                    timeout=self.timeout
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                if response.status_code == 200:
                    data = response.json()
                    parsed_injuries = self._parse_espn_response(data)
                    
                    print(f"✅ ESPN API: Fetched {len(parsed_injuries)} injuries in {duration_ms}ms")
                    return parsed_injuries
                    
                elif response.status_code == 404:
                    # No injury data available
                    return []
                    
                else:
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay * (2 ** attempt)
                        print(f"⚠️ ESPN API returned {response.status_code}, retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                    else:
                        raise APIError(f"ESPN API error {response.status_code}: {response.text[:200]}")
                        
            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    print(f"⚠️ ESPN API timeout, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    raise APIError("ESPN API request timed out after retries")
                    
            except Exception as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    print(f"⚠️ ESPN API error: {e}, retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    raise APIError(f"ESPN API error: {e}")
        
        return []
    
    def _parse_espn_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse ESPN injury API response.
        
        ESPN response format (actual):
        {
            "injuries": [
                {
                    "id": "22",
                    "displayName": "Arizona Cardinals",
                    "injuries": [
                        {
                            "id": "610356",
                            "status": "Active",
                            "athlete": {
                                "displayName": "Player Name",
                                "position": {...}
                            },
                            "details": {...}
                        }
                    ]
                }
            ]
        }
        """
        parsed_injuries = []
        
        teams = data.get('injuries', [])
        
        for team_data in teams:
            # Team info
            team_name = team_data.get('displayName', '')
            # Extract team abbreviation from team name (e.g., "Arizona Cardinals" -> "ARI")
            team_abbr = self._get_team_abbr(team_name)
            
            team_injuries = team_data.get('injuries', [])
            
            for injury in team_injuries:
                try:
                    # Player info from 'athlete' key
                    athlete = injury.get('athlete', {})
                    player_name = athlete.get('displayName', '')
                    
                    if not player_name:
                        continue
                    
                    # Position from athlete
                    position_info = athlete.get('position', {})
                    position = position_info.get('abbreviation', '') if position_info else ''
                    
                    # Injury status from top level
                    status = injury.get('status', 'Unknown')
                    
                    # Map ESPN status to standard format
                    status_map = {
                        'Out': 'Out',
                        'Questionable': 'Questionable',
                        'Doubtful': 'Doubtful',
                        'Day To Day': 'Questionable',
                        'Active': 'Questionable',  # Often means game-time decision
                        'IR': 'IR',
                        'Injured Reserve': 'IR',
                        'PUP': 'Out',
                        'NFI': 'Out'
                    }
                    injury_status = status_map.get(status, 'Questionable')
                    
                    # Injury details from 'details' or comments
                    details = injury.get('details', {})
                    body_part = details.get('type', '')
                    
                    # Try to extract body part from shortComment if not in details
                    if not body_part:
                        short_comment = injury.get('shortComment', '')
                        # Parse common patterns like "foot injury", "knee injury", etc.
                        import re
                        body_part_match = re.search(r'(foot|knee|ankle|hamstring|shoulder|hand|finger|toe|back|neck|elbow|concussion|calf|quad|groin|hip|chest|rib|wrist|thumb|arm|leg|thigh|achilles|head|oblique|illness) (injury|issue|problem)', 
                                                   short_comment.lower())
                        if body_part_match:
                            body_part = body_part_match.group(1).capitalize()
                    
                    injury_desc = details.get('detail', body_part)
                    
                    # Use shortComment as description if available
                    if not injury_desc:
                        injury_desc = injury.get('shortComment', body_part)
                    
                    # Get full context from ESPN
                    short_comment = injury.get('shortComment', '')
                    long_comment = injury.get('longComment', '')
                    
                    # Extract affected players (e.g., backup QBs, RB committee changes)
                    affected_players = self._extract_affected_players(long_comment or short_comment)
                    
                    parsed_injuries.append({
                        'player_name': player_name,
                        'team': team_abbr,
                        'position': position,
                        'injury_status': injury_status,
                        'body_part': body_part,
                        'injury_description': injury_desc,
                        'short_comment': short_comment,
                        'long_comment': long_comment,
                        'affected_players': affected_players,
                        'last_update': datetime.now(),
                        'source': 'ESPN',
                        'espn_date': injury.get('date', '')
                    })
                    
                except Exception as e:
                    print(f"⚠️ Error parsing ESPN injury for player: {e}")
                    continue
        
        return parsed_injuries
    
    def _get_team_abbr(self, team_name: str) -> str:
        """Convert team display name to abbreviation."""
        team_map = {
            'Arizona Cardinals': 'ARI', 'Atlanta Falcons': 'ATL', 'Baltimore Ravens': 'BAL',
            'Buffalo Bills': 'BUF', 'Carolina Panthers': 'CAR', 'Chicago Bears': 'CHI',
            'Cincinnati Bengals': 'CIN', 'Cleveland Browns': 'CLE', 'Dallas Cowboys': 'DAL',
            'Denver Broncos': 'DEN', 'Detroit Lions': 'DET', 'Green Bay Packers': 'GB',
            'Houston Texans': 'HOU', 'Indianapolis Colts': 'IND', 'Jacksonville Jaguars': 'JAX',
            'Kansas City Chiefs': 'KC', 'Las Vegas Raiders': 'LV', 'Los Angeles Chargers': 'LAC',
            'Los Angeles Rams': 'LAR', 'Miami Dolphins': 'MIA', 'Minnesota Vikings': 'MIN',
            'New England Patriots': 'NE', 'New Orleans Saints': 'NO', 'New York Giants': 'NYG',
            'New York Jets': 'NYJ', 'Philadelphia Eagles': 'PHI', 'Pittsburgh Steelers': 'PIT',
            'San Francisco 49ers': 'SF', 'Seattle Seahawks': 'SEA', 'Tampa Bay Buccaneers': 'TB',
            'Tennessee Titans': 'TEN', 'Washington Commanders': 'WAS'
        }
        return team_map.get(team_name, team_name[:3].upper())
    
    def _extract_affected_players(self, comment: str) -> List[str]:
        """
        Extract names of players affected by an injury from ESPN's commentary.
        
        Example: "Brissett is likely to start at quarterback for the Cardinals"
        -> Extract: ["Jacoby Brissett"]
        
        Args:
            comment: ESPN injury commentary text
        
        Returns:
            List of affected player names (first + last name)
        """
        if not comment:
            return []
        
        import re
        
        # Pattern: Capital Letter + lowercase letters + space + Capital Letter + lowercase letters
        # This matches "Jacoby Brissett", "Tyler Huntley", etc.
        # But avoids team names, single words, etc.
        pattern = r'\b([A-Z][a-z]+(?:\s+(?:de|De|van|Van|von|Von|Mc|Mac|O\')?[A-Z][a-z]+)+)\b'
        
        matches = re.findall(pattern, comment)
        
        # Filter out common false positives
        exclude_terms = {
            'Ian Rapoport', 'Adam Schefter', 'Tom Pelissero', 'Albert Breer',
            'Mike Garafolo', 'Jordan Schultz', 'Jay Glazer', 'Josina Anderson',
            'Sunday Night', 'Monday Night', 'Thursday Night', 'Pro Bowl',
            'Super Bowl', 'NFL Network', 'First Team', 'Second Team',
            'Last Year', 'This Year', 'Next Week', 'Last Week'
        }
        
        # Deduplicate and filter
        affected = []
        seen = set()
        for name in matches:
            if name not in exclude_terms and name.lower() not in seen:
                affected.append(name)
                seen.add(name.lower())
        
        return affected[:5]  # Limit to top 5 affected players
    
    def close(self):
        """Close client (no persistent connections for ESPN API)."""
        pass

