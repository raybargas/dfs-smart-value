"""
Injury data merger - combines MySportsFeeds and ESPN data.

Strategy:
1. Fetch from both MySportsFeeds (paid, official) and ESPN (free, fast)
2. Merge results, prioritizing ESPN for breaking news
3. Deduplicate by player name + team
4. Keep most recent/most severe status
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class InjuryMerger:
    """Merges injury data from multiple sources."""
    
    # Status severity ranking (higher = more severe)
    STATUS_SEVERITY = {
        'Out': 4,
        'Doubtful': 3,
        'Questionable': 2,
        'Day To Day': 1,
        'IR': 5,
        'Unknown': 0
    }
    
    @classmethod
    def merge_injuries(
        cls,
        mysportsfeeds_injuries: List[Dict[str, Any]],
        espn_injuries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Merge injuries from MySportsFeeds and ESPN.
        
        Rules:
        1. ESPN takes priority for breaking news (more recent updates)
        2. MySportsFeeds is the official source (more detailed/accurate)
        3. Use more severe status if there's a conflict
        4. Keep both sources for reference
        
        Args:
            mysportsfeeds_injuries: List from MySportsFeeds API
            espn_injuries: List from ESPN API
        
        Returns:
            Merged and deduplicated injury list
        """
        # Index MySportsFeeds injuries by (player_name, team)
        msf_index = {}
        for injury in mysportsfeeds_injuries:
            key = cls._get_player_key(injury)
            msf_index[key] = injury
        
        # Index ESPN injuries by (player_name, team)
        espn_index = {}
        for injury in espn_injuries:
            key = cls._get_player_key(injury)
            espn_index[key] = injury
        
        # Merge
        merged = []
        all_keys = set(msf_index.keys()) | set(espn_index.keys())
        
        for key in all_keys:
            msf_injury = msf_index.get(key)
            espn_injury = espn_index.get(key)
            
            if msf_injury and espn_injury:
                # Both sources have this player - merge intelligently
                merged_injury = cls._merge_single_injury(msf_injury, espn_injury)
                merged.append(merged_injury)
                
            elif msf_injury:
                # Only MySportsFeeds has this player
                msf_injury['sources'] = ['MySportsFeeds']
                merged.append(msf_injury)
                
            else:  # Only ESPN has this player
                # ESPN is often faster with breaking news
                espn_injury['sources'] = ['ESPN']
                espn_injury['is_breaking'] = True  # Flag as potentially breaking news
                merged.append(espn_injury)
        
        logger.info(
            f"✅ Merged injuries: {len(mysportsfeeds_injuries)} MSF + "
            f"{len(espn_injuries)} ESPN = {len(merged)} total "
            f"(ESPN-only: {len([i for i in merged if i.get('is_breaking')])})"
        )
        
        return merged
    
    @classmethod
    def _get_player_key(cls, injury: Dict[str, Any]) -> tuple:
        """Generate unique key for player."""
        player_name = injury.get('player_name', '').strip().lower()
        team = injury.get('team', '').strip().upper()
        return (player_name, team)
    
    @classmethod
    def _merge_single_injury(
        cls,
        msf_injury: Dict[str, Any],
        espn_injury: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge two injury reports for the same player.
        
        Priority:
        1. More severe status wins
        2. More detailed body_part/description wins
        3. Mark as confirmed by both sources
        """
        # Start with MySportsFeeds as base (official source)
        merged = msf_injury.copy()
        merged['sources'] = ['MySportsFeeds', 'ESPN']
        
        # Use more severe status
        msf_severity = cls.STATUS_SEVERITY.get(msf_injury['injury_status'], 0)
        espn_severity = cls.STATUS_SEVERITY.get(espn_injury['injury_status'], 0)
        
        if espn_severity > msf_severity:
            merged['injury_status'] = espn_injury['injury_status']
            merged['status_source'] = 'ESPN (more severe)'
        elif espn_severity < msf_severity:
            merged['status_source'] = 'MySportsFeeds (more severe)'
        else:
            merged['status_source'] = 'Both agree'
        
        # Use more detailed body part if available
        if not merged.get('body_part') and espn_injury.get('body_part'):
            merged['body_part'] = espn_injury['body_part']
        
        # Combine descriptions if both exist and are different
        msf_desc = msf_injury.get('injury_description', '').strip()
        espn_desc = espn_injury.get('injury_description', '').strip()
        
        if msf_desc and espn_desc and msf_desc.lower() != espn_desc.lower():
            # Keep more detailed description
            if len(espn_desc) > len(msf_desc):
                merged['injury_description'] = espn_desc
                merged['alternate_description'] = msf_desc
            else:
                merged['alternate_description'] = espn_desc
        
        return merged

