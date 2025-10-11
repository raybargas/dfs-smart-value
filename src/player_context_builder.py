"""
Player Context Builder for DFS Narrative Intelligence

This service enriches player data by:
1. Attaching ITT (Implied Team Total) from vegas_lines
2. Attaching injury status from injury_reports  
3. Running smart rules evaluation to generate flags
4. Building a complete player context for the UI

Usage:
    builder = PlayerContextBuilder(week=1)
    enriched_players = builder.enrich_players(player_df)
"""

from typing import Dict, List, Optional, Any
import pandas as pd
from datetime import datetime

from .rules_engine import SmartRulesEngine
from .database_models import VegasLine, InjuryReport, create_session


class PlayerContextBuilder:
    """
    Enriches player data with narrative intelligence context.
    
    Takes a DataFrame of players (from CSV) and adds:
    - ITT (Implied Team Total)
    - Injury status and details
    - Smart rules flags (red/yellow/green)
    - Prior week points (for 80/20 rule)
    """
    
    def __init__(self, week: int = 1, db_path: str = "dfs_optimizer.db"):
        """
        Initialize Player Context Builder.
        
        Args:
            week: NFL week number
            db_path: Path to SQLite database
        """
        self.week = week
        self.db_path = db_path
        self.session = create_session(db_path)
        self.rules_engine = SmartRulesEngine(db_path=db_path, week=week)
        
        # Load Vegas lines into memory
        self.vegas_lines_cache = self._load_vegas_lines()
        
        # Load injury reports into memory
        self.injury_reports_cache = self._load_injury_reports()
    
    def _load_vegas_lines(self) -> Dict[str, Dict[str, Any]]:
        """
        Load Vegas lines from database.
        
        Returns:
            Dictionary mapping team abbreviation to ITT and line data
        """
        vegas_cache = {}
        try:
            lines = self.session.query(VegasLine).filter_by(week=self.week).all()
            for line in lines:
                # Map both home and away teams
                vegas_cache[line.home_team] = {
                    'itt': line.home_itt,
                    'spread': line.home_spread,
                    'total': line.total,
                    'opponent': line.away_team,
                    'is_home': True
                }
                vegas_cache[line.away_team] = {
                    'itt': line.away_itt,
                    'spread': line.away_spread,
                    'total': line.total,
                    'opponent': line.home_team,
                    'is_home': False
                }
            return vegas_cache
        except Exception as e:
            print(f"Warning: Could not load Vegas lines: {e}")
            return {}
    
    def _load_injury_reports(self) -> Dict[tuple, Dict[str, Any]]:
        """
        Load the MOST RECENT injury report for each player from database.
        Gets the latest report regardless of week.
        
        Returns:
            Dictionary mapping (player_name, team) to injury data
        """
        injury_cache = {}
        try:
            from sqlalchemy import func
            
            # Get the most recent injury report for each (player_name, team) combination
            # This subquery finds the max updated_at for each player
            subquery = self.session.query(
                InjuryReport.player_name,
                InjuryReport.team,
                func.max(InjuryReport.updated_at).label('max_updated')
            ).group_by(InjuryReport.player_name, InjuryReport.team).subquery()
            
            # Join to get the full report for the most recent update
            reports = self.session.query(InjuryReport).join(
                subquery,
                (InjuryReport.player_name == subquery.c.player_name) &
                (InjuryReport.team == subquery.c.team) &
                (InjuryReport.updated_at == subquery.c.max_updated)
            ).all()
            
            for report in reports:
                key = (report.player_name, report.team)
                injury_cache[key] = {
                    'status': report.injury_status,
                    'practice_status': report.practice_status,
                    'body_part': report.body_part,
                    'description': report.description,
                    'updated_at': report.updated_at,
                    'week': report.week  # Keep track of which week this data is from
                }
            
            print(f"Loaded {len(injury_cache)} most recent injury reports from database")
            return injury_cache
        except Exception as e:
            print(f"Warning: Could not load injury reports: {e}")
            return {}
    
    def enrich_players(
        self,
        player_df: pd.DataFrame,
        prior_week_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Enrich player DataFrame with narrative intelligence context.
        
        Args:
            player_df: DataFrame with player data (name, team, position, salary, etc.)
            prior_week_df: Optional DataFrame with prior week fantasy points
            
        Returns:
            Enriched DataFrame with ITT, injury status, and flags
        """
        # Make a copy to avoid modifying original
        enriched_df = player_df.copy()
        
        # Add ITT column
        enriched_df['itt'] = enriched_df.apply(
            lambda row: self._get_itt(row.get('Team', row.get('team'))),
            axis=1
        )
        
        # Add opponent column
        enriched_df['opponent'] = enriched_df.apply(
            lambda row: self._get_opponent(row.get('Team', row.get('team'))),
            axis=1
        )
        
        # Add injury status columns
        enriched_df['injury_status'] = enriched_df.apply(
            lambda row: self._get_injury_status(
                row.get('Name', row.get('name')),
                row.get('Team', row.get('team'))
            ),
            axis=1
        )
        
        enriched_df['injury_details'] = enriched_df.apply(
            lambda row: self._get_injury_details(
                row.get('Name', row.get('name')),
                row.get('Team', row.get('team'))
            ),
            axis=1
        )
        
        # Add prior week points (for 80/20 rule)
        if prior_week_df is not None:
            enriched_df['last_week_points'] = enriched_df.apply(
                lambda row: self._get_prior_week_points(
                    row.get('Name', row.get('name')),
                    prior_week_df
                ),
                axis=1
            )
        else:
            enriched_df['last_week_points'] = None
        
        # Generate flags using smart rules engine
        enriched_df['flags'] = enriched_df.apply(
            lambda row: self._evaluate_player(row),
            axis=1
        )
        
        # Add flag count (for sorting/filtering)
        enriched_df['flag_count'] = enriched_df['flags'].apply(len)
        
        # Add severity counts
        enriched_df['red_flags'] = enriched_df['flags'].apply(
            lambda flags: sum(1 for f in flags if f.get('severity') == 'red')
        )
        enriched_df['yellow_flags'] = enriched_df['flags'].apply(
            lambda flags: sum(1 for f in flags if f.get('severity') == 'yellow')
        )
        enriched_df['green_flags'] = enriched_df['flags'].apply(
            lambda flags: sum(1 for f in flags if f.get('severity') == 'green')
        )
        
        # Add overall player score (for color coding)
        # 0 red flags + 0-1 yellow = green
        # 1+ red flags or 2+ yellow = red
        # Everything else = yellow
        enriched_df['player_score'] = enriched_df.apply(
            lambda row: self._calculate_player_score(
                row['red_flags'],
                row['yellow_flags'],
                row['green_flags']
            ),
            axis=1
        )
        
        return enriched_df
    
    def _get_itt(self, team: str) -> Optional[float]:
        """Get ITT for a team."""
        if not team or team not in self.vegas_lines_cache:
            return None
        return self.vegas_lines_cache[team]['itt']
    
    def _get_opponent(self, team: str) -> Optional[str]:
        """Get opponent for a team."""
        if not team or team not in self.vegas_lines_cache:
            return None
        return self.vegas_lines_cache[team]['opponent']
    
    def _get_injury_status(self, player_name: str, team: str) -> Optional[str]:
        """Get injury status for a player."""
        if not player_name:
            return None
        
        # Try exact match first (name + team)
        if team:
            key = (player_name, team)
            if key in self.injury_reports_cache:
                return self.injury_reports_cache[key]['status']
        
        # Try case-insensitive match (name + team)
        player_name_lower = player_name.lower().strip()
        if team:
            team_upper = team.upper().strip()
            for (cached_name, cached_team), report in self.injury_reports_cache.items():
                if cached_name.lower().strip() == player_name_lower and cached_team.upper().strip() == team_upper:
                    return report['status']
        
        # Fallback: Try name-only match (for traded players or team mismatches)
        for (cached_name, cached_team), report in self.injury_reports_cache.items():
            if cached_name.lower().strip() == player_name_lower:
                return report['status']
        
        return None
    
    def _get_injury_details(self, player_name: str, team: str) -> Optional[str]:
        """Get injury details for a player."""
        if not player_name:
            return None
        
        report = None
        
        # Try exact match first (name + team)
        if team:
            key = (player_name, team)
            if key in self.injury_reports_cache:
                report = self.injury_reports_cache[key]
        
        # Try case-insensitive match (name + team)
        if not report and team:
            player_name_lower = player_name.lower().strip()
            team_upper = team.upper().strip()
            for (cached_name, cached_team), cached_report in self.injury_reports_cache.items():
                if cached_name.lower().strip() == player_name_lower and cached_team.upper().strip() == team_upper:
                    report = cached_report
                    break
        
        # Fallback: Try name-only match (for traded players or team mismatches)
        if not report:
            player_name_lower = player_name.lower().strip()
            for (cached_name, cached_team), cached_report in self.injury_reports_cache.items():
                if cached_name.lower().strip() == player_name_lower:
                    report = cached_report
                    break
        
        if report:
            status = report['status'] or 'Unknown'
            body_part = report['body_part'] or 'Unknown'
            practice = report['practice_status'] or 'Unknown'
            return f"{status} - {body_part} ({practice} practice)"
        return None
    
    def _get_prior_week_points(
        self,
        player_name: str,
        prior_week_df: pd.DataFrame
    ) -> Optional[float]:
        """Get prior week fantasy points for 80/20 rule."""
        if not player_name or prior_week_df is None:
            return None
        
        # Match by name (case-insensitive)
        matches = prior_week_df[
            prior_week_df['Name'].str.lower() == player_name.lower()
        ]
        
        if not matches.empty:
            return matches.iloc[0].get('FantasyPoints', None)
        return None
    
    def _evaluate_player(self, row: pd.Series) -> List[Dict[str, Any]]:
        """
        Evaluate player using smart rules engine.
        
        Returns:
            List of flag dictionaries
        """
        try:
            # Normalize column names (handle both uppercase and lowercase)
            player_data = {
                'player_name': row.get('Name', row.get('name')),
                'team': row.get('Team', row.get('team')),
                'position': row.get('Position', row.get('position')),
                'salary': float(row.get('Salary', row.get('salary', 0))),
                'projected_points': float(row.get('AvgPointsPerGame', row.get('avg_points_per_game', 0))),
                'projected_ceiling': row.get('Ceiling', row.get('ceiling')),
                'last_week_points': row.get('last_week_points'),
                'attempts': row.get('Attempts', row.get('attempts')),
                'snaps': row.get('Snaps', row.get('snaps')),
                'routes': row.get('Routes', row.get('routes')),
                'projected_ownership': row.get('Ownership', row.get('ownership'))
            }
            
            # Remove None values
            player_data = {k: v for k, v in player_data.items() if v is not None}
            
            # Evaluate player
            flags = self.rules_engine.evaluate_player(**player_data)
            return flags
            
        except Exception as e:
            print(f"Error evaluating player {row.get('Name', 'unknown')}: {e}")
            return []
    
    def _calculate_player_score(
        self,
        red_count: int,
        yellow_count: int,
        green_count: int
    ) -> str:
        """
        Calculate overall player score for color coding.
        
        Returns:
            'green', 'yellow', or 'red'
        """
        # Red if any red flags
        if red_count > 0:
            return 'red'
        
        # Green if no yellow flags or only 1 yellow + some green
        if yellow_count == 0:
            return 'green'
        if yellow_count == 1 and green_count > 0:
            return 'green'
        
        # Yellow for everything else
        return 'yellow'
    
    def get_enrichment_stats(self) -> Dict[str, Any]:
        """
        Get statistics about available enrichment data.
        
        Returns:
            Dictionary with stats
        """
        return {
            'vegas_lines_loaded': len(self.vegas_lines_cache),
            'injury_reports_loaded': len(self.injury_reports_cache),
            'week': self.week,
            'teams_with_itt': list(self.vegas_lines_cache.keys()),
            'injured_players': len(self.injury_reports_cache)
        }
    
    def close(self):
        """Close database connections."""
        try:
            self.session.close()
            self.rules_engine.close()
        except Exception as e:
            print(f"Error closing connections: {e}")

