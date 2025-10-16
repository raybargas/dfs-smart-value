"""
Database Models Module (Phase 2C - Narrative Intelligence + Historical Data)

SQLAlchemy ORM models for:
- VegasLine: Stores Vegas odds data (spread, total, ITT)
- InjuryReport: Stores NFL injury reports and practice status
- NarrativeFlag: Stores smart rules evaluation results
- APICallLog: Tracks API calls for rate limit management
- GameBoxscore: Stores historical game data (scores, date, teams)
- PlayerGameStats: Stores player statistics by game
- TeamGameStats: Stores team statistics by game

These models provide ORM functionality for database operations.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text,
    CheckConstraint, UniqueConstraint, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class VegasLine(Base):
    """
    Vegas odds data from The Odds API.
    
    Stores spread, total, and calculated implied team totals (ITT)
    for NFL games.
    
    Attributes:
        id: Primary key
        week: NFL week number (1-18)
        game_id: Unique game identifier
        home_team: Home team abbreviation
        away_team: Away team abbreviation
        home_spread: Home team spread (negative = favored)
        away_spread: Away team spread (positive = underdog)
        total: Game total (over/under)
        home_itt: Home team implied total: (total/2) + (spread/2)
        away_itt: Away team implied total: (total/2) - (spread/2)
        fetched_at: Timestamp of API data fetch
    """
    __tablename__ = 'vegas_lines'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    week = Column(Integer, nullable=False)
    game_id = Column(String, nullable=False)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    home_spread = Column(Float, nullable=True)
    away_spread = Column(Float, nullable=True)
    total = Column(Float, nullable=True)
    home_itt = Column(Float, nullable=True)
    away_itt = Column(Float, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('week', 'game_id', name='uq_vegas_lines_week_game'),
        CheckConstraint('total IS NULL OR total > 0', name='ck_vegas_lines_total'),
        CheckConstraint('home_itt IS NULL OR home_itt > 0', name='ck_vegas_lines_home_itt'),
        CheckConstraint('away_itt IS NULL OR away_itt > 0', name='ck_vegas_lines_away_itt'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<VegasLine(week={self.week}, game='{self.away_team} @ {self.home_team}', "
            f"spread={self.home_spread}, total={self.total}, "
            f"ITT={self.home_itt}/{self.away_itt})>"
        )
    
    def get_itt(self, team: str) -> Optional[float]:
        """
        Get ITT for a specific team.
        
        Args:
            team: Team abbreviation
            
        Returns:
            float: ITT for the team, or None if not found
        """
        if team == self.home_team:
            return self.home_itt
        elif team == self.away_team:
            return self.away_itt
        return None


class InjuryReport(Base):
    """
    NFL injury reports from MySportsFeeds API.
    
    Stores injury status, practice participation, and body part info
    for all NFL players.
    
    Attributes:
        id: Primary key
        week: NFL week number (1-18)
        player_name: Player full name
        team: Team abbreviation
        position: Player position (QB, RB, WR, TE, DST)
        injury_status: Q (Questionable), D (Doubtful), O (Out), IR, PUP, NFI
        practice_status: Full, Limited, DNP (Did Not Participate)
        body_part: Injured body part (Hamstring, Ankle, etc.)
        description: Full injury description text
        updated_at: Timestamp of last update
    """
    __tablename__ = 'injury_reports'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    week = Column(Integer, nullable=False)
    player_name = Column(String, nullable=False)
    team = Column(String, nullable=False)
    position = Column(String, nullable=True)
    injury_status = Column(String, nullable=True)
    practice_status = Column(String, nullable=True)
    body_part = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('week', 'player_name', 'team', name='uq_injury_reports_week_player'),
        CheckConstraint(
            "injury_status IS NULL OR injury_status IN ('Q', 'D', 'O', 'IR', 'PUP', 'NFI')",
            name='ck_injury_reports_status'
        ),
        CheckConstraint(
            "practice_status IS NULL OR practice_status IN ('Full', 'Limited', 'DNP')",
            name='ck_injury_reports_practice'
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<InjuryReport(player='{self.player_name}', team='{self.team}', "
            f"status='{self.injury_status}', practice='{self.practice_status}', "
            f"body_part='{self.body_part}')>"
        )
    
    @property
    def is_active_injury(self) -> bool:
        """
        Check if this is an active injury (Q, D, or O status).
        
        Returns:
            bool: True if player has active injury designation
        """
        return self.injury_status in ('Q', 'D', 'O')
    
    @property
    def severity_score(self) -> int:
        """
        Get numeric severity score for sorting.
        
        Returns:
            int: 0 (no injury) to 5 (IR/Out)
        """
        severity_map = {
            None: 0,
            'Q': 2,
            'D': 3,
            'O': 4,
            'IR': 5,
            'PUP': 5,
            'NFI': 5
        }
        return severity_map.get(self.injury_status, 0)


class NarrativeFlag(Base):
    """
    Smart rules evaluation results for players.
    
    Stores flags generated by position evaluators (QB, RB, WR, TE, DST)
    based on business rules (ITT thresholds, salary/ceiling ratios, etc.)
    
    Attributes:
        id: Primary key
        week: NFL week number (1-18)
        player_name: Player full name
        team: Team abbreviation
        position: Player position (QB, RB, WR, TE, DST)
        flag_type: optimal, caution, warning
        flag_category: itt, salary_ceiling, snap_count, routes, committee, etc.
        message: Human-readable flag explanation
        severity: green, yellow, red (for UI color-coding)
        created_at: Timestamp of flag creation
    """
    __tablename__ = 'narrative_flags'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    week = Column(Integer, nullable=False)
    player_name = Column(String, nullable=False)
    team = Column(String, nullable=False)
    position = Column(String, nullable=False)
    flag_type = Column(String, nullable=False)
    flag_category = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    severity = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint(
            "flag_type IN ('optimal', 'caution', 'warning')",
            name='ck_narrative_flags_type'
        ),
        CheckConstraint(
            "flag_category IN ('itt', 'salary_ceiling', 'snap_count', 'routes', 'committee', "
            "'regression', 'price_floor', 'stacking', 'matchup', 'other')",
            name='ck_narrative_flags_category'
        ),
        CheckConstraint(
            "severity IN ('green', 'yellow', 'red')",
            name='ck_narrative_flags_severity'
        ),
        CheckConstraint(
            "LENGTH(message) > 0",
            name='ck_narrative_flags_message'
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<NarrativeFlag(player='{self.player_name}', "
            f"category='{self.flag_category}', severity='{self.severity}', "
            f"message='{self.message[:50]}...')>"
        )
    
    @property
    def color_code(self) -> str:
        """
        Get hex color code for UI rendering.
        
        Returns:
            str: Hex color code (#rrggbb)
        """
        color_map = {
            'green': '#1a472a',
            'yellow': '#4a4419',
            'red': '#4a1a1a'
        }
        return color_map.get(self.severity, '#ffffff')


class APICallLog(Base):
    """
    API call tracking for rate limit management.
    
    Logs all external API calls (The Odds API, MySportsFeeds, etc.)
    for monitoring, debugging, and rate limit enforcement.
    
    Attributes:
        id: Primary key
        api_name: the_odds_api, mysportsfeeds, nfl_data_py, other
        endpoint: Full API endpoint URL
        status_code: HTTP status code (200, 429, 500, etc.)
        response_time_ms: Response time in milliseconds
        error_message: Error description if call failed
        called_at: Timestamp of API call
    """
    __tablename__ = 'api_call_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    api_name = Column(String, nullable=False)
    endpoint = Column(String, nullable=False)
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    called_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint(
            "api_name IN ('the_odds_api', 'mysportsfeeds', 'nfl_data_py', 'other')",
            name='ck_api_call_log_name'
        ),
        CheckConstraint(
            "status_code IS NULL OR (status_code >= 100 AND status_code < 600)",
            name='ck_api_call_log_status'
        ),
        CheckConstraint(
            "response_time_ms IS NULL OR response_time_ms >= 0",
            name='ck_api_call_log_time'
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<APICallLog(api='{self.api_name}', endpoint='{self.endpoint}', "
            f"status={self.status_code}, time={self.response_time_ms}ms)>"
        )
    
    @property
    def is_success(self) -> bool:
        """
        Check if API call was successful.
        
        Returns:
            bool: True if status code 200-299
        """
        return self.status_code is not None and 200 <= self.status_code < 300
    
    @property
    def is_rate_limited(self) -> bool:
        """
        Check if API call was rate limited.
        
        Returns:
            bool: True if status code 429
        """
        return self.status_code == 429


# ============================================================================
# PHASE 2D: HISTORICAL INTELLIGENCE MODELS
# ============================================================================

class Slate(Base):
    """
    Multi-site, multi-contest slate metadata.
    
    Stores information about DFS slates (contest types, sites, weeks).
    Enables DK vs FD comparison, Classic vs Showdown analysis.
    
    Attributes:
        slate_id: Primary key (e.g., "2024-W6-DK-CLASSIC")
        week: NFL week number
        season: NFL season year
        site: DFS site name ('DraftKings', 'FanDuel')
        contest_type: Contest type ('Classic', 'Showdown', 'Thanksgiving')
        slate_date: Date of the slate
        games_in_slate: JSON array of game IDs
        created_at: Timestamp of slate creation
    """
    __tablename__ = 'slates'
    
    slate_id = Column(String, primary_key=True)
    week = Column(Integer, nullable=False)
    season = Column(Integer, nullable=False)
    site = Column(String, nullable=False)
    contest_type = Column(String, nullable=False)
    slate_date = Column(DateTime, nullable=False)
    games_in_slate = Column(Text)  # JSON array
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return (
            f"<Slate(id='{self.slate_id}', week={self.week}, "
            f"site='{self.site}', type='{self.contest_type}')>"
        )


class HistoricalPlayerPool(Base):
    """
    Complete weekly player pool snapshot for perfect replay.
    
    Stores all player data for a specific slate, enabling backtesting
    and time-travel analysis. Tracks projections, salaries, ownership,
    and actual results.
    
    Attributes:
        slate_id: Foreign key to slates table
        player_id: Player identifier
        player_name: Player full name
        position: Player position (QB, RB, WR, TE, DST)
        team: Player team abbreviation
        opponent: Opponent team abbreviation
        salary: DFS salary
        projection: Projected fantasy points
        ceiling: Projected ceiling
        ownership: Projected ownership %
        actual_points: Actual fantasy points (fetched Monday)
        smart_value: Calculated Smart Value score
        smart_value_profile: Profile used for calculation
        projection_source: Source of projection data
        ownership_source: Source of ownership data
        data_source: How data was obtained
        fetched_at: Timestamp of data fetch
    """
    __tablename__ = 'historical_player_pool'
    
    slate_id = Column(String, primary_key=True)
    player_id = Column(String, primary_key=True)
    player_name = Column(String, nullable=False)
    position = Column(String, nullable=False)
    team = Column(String, nullable=False)
    opponent = Column(String, nullable=True)  # Optional - may be missing from API
    salary = Column(Integer, nullable=False)
    projection = Column(Float, nullable=False)
    ceiling = Column(Float)
    ownership = Column(Float)
    actual_points = Column(Float)
    smart_value = Column(Float)
    smart_value_profile = Column(String)
    projection_source = Column(String)
    ownership_source = Column(String)
    data_source = Column(String, nullable=False)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return (
            f"<HistoricalPlayerPool(slate='{self.slate_id}', "
            f"player='{self.player_name}', pos={self.position}, "
            f"salary=${self.salary}, proj={self.projection})>"
        )


class SmartValueProfileHistory(Base):
    """
    Smart Value profile versioning and performance tracking.
    
    Stores each profile version used and tracks its performance
    across weeks. Enables profile comparison and optimization.
    
    Attributes:
        profile_id: Primary key (e.g., "GPP_Balanced_v3.0_W10")
        profile_name: Profile name
        version: Version string
        week_used: Week number when profile was used
        season: Season year
        weights: JSON of full weight configuration
        performance_score: Average % of optimal lineup
        avg_lineup_score: Average actual points
        top_lineup_score: Best lineup actual points
        lineups_generated: Number of lineups generated
        created_at: Timestamp of profile creation
    """
    __tablename__ = 'smart_value_profiles_history'
    
    profile_id = Column(String, primary_key=True)
    profile_name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    week_used = Column(Integer, nullable=False)
    season = Column(Integer, nullable=False)
    weights = Column(Text, nullable=False)  # JSON
    performance_score = Column(Float)
    avg_lineup_score = Column(Float)
    top_lineup_score = Column(Float)
    lineups_generated = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return (
            f"<SmartValueProfileHistory(id='{self.profile_id}', "
            f"name='{self.profile_name}', version={self.version}, "
            f"week={self.week_used}, score={self.performance_score})>"
        )


class InjuryPattern(Base):
    """
    Learned injury intelligence patterns.
    
    Accumulates injury outcomes over time to learn typical impacts
    by injury type, position, and practice status. Enables data-driven
    injury decisions.
    
    Attributes:
        pattern_id: Primary key (e.g., "ankle_sprain_WR_LP-FP")
        injury_type: Type of injury
        position: Player position
        practice_status: Practice participation pattern
        games_played: Count of times played through injury
        games_missed: Count of times sat out
        total_projection_diff: Sum of (actual - projection)
        avg_points_impact: Calculated average impact
        sample_size: Total games (played + missed)
        last_updated: Last update timestamp
    """
    __tablename__ = 'injury_patterns'
    
    pattern_id = Column(String, primary_key=True)
    injury_type = Column(String, nullable=False)
    position = Column(String, nullable=False)
    practice_status = Column(String)
    games_played = Column(Integer, default=0)
    games_missed = Column(Integer, default=0)
    total_projection_diff = Column(Float, default=0.0)
    avg_points_impact = Column(Float)
    sample_size = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return (
            f"<InjuryPattern(id='{self.pattern_id}', "
            f"injury='{self.injury_type}', pos={self.position}, "
            f"impact={self.avg_points_impact}, n={self.sample_size})>"
        )
    
    def update_pattern(self, played: bool, projection_diff: float = 0.0):
        """
        Update pattern with new data point.
        
        Args:
            played: True if player played, False if sat out
            projection_diff: actual_points - projection (if played)
        """
        if played:
            self.games_played += 1
            self.total_projection_diff += projection_diff
            self.avg_points_impact = self.total_projection_diff / self.games_played
        else:
            self.games_missed += 1
        
        self.sample_size = self.games_played + self.games_missed
        self.last_updated = datetime.utcnow()


class BacktestResult(Base):
    """
    Backtest run artifacts and results.
    
    Stores results from backtesting runs, enabling comparison of
    different Smart Value profiles across multiple weeks.
    
    Attributes:
        backtest_id: Primary key (UUID)
        run_timestamp: When backtest was run
        weeks_tested: JSON array of weeks tested
        profile_name: Profile name
        profile_weights: JSON of profile weights
        week_results: JSON array of per-week results
        overall_avg_score: Average score across all weeks
        overall_top_score: Best score across all weeks
        overall_optimal_score: Perfect hindsight score
        avg_gap_from_optimal: Average % below optimal
        notes: User notes
    """
    __tablename__ = 'backtest_results'
    
    backtest_id = Column(String, primary_key=True)
    run_timestamp = Column(DateTime, default=datetime.utcnow)
    weeks_tested = Column(Text, nullable=False)  # JSON array
    profile_name = Column(String, nullable=False)
    profile_weights = Column(Text, nullable=False)  # JSON
    week_results = Column(Text, nullable=False)  # JSON array
    overall_avg_score = Column(Float)
    overall_top_score = Column(Float)
    overall_optimal_score = Column(Float)
    avg_gap_from_optimal = Column(Float)
    notes = Column(Text)
    
    def __repr__(self) -> str:
        return (
            f"<BacktestResult(id='{self.backtest_id}', "
            f"profile='{self.profile_name}', "
            f"avg={self.overall_avg_score}, gap={self.avg_gap_from_optimal}%)>"
        )


# Database session factory
def create_session(db_path: str = "dfs_optimizer.db"):
    """
    Create a SQLAlchemy session for database operations.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        Session: SQLAlchemy session object
    """
    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    return Session()


# Helper functions for common queries
def get_vegas_lines_by_week(session, week: int) -> list:
    """Get all Vegas lines for a specific week."""
    return session.query(VegasLine).filter(VegasLine.week == week).all()


def get_itt_for_team(session, team: str, week: int) -> Optional[float]:
    """Get ITT for a specific team in a specific week."""
    lines = session.query(VegasLine).filter(
        VegasLine.week == week,
        (VegasLine.home_team == team) | (VegasLine.away_team == team)
    ).first()
    
    if lines:
        return lines.get_itt(team)
    return None


def get_injury_reports_by_week(session, week: int) -> list:
    """Get all injury reports for a specific week."""
    return session.query(InjuryReport).filter(InjuryReport.week == week).all()


def get_active_injuries_by_week(session, week: int) -> list:
    """Get only active injuries (Q, D, O) for a specific week."""
    return session.query(InjuryReport).filter(
        InjuryReport.week == week,
        InjuryReport.injury_status.in_(['Q', 'D', 'O'])
    ).all()


def get_flags_for_player(session, player_name: str, team: str, week: int) -> list:
    """Get all flags for a specific player in a specific week."""
    return session.query(NarrativeFlag).filter(
        NarrativeFlag.week == week,
        NarrativeFlag.player_name == player_name,
        NarrativeFlag.team == team
    ).all()


def get_recent_api_calls(session, api_name: str, hours: int = 24) -> list:
    """Get API calls for a specific API in the last N hours."""
    from datetime import timedelta
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    
    return session.query(APICallLog).filter(
        APICallLog.api_name == api_name,
        APICallLog.called_at >= cutoff_time
    ).all()

