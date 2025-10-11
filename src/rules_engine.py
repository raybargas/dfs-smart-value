"""
Smart Rules Engine for DFS Narrative Intelligence (Phase 2C)

This engine evaluates players against business partner's expert rules:
- Position-specific criteria (QB, RB, WR, TE, DST)
- Vegas line integration (ITT thresholds)
- Salary vs ceiling validation
- 80/20 regression analysis
- Stacking opportunities

Generates color-coded flags:
- Green: Optimal play
- Yellow: Caution/warning
- Red: Avoid/critical concern
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd

from .database_models import VegasLine, InjuryReport, NarrativeFlag


class SmartRulesEngine:
    """
    Evaluates DFS players against expert rules and generates narrative flags.
    
    Features:
    - Position-specific rule evaluation
    - ITT threshold checks (Vegas lines)
    - Salary/ceiling ratio validation
    - 80/20 WR regression analysis
    - Committee RB detection
    - Stacking opportunity identification
    """
    
    # Rule thresholds (from business partner requirements)
    THRESHOLDS = {
        'qb': {
            'min_itt': 21,
            'min_scrimmage_yards': 270,
        },
        'rb': {
            'min_itt': 18,
            'min_attempts': 14,
            'high_salary': 5500,
            'salary_ceiling_multiplier': 3.5,
        },
        'wr': {
            'min_itt': 18,
            'min_snaps': 20,
            'min_routes': 20,
            'high_salary': 6500,
            'salary_ceiling_multiplier': 3.5,
            'floor_salary': 4000,
            'regression_threshold': 20,  # 80/20 rule
            'high_ownership_threshold': 20,
            'leverage_ownership_threshold': 10,
            'leverage_ceiling': 20,
        },
        'te': {
            'min_itt': 18,
            'min_snaps': 20,
            'min_routes': 13,
            'floor_salary': 3000,
        },
        'dst': {
            'oline_rank_threshold': 28,  # Bottom 5 (32 teams)
        }
    }
    
    def __init__(self, db_path: str = "dfs_optimizer.db", week: int = 1):
        """
        Initialize Smart Rules Engine.
        
        Args:
            db_path: Path to SQLite database
            week: NFL week number for evaluation
        """
        self.db_path = db_path
        self.week = week
        
        # Setup database session
        engine = create_engine(f'sqlite:///{db_path}')
        Session = sessionmaker(bind=engine)
        self.session = Session()
        
        # Load Vegas lines for ITT lookups
        self.vegas_lines_cache = self._load_vegas_lines()
        
        # Load injury reports
        self.injury_reports_cache = self._load_injury_reports()
    
    def _load_vegas_lines(self) -> Dict[str, VegasLine]:
        """
        Load Vegas lines from database for the current week.
        
        Returns:
            Dictionary mapping team abbreviation to VegasLine object
        """
        vegas_cache = {}
        try:
            lines = self.session.query(VegasLine).filter_by(week=self.week).all()
            for line in lines:
                # Map both home and away teams
                vegas_cache[line.home_team] = line
                vegas_cache[line.away_team] = line
            return vegas_cache
        except Exception as e:
            print(f"Warning: Could not load Vegas lines: {e}")
            return {}
    
    def _load_injury_reports(self) -> Dict[str, InjuryReport]:
        """
        Load injury reports from database for the current week.
        
        Returns:
            Dictionary mapping (player_name, team) to InjuryReport object
        """
        injury_cache = {}
        try:
            reports = self.session.query(InjuryReport).filter_by(week=self.week).all()
            for report in reports:
                key = (report.player_name, report.team)
                injury_cache[key] = report
            return injury_cache
        except Exception as e:
            print(f"Warning: Could not load injury reports: {e}")
            return {}
    
    def get_team_itt(self, team: str) -> Optional[float]:
        """
        Get Implied Team Total (ITT) for a team.
        
        Args:
            team: Team abbreviation (e.g., 'SF', 'KC')
            
        Returns:
            ITT value or None if not found
        """
        if team not in self.vegas_lines_cache:
            return None
        
        vegas_line = self.vegas_lines_cache[team]
        return vegas_line.get_itt(team)
    
    def evaluate_player(
        self,
        player_name: str,
        team: str,
        position: str,
        salary: float,
        projected_points: float,
        projected_ceiling: Optional[float] = None,
        last_week_points: Optional[float] = None,
        attempts: Optional[int] = None,
        snaps: Optional[int] = None,
        routes: Optional[int] = None,
        projected_ownership: Optional[float] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Evaluate a player against position-specific rules.
        
        Args:
            player_name: Player's full name
            team: Team abbreviation
            position: Position (QB, RB, WR, TE, DST)
            salary: DraftKings salary
            projected_points: Projected fantasy points
            projected_ceiling: Projected ceiling (optional)
            last_week_points: Points scored last week (optional)
            attempts: Projected attempts (RB) (optional)
            snaps: Projected snaps (optional)
            routes: Projected routes (optional)
            projected_ownership: Projected ownership % (optional)
            **kwargs: Additional player data
            
        Returns:
            List of flag dictionaries
        """
        flags = []
        
        # Position-specific evaluation
        if position == 'QB':
            flags.extend(self._evaluate_qb(
                player_name, team, salary, projected_points, projected_ceiling, **kwargs
            ))
        elif position == 'RB':
            flags.extend(self._evaluate_rb(
                player_name, team, salary, projected_points, projected_ceiling,
                attempts, **kwargs
            ))
        elif position == 'WR':
            flags.extend(self._evaluate_wr(
                player_name, team, salary, projected_points, projected_ceiling,
                last_week_points, snaps, routes, projected_ownership, **kwargs
            ))
        elif position == 'TE':
            flags.extend(self._evaluate_te(
                player_name, team, salary, projected_points, projected_ceiling,
                snaps, routes, **kwargs
            ))
        elif position in ['DST', 'D']:
            flags.extend(self._evaluate_dst(
                player_name, team, salary, projected_points, **kwargs
            ))
        
        return flags
    
    def _evaluate_qb(
        self,
        player_name: str,
        team: str,
        salary: float,
        projected_points: float,
        projected_ceiling: Optional[float],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Evaluate QB against expert rules.
        
        Rules:
        - Team ITT should be 21+ (strong correlation to QB scoring)
        - Can regularly hit 270+ scrimmage yards
        - Opportunity for multiple TDs
        """
        flags = []
        
        # Rule 1: ITT threshold check
        itt = self.get_team_itt(team)
        if itt is not None:
            if itt < self.THRESHOLDS['qb']['min_itt']:
                flags.append({
                    'flag_category': 'low_itt',
                    'message': f"Team ITT = {itt} (threshold: {self.THRESHOLDS['qb']['min_itt']}+) - low scoring environment",
                    'severity': 'red'
                })
            elif itt >= self.THRESHOLDS['qb']['min_itt'] and itt < 24:
                flags.append({
                    'flag_category': 'moderate_itt',
                    'message': f"Team ITT = {itt} (moderate scoring environment)",
                    'severity': 'yellow'
                })
            else:
                flags.append({
                    'flag_category': 'high_itt',
                    'message': f"Team ITT = {itt} (high scoring environment - optimal)",
                    'severity': 'green'
                })
        
        return flags
    
    def _evaluate_rb(
        self,
        player_name: str,
        team: str,
        salary: float,
        projected_points: float,
        projected_ceiling: Optional[float],
        attempts: Optional[int],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Evaluate RB against expert rules.
        
        Rules:
        - 14+ attempts required
        - Passing game involvement
        - Goal-line work
        - Salary/ceiling ratio: (Salary/1000)*3.5 should not exceed ceiling
        - Team ITT 18+
        - Avoid committees
        """
        flags = []
        
        # Rule 1: ITT threshold check (18+ for non-QBs)
        itt = self.get_team_itt(team)
        if itt is not None and itt < self.THRESHOLDS['rb']['min_itt']:
            flags.append({
                'flag_category': 'low_itt',
                'message': f"Team ITT = {itt} (threshold: {self.THRESHOLDS['rb']['min_itt']}+) - lower scoring potential",
                'severity': 'yellow'
            })
        
        # Rule 2: Attempt threshold
        if attempts is not None and attempts < self.THRESHOLDS['rb']['min_attempts']:
            flags.append({
                'flag_category': 'low_volume',
                'message': f"Projected {attempts} attempts (threshold: {self.THRESHOLDS['rb']['min_attempts']}+) - committee concern",
                'severity': 'red'
            })
        
        # Rule 3: Salary/ceiling ratio check (for high-priced RBs)
        if salary >= self.THRESHOLDS['rb']['high_salary'] and projected_ceiling is not None:
            threshold_ceiling = (salary / 1000) * self.THRESHOLDS['rb']['salary_ceiling_multiplier']
            if projected_ceiling < threshold_ceiling:
                flags.append({
                    'flag_category': 'salary_ceiling_mismatch',
                    'message': f"Salary ${int(salary)} needs {threshold_ceiling:.1f}+ ceiling (projected: {projected_ceiling:.1f}) - value concern",
                    'severity': 'red'
                })
        
        return flags
    
    def _evaluate_wr(
        self,
        player_name: str,
        team: str,
        salary: float,
        projected_points: float,
        projected_ceiling: Optional[float],
        last_week_points: Optional[float],
        snaps: Optional[int],
        routes: Optional[int],
        projected_ownership: Optional[float],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Evaluate WR against expert rules.
        
        Rules:
        - 20+ snaps and 20+ routes minimum
        - 80/20 rule: If 20+ points last week, 80% likely < 20 this week
        - Salary/ceiling ratio: (Salary/1000)*3.5 should not exceed ceiling
        - Avoid WRs < $4K unless extreme value
        - Team ITT 18+
        - Stacking opportunities
        - Leverage plays (< 10% ownership, 20+ ceiling)
        """
        flags = []
        
        # Rule 1: ITT threshold check
        itt = self.get_team_itt(team)
        if itt is not None and itt < self.THRESHOLDS['wr']['min_itt']:
            flags.append({
                'flag_category': 'low_itt',
                'message': f"Team ITT = {itt} (threshold: {self.THRESHOLDS['wr']['min_itt']}+) - lower scoring potential",
                'severity': 'yellow'
            })
        
        # Rule 2: Snap/route threshold
        if snaps is not None and snaps < self.THRESHOLDS['wr']['min_snaps']:
            flags.append({
                'flag_category': 'low_snaps',
                'message': f"Projected {snaps} snaps (threshold: {self.THRESHOLDS['wr']['min_snaps']}+) - limited opportunity",
                'severity': 'red'
            })
        
        if routes is not None and routes < self.THRESHOLDS['wr']['min_routes']:
            flags.append({
                'flag_category': 'low_routes',
                'message': f"Projected {routes} routes (threshold: {self.THRESHOLDS['wr']['min_routes']}+) - limited targets",
                'severity': 'red'
            })
        
        # Rule 3: 80/20 regression rule
        if last_week_points is not None and last_week_points >= self.THRESHOLDS['wr']['regression_threshold']:
            flags.append({
                'flag_category': '80_20_regression',
                'message': f"Scored {last_week_points:.1f} last week - 80% likely to score < {self.THRESHOLDS['wr']['regression_threshold']} this week (regression risk)",
                'severity': 'yellow'
            })
        
        # Rule 4: Salary/ceiling ratio check (for high-priced WRs)
        if salary >= self.THRESHOLDS['wr']['high_salary'] and projected_ceiling is not None:
            threshold_ceiling = (salary / 1000) * self.THRESHOLDS['wr']['salary_ceiling_multiplier']
            if projected_ceiling < threshold_ceiling:
                flags.append({
                    'flag_category': 'salary_ceiling_mismatch',
                    'message': f"Salary ${int(salary)} needs {threshold_ceiling:.1f}+ ceiling (projected: {projected_ceiling:.1f}) - value concern",
                    'severity': 'red'
                })
        
        # Rule 5: Low salary floor check
        if salary < self.THRESHOLDS['wr']['floor_salary']:
            # Check if it's "extreme value"
            if projected_points is not None and (projected_points / (salary / 1000)) >= 3.0:
                flags.append({
                    'flag_category': 'value_play',
                    'message': f"Salary ${int(salary)} but strong value ({projected_points:.1f} pts / ${salary/1000:.1f}K = {(projected_points / (salary / 1000)):.1f}x)",
                    'severity': 'green'
                })
            else:
                flags.append({
                    'flag_category': 'low_salary',
                    'message': f"Salary ${int(salary)} below threshold (${self.THRESHOLDS['wr']['floor_salary']}) - limited upside unless extreme value",
                    'severity': 'yellow'
                })
        
        # Rule 6: Leverage play identification
        if (projected_ownership is not None and 
            projected_ownership < self.THRESHOLDS['wr']['leverage_ownership_threshold'] and
            projected_ceiling is not None and
            projected_ceiling >= self.THRESHOLDS['wr']['leverage_ceiling']):
            flags.append({
                'flag_category': 'leverage_play',
                'message': f"Low ownership ({projected_ownership:.1f}%) + high ceiling ({projected_ceiling:.1f}) = elite leverage opportunity",
                'severity': 'green'
            })
        
        return flags
    
    def _evaluate_te(
        self,
        player_name: str,
        team: str,
        salary: float,
        projected_points: float,
        projected_ceiling: Optional[float],
        snaps: Optional[int],
        routes: Optional[int],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Evaluate TE against expert rules.
        
        Rules:
        - Route-running vs blocking (20+ snaps, 13+ routes)
        - Stacking partner with QB
        - Avoid TEs < $3K
        - Team ITT 18+
        """
        flags = []
        
        # Rule 1: ITT threshold check
        itt = self.get_team_itt(team)
        if itt is not None and itt < self.THRESHOLDS['te']['min_itt']:
            flags.append({
                'flag_category': 'low_itt',
                'message': f"Team ITT = {itt} (threshold: {self.THRESHOLDS['te']['min_itt']}+) - lower scoring potential",
                'severity': 'yellow'
            })
        
        # Rule 2: Snap/route threshold (route-runner vs blocker)
        if snaps is not None and snaps < self.THRESHOLDS['te']['min_snaps']:
            flags.append({
                'flag_category': 'blocking_te',
                'message': f"Projected {snaps} snaps (threshold: {self.THRESHOLDS['te']['min_snaps']}+) - likely blocking TE",
                'severity': 'red'
            })
        
        if routes is not None and routes < self.THRESHOLDS['te']['min_routes']:
            flags.append({
                'flag_category': 'low_routes',
                'message': f"Projected {routes} routes (threshold: {self.THRESHOLDS['te']['min_routes']}+) - limited receiving role",
                'severity': 'red'
            })
        
        # Rule 3: Low salary floor check
        if salary < self.THRESHOLDS['te']['floor_salary']:
            flags.append({
                'flag_category': 'low_salary',
                'message': f"Salary ${int(salary)} below threshold (${self.THRESHOLDS['te']['floor_salary']}) - avoid",
                'severity': 'red'
            })
        
        return flags
    
    def _evaluate_dst(
        self,
        player_name: str,
        team: str,
        salary: float,
        projected_points: float,
        opponent_team: Optional[str] = None,
        opponent_oline_rank: Optional[int] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Evaluate DST against expert rules.
        
        Rules:
        - Favored or facing bottom 5 O-line
        - Opponent has shaky QB play (turnovers)
        """
        flags = []
        
        # Rule 1: Opponent O-line ranking
        if opponent_oline_rank is not None:
            if opponent_oline_rank >= self.THRESHOLDS['dst']['oline_rank_threshold']:
                flags.append({
                    'flag_category': 'weak_oline_matchup',
                    'message': f"Facing bottom 5 O-line (rank {opponent_oline_rank}/32) - sack/pressure opportunity",
                    'severity': 'green'
                })
            elif opponent_oline_rank <= 10:
                flags.append({
                    'flag_category': 'strong_oline_matchup',
                    'message': f"Facing top 10 O-line (rank {opponent_oline_rank}/32) - difficult matchup",
                    'severity': 'yellow'
                })
        
        return flags
    
    def store_flags(self, player_name: str, team: str, position: str, flags: List[Dict[str, Any]]):
        """
        Store generated flags to narrative_flags table.
        
        Args:
            player_name: Player's full name
            team: Team abbreviation
            position: Player position (QB, RB, WR, TE, DST)
            flags: List of flag dictionaries
        """
        try:
            for flag in flags:
                # Determine flag_type from severity
                flag_type_map = {
                    'green': 'optimal',
                    'yellow': 'caution',
                    'red': 'warning'
                }
                flag_type = flag_type_map.get(flag['severity'], 'warning')
                
                # Map flag_category to allowed values
                category_map = {
                    'low_itt': 'itt',
                    'moderate_itt': 'itt',
                    'high_itt': 'itt',
                    'low_volume': 'committee',
                    'salary_ceiling_mismatch': 'salary_ceiling',
                    'low_snaps': 'snap_count',
                    'low_routes': 'routes',
                    '80_20_regression': 'regression',
                    'value_play': 'price_floor',
                    'low_salary': 'price_floor',
                    'leverage_play': 'stacking',
                    'blocking_te': 'routes',
                    'weak_oline_matchup': 'matchup',
                    'strong_oline_matchup': 'matchup'
                }
                flag_category = category_map.get(flag['flag_category'], 'other')
                
                narrative_flag = NarrativeFlag(
                    week=self.week,
                    player_name=player_name,
                    team=team,
                    position=position,
                    flag_type=flag_type,
                    flag_category=flag_category,
                    message=flag['message'],
                    severity=flag['severity'],
                    created_at=datetime.now()
                )
                self.session.add(narrative_flag)
            
            self.session.commit()
        except Exception as e:
            print(f"Error storing flags for {player_name}: {e}")
            self.session.rollback()
    
    def evaluate_and_store(
        self,
        players: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Evaluate multiple players and store flags.
        
        Args:
            players: List of player dictionaries with required fields
            
        Returns:
            Dictionary mapping player names to their flags
        """
        results = {}
        
        for player in players:
            player_name = player.get('player_name') or player.get('name')
            team = player.get('team')
            position = player.get('position')
            
            if not player_name or not team or not position:
                continue
            
            flags = self.evaluate_player(**player)
            results[player_name] = flags
            
            if flags:
                self.store_flags(player_name, team, position, flags)
        
        return results
    
    def close(self):
        """Close database session."""
        try:
            self.session.close()
        except Exception as e:
            print(f"Error closing session: {e}")

