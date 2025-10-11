"""
Tests for Player Context Builder (Phase 2C)
"""

import pytest
import pandas as pd
from datetime import datetime
import tempfile
import os

from src.player_context_builder import PlayerContextBuilder
from src.database_models import Base, VegasLine, InjuryReport

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


# ===== Fixtures =====

@pytest.fixture(scope='function')
def test_db_path():
    """Create a temporary database file for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except:
        pass


@pytest.fixture(scope='function')
def db_session(test_db_path):
    """Create test database with schema."""
    engine = create_engine(f'sqlite:///{test_db_path}')
    Base.metadata.create_all(engine)
    
    # Create Phase 2C tables
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vegas_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week INTEGER NOT NULL,
                game_id TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                home_spread REAL,
                away_spread REAL,
                total REAL,
                home_itt REAL,
                away_itt REAL,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(week, game_id)
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS injury_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                team TEXT NOT NULL,
                position TEXT,
                injury_status TEXT CHECK(injury_status IN ('Q', 'D', 'O', 'IR', 'PUP', 'NFI', NULL)),
                practice_status TEXT CHECK(practice_status IN ('Full', 'Limited', 'DNP', NULL)),
                body_part TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(week, player_name, team)
            )
        """))
        
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS narrative_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                team TEXT NOT NULL,
                position TEXT NOT NULL,
                flag_type TEXT NOT NULL CHECK(flag_type IN ('optimal', 'caution', 'warning')),
                flag_category TEXT NOT NULL CHECK(flag_category IN (
                    'itt', 'salary_ceiling', 'snap_count', 'routes', 'committee', 
                    'regression', 'price_floor', 'stacking', 'matchup', 'other'
                )),
                message TEXT NOT NULL,
                severity TEXT NOT NULL CHECK(severity IN ('green', 'yellow', 'red')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK(LENGTH(message) > 0)
            )
        """))
        
        conn.commit()
    
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_vegas_lines(db_session):
    """Insert sample Vegas lines."""
    lines = [
        VegasLine(
            week=1,
            game_id='kc_buf_2025',
            home_team='KC',
            away_team='BUF',
            home_spread=-3.0,
            away_spread=3.0,
            total=52.5,
            home_itt=27.8,
            away_itt=24.8,
            fetched_at=datetime.now()
        ),
        VegasLine(
            week=1,
            game_id='sf_sea_2025',
            home_team='SF',
            away_team='SEA',
            home_spread=-7.0,
            away_spread=7.0,
            total=48.0,
            home_itt=27.5,
            away_itt=20.5,
            fetched_at=datetime.now()
        )
    ]
    for line in lines:
        db_session.add(line)
    db_session.commit()


@pytest.fixture
def sample_injuries(db_session):
    """Insert sample injury reports."""
    injuries = [
        InjuryReport(
            week=1,
            player_name='Christian McCaffrey',
            team='SF',
            position='RB',
            injury_status='Q',
            practice_status='Limited',
            body_part='Hamstring',
            description='Hamstring strain',
            updated_at=datetime.now()
        ),
        InjuryReport(
            week=1,
            player_name='Tyreek Hill',
            team='MIA',
            position='WR',
            injury_status='Q',
            practice_status='Full',
            body_part='Ankle',
            description='Ankle sprain',
            updated_at=datetime.now()
        )
    ]
    for injury in injuries:
        db_session.add(injury)
    db_session.commit()


@pytest.fixture
def sample_player_df():
    """Create sample player DataFrame."""
    return pd.DataFrame([
        {
            'Name': 'Patrick Mahomes',
            'Team': 'KC',
            'Position': 'QB',
            'Salary': 8500,
            'AvgPointsPerGame': 24.5,
            'Ceiling': 32.0
        },
        {
            'Name': 'Christian McCaffrey',
            'Team': 'SF',
            'Position': 'RB',
            'Salary': 9500,
            'AvgPointsPerGame': 22.0,
            'Ceiling': 30.0,
            'Attempts': 18
        },
        {
            'Name': 'Deebo Samuel',
            'Team': 'SF',
            'Position': 'WR',
            'Salary': 7000,
            'AvgPointsPerGame': 15.5,
            'Ceiling': 25.0,
            'Snaps': 50,
            'Routes': 35
        }
    ])


@pytest.fixture
def sample_prior_week_df():
    """Create sample prior week DataFrame."""
    return pd.DataFrame([
        {
            'Name': 'Deebo Samuel',
            'Team': 'SF',
            'FantasyPoints': 24.5
        },
        {
            'Name': 'Christian McCaffrey',
            'Team': 'SF',
            'FantasyPoints': 18.2
        }
    ])


@pytest.fixture
def context_builder(test_db_path, db_session, sample_vegas_lines, sample_injuries):
    """Create PlayerContextBuilder instance with test data."""
    builder = PlayerContextBuilder(week=1, db_path=test_db_path)
    yield builder
    builder.close()


# ===== Tests =====

def test_initialization(context_builder):
    """Test PlayerContextBuilder initialization."""
    assert context_builder.week == 1
    assert context_builder.session is not None
    assert context_builder.rules_engine is not None
    assert len(context_builder.vegas_lines_cache) > 0
    assert len(context_builder.injury_reports_cache) > 0


def test_load_vegas_lines(context_builder):
    """Test Vegas lines loading."""
    vegas_cache = context_builder.vegas_lines_cache
    
    # Should have 4 entries (2 games * 2 teams)
    assert len(vegas_cache) == 4
    
    # Check KC data
    assert 'KC' in vegas_cache
    assert vegas_cache['KC']['itt'] == 27.8
    assert vegas_cache['KC']['opponent'] == 'BUF'
    assert vegas_cache['KC']['is_home'] is True
    
    # Check BUF data
    assert 'BUF' in vegas_cache
    assert vegas_cache['BUF']['itt'] == 24.8
    assert vegas_cache['BUF']['opponent'] == 'KC'
    assert vegas_cache['BUF']['is_home'] is False


def test_load_injury_reports(context_builder):
    """Test injury reports loading."""
    injury_cache = context_builder.injury_reports_cache
    
    # Should have 2 entries
    assert len(injury_cache) == 2
    
    # Check CMC data
    key = ('Christian McCaffrey', 'SF')
    assert key in injury_cache
    assert injury_cache[key]['status'] == 'Q'
    assert injury_cache[key]['body_part'] == 'Hamstring'
    assert injury_cache[key]['practice_status'] == 'Limited'


def test_get_itt(context_builder):
    """Test ITT retrieval."""
    # Existing team
    assert context_builder._get_itt('KC') == 27.8
    assert context_builder._get_itt('SF') == 27.5
    
    # Non-existent team
    assert context_builder._get_itt('FAKE') is None
    assert context_builder._get_itt(None) is None


def test_get_opponent(context_builder):
    """Test opponent retrieval."""
    # Existing team
    assert context_builder._get_opponent('KC') == 'BUF'
    assert context_builder._get_opponent('SF') == 'SEA'
    
    # Non-existent team
    assert context_builder._get_opponent('FAKE') is None


def test_get_injury_status(context_builder):
    """Test injury status retrieval."""
    # Injured player
    assert context_builder._get_injury_status('Christian McCaffrey', 'SF') == 'Q'
    assert context_builder._get_injury_status('Tyreek Hill', 'MIA') == 'Q'
    
    # Healthy player
    assert context_builder._get_injury_status('Patrick Mahomes', 'KC') is None
    
    # Non-existent player
    assert context_builder._get_injury_status('Fake Player', 'SF') is None


def test_get_injury_details(context_builder):
    """Test injury details retrieval."""
    details = context_builder._get_injury_details('Christian McCaffrey', 'SF')
    
    assert details is not None
    assert 'Q' in details
    assert 'Hamstring' in details
    assert 'Limited' in details


def test_get_prior_week_points(context_builder, sample_prior_week_df):
    """Test prior week points retrieval."""
    # Player with data
    points = context_builder._get_prior_week_points('Deebo Samuel', sample_prior_week_df)
    assert points == 24.5
    
    # Player without data
    points = context_builder._get_prior_week_points('Patrick Mahomes', sample_prior_week_df)
    assert points is None


def test_calculate_player_score(context_builder):
    """Test player score calculation."""
    # Green score: no red, no/few yellow
    assert context_builder._calculate_player_score(0, 0, 2) == 'green'
    assert context_builder._calculate_player_score(0, 1, 1) == 'green'
    
    # Yellow score: some yellow, no red
    assert context_builder._calculate_player_score(0, 2, 0) == 'yellow'
    assert context_builder._calculate_player_score(0, 1, 0) == 'yellow'
    
    # Red score: any red flags
    assert context_builder._calculate_player_score(1, 0, 0) == 'red'
    assert context_builder._calculate_player_score(2, 1, 1) == 'red'


def test_enrich_players_basic(context_builder, sample_player_df):
    """Test basic player enrichment."""
    enriched = context_builder.enrich_players(sample_player_df)
    
    # Should have same number of rows
    assert len(enriched) == len(sample_player_df)
    
    # Should have new columns
    assert 'itt' in enriched.columns
    assert 'opponent' in enriched.columns
    assert 'injury_status' in enriched.columns
    assert 'injury_details' in enriched.columns
    assert 'flags' in enriched.columns
    assert 'flag_count' in enriched.columns
    assert 'red_flags' in enriched.columns
    assert 'yellow_flags' in enriched.columns
    assert 'green_flags' in enriched.columns
    assert 'player_score' in enriched.columns


def test_enrich_players_itt(context_builder, sample_player_df):
    """Test ITT enrichment."""
    enriched = context_builder.enrich_players(sample_player_df)
    
    # Patrick Mahomes (KC)
    mahomes_row = enriched[enriched['Name'] == 'Patrick Mahomes'].iloc[0]
    assert mahomes_row['itt'] == 27.8
    assert mahomes_row['opponent'] == 'BUF'
    
    # Christian McCaffrey (SF)
    cmc_row = enriched[enriched['Name'] == 'Christian McCaffrey'].iloc[0]
    assert cmc_row['itt'] == 27.5
    assert cmc_row['opponent'] == 'SEA'


def test_enrich_players_injury(context_builder, sample_player_df):
    """Test injury enrichment."""
    enriched = context_builder.enrich_players(sample_player_df)
    
    # Christian McCaffrey (injured)
    cmc_row = enriched[enriched['Name'] == 'Christian McCaffrey'].iloc[0]
    assert cmc_row['injury_status'] == 'Q'
    assert 'Hamstring' in cmc_row['injury_details']
    
    # Patrick Mahomes (healthy)
    mahomes_row = enriched[enriched['Name'] == 'Patrick Mahomes'].iloc[0]
    assert pd.isna(mahomes_row['injury_status'])


def test_enrich_players_with_prior_week(context_builder, sample_player_df, sample_prior_week_df):
    """Test enrichment with prior week data."""
    enriched = context_builder.enrich_players(sample_player_df, prior_week_df=sample_prior_week_df)
    
    # Should have last_week_points column
    assert 'last_week_points' in enriched.columns
    
    # Deebo Samuel should have prior week points
    deebo_row = enriched[enriched['Name'] == 'Deebo Samuel'].iloc[0]
    assert deebo_row['last_week_points'] == 24.5
    
    # Patrick Mahomes should not
    mahomes_row = enriched[enriched['Name'] == 'Patrick Mahomes'].iloc[0]
    assert pd.isna(mahomes_row['last_week_points'])


def test_enrich_players_flags(context_builder, sample_player_df):
    """Test flag generation during enrichment."""
    enriched = context_builder.enrich_players(sample_player_df)
    
    # All players should have flags evaluated
    for idx, row in enriched.iterrows():
        assert isinstance(row['flags'], list)
        
        # Flag counts should be consistent
        red_count = sum(1 for f in row['flags'] if f.get('severity') == 'red')
        yellow_count = sum(1 for f in row['flags'] if f.get('severity') == 'yellow')
        green_count = sum(1 for f in row['flags'] if f.get('severity') == 'green')
        
        assert row['red_flags'] == red_count
        assert row['yellow_flags'] == yellow_count
        assert row['green_flags'] == green_count
        assert row['flag_count'] == len(row['flags'])


def test_enrich_players_player_score(context_builder, sample_player_df):
    """Test player score calculation during enrichment."""
    enriched = context_builder.enrich_players(sample_player_df)
    
    # All players should have a score
    for idx, row in enriched.iterrows():
        assert row['player_score'] in ['green', 'yellow', 'red']


def test_get_enrichment_stats(context_builder):
    """Test enrichment statistics."""
    stats = context_builder.get_enrichment_stats()
    
    assert stats['week'] == 1
    assert stats['vegas_lines_loaded'] == 4  # 2 games * 2 teams
    assert stats['injury_reports_loaded'] == 2
    assert 'KC' in stats['teams_with_itt']
    assert 'SF' in stats['teams_with_itt']


def test_case_insensitive_columns(context_builder):
    """Test that enrichment works with lowercase column names."""
    # Create DataFrame with lowercase columns
    df_lowercase = pd.DataFrame([
        {
            'name': 'Patrick Mahomes',
            'team': 'KC',
            'position': 'QB',
            'salary': 8500,
            'avg_points_per_game': 24.5,
            'ceiling': 32.0
        }
    ])
    
    enriched = context_builder.enrich_players(df_lowercase)
    
    # Should work without errors
    assert len(enriched) == 1
    assert 'itt' in enriched.columns
    assert enriched.iloc[0]['itt'] == 27.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

