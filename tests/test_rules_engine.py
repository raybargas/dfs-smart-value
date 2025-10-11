"""
Tests for Smart Rules Engine (Phase 2C)
"""

import pytest
from datetime import datetime
import tempfile
import os

from src.rules_engine import SmartRulesEngine
from src.database_models import Base, VegasLine, InjuryReport, NarrativeFlag

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
def rules_engine(test_db_path, db_session):
    """Create SmartRulesEngine instance with test data."""
    # Insert test Vegas lines
    vegas_line_high = VegasLine(
        week=1,
        game_id='test_game_1',
        home_team='KC',
        away_team='BUF',
        home_spread=-3.0,
        away_spread=3.0,
        total=52.5,
        home_itt=27.8,
        away_itt=24.8,
        fetched_at=datetime.now()
    )
    
    vegas_line_low = VegasLine(
        week=1,
        game_id='test_game_2',
        home_team='CHI',
        away_team='CAR',
        home_spread=-1.5,
        away_spread=1.5,
        total=38.0,
        home_itt=19.8,
        away_itt=18.3,
        fetched_at=datetime.now()
    )
    
    db_session.add(vegas_line_high)
    db_session.add(vegas_line_low)
    db_session.commit()
    
    # Create engine
    engine = SmartRulesEngine(db_path=test_db_path, week=1)
    yield engine
    engine.close()


# ===== QB Tests =====

def test_qb_low_itt_red_flag(rules_engine):
    """Test QB with low ITT gets red flag."""
    flags = rules_engine.evaluate_player(
        player_name='Justin Fields',
        team='CHI',
        position='QB',
        salary=6000,
        projected_points=18.5,
        projected_ceiling=25.0
    )
    
    # Should have low ITT flag
    itt_flags = [f for f in flags if f['flag_category'] == 'low_itt']
    assert len(itt_flags) == 1
    assert itt_flags[0]['severity'] == 'red'
    assert '19.8' in itt_flags[0]['message']


def test_qb_high_itt_green_flag(rules_engine):
    """Test QB with high ITT gets green flag."""
    flags = rules_engine.evaluate_player(
        player_name='Patrick Mahomes',
        team='KC',
        position='QB',
        salary=8500,
        projected_points=24.0,
        projected_ceiling=32.0
    )
    
    # Should have high ITT flag
    itt_flags = [f for f in flags if f['flag_category'] == 'high_itt']
    assert len(itt_flags) == 1
    assert itt_flags[0]['severity'] == 'green'
    assert '27.8' in itt_flags[0]['message']


# ===== RB Tests =====

def test_rb_low_attempts_red_flag(rules_engine):
    """Test RB with low attempts gets red flag."""
    flags = rules_engine.evaluate_player(
        player_name='Committee Back',
        team='KC',
        position='RB',
        salary=5000,
        projected_points=10.0,
        projected_ceiling=15.0,
        attempts=8
    )
    
    # Should have low volume flag
    volume_flags = [f for f in flags if f['flag_category'] == 'low_volume']
    assert len(volume_flags) == 1
    assert volume_flags[0]['severity'] == 'red'
    assert '8 attempts' in volume_flags[0]['message']


def test_rb_salary_ceiling_mismatch(rules_engine):
    """Test RB with high salary but low ceiling gets red flag."""
    flags = rules_engine.evaluate_player(
        player_name='Expensive RB',
        team='KC',
        position='RB',
        salary=9000,
        projected_points=18.0,
        projected_ceiling=22.0,  # Needs 31.5 (9 * 3.5)
        attempts=18
    )
    
    # Should have salary/ceiling mismatch flag
    mismatch_flags = [f for f in flags if f['flag_category'] == 'salary_ceiling_mismatch']
    assert len(mismatch_flags) == 1
    assert mismatch_flags[0]['severity'] == 'red'
    assert '31.5' in mismatch_flags[0]['message']


def test_rb_good_value(rules_engine):
    """Test RB with good value (no negative flags)."""
    flags = rules_engine.evaluate_player(
        player_name='Value RB',
        team='KC',
        position='RB',
        salary=6500,
        projected_points=16.0,
        projected_ceiling=26.0,
        attempts=16
    )
    
    # Should have no red flags
    red_flags = [f for f in flags if f['severity'] == 'red']
    assert len(red_flags) == 0


# ===== WR Tests =====

def test_wr_80_20_regression_flag(rules_engine):
    """Test WR with 20+ points last week gets regression warning."""
    flags = rules_engine.evaluate_player(
        player_name='Hot WR',
        team='KC',
        position='WR',
        salary=7000,
        projected_points=18.0,
        projected_ceiling=28.0,
        last_week_points=24.5,
        snaps=55,
        routes=42
    )
    
    # Should have 80/20 regression flag
    regression_flags = [f for f in flags if f['flag_category'] == '80_20_regression']
    assert len(regression_flags) == 1
    assert regression_flags[0]['severity'] == 'yellow'
    assert '24.5' in regression_flags[0]['message']


def test_wr_low_snaps_red_flag(rules_engine):
    """Test WR with low snaps gets red flag."""
    flags = rules_engine.evaluate_player(
        player_name='Limited WR',
        team='KC',
        position='WR',
        salary=5000,
        projected_points=8.0,
        projected_ceiling=14.0,
        snaps=12,
        routes=10
    )
    
    # Should have low snaps AND low routes flags
    snap_flags = [f for f in flags if f['flag_category'] == 'low_snaps']
    route_flags = [f for f in flags if f['flag_category'] == 'low_routes']
    
    assert len(snap_flags) == 1
    assert snap_flags[0]['severity'] == 'red'
    assert len(route_flags) == 1
    assert route_flags[0]['severity'] == 'red'


def test_wr_leverage_play_green_flag(rules_engine):
    """Test WR with low ownership + high ceiling gets leverage flag."""
    flags = rules_engine.evaluate_player(
        player_name='Leverage WR',
        team='KC',
        position='WR',
        salary=6000,
        projected_points=14.0,
        projected_ceiling=24.0,
        projected_ownership=7.5,
        snaps=48,
        routes=35
    )
    
    # Should have leverage play flag
    leverage_flags = [f for f in flags if f['flag_category'] == 'leverage_play']
    assert len(leverage_flags) == 1
    assert leverage_flags[0]['severity'] == 'green'
    assert '7.5%' in leverage_flags[0]['message']
    assert '24.0' in leverage_flags[0]['message']


def test_wr_value_play_under_4k(rules_engine):
    """Test cheap WR with strong value gets green flag."""
    flags = rules_engine.evaluate_player(
        player_name='Value WR',
        team='KC',
        position='WR',
        salary=3500,
        projected_points=11.0,  # 11.0 / 3.5 = 3.14x
        projected_ceiling=18.0,
        snaps=35,
        routes=28
    )
    
    # Should have value play flag (not low salary warning)
    value_flags = [f for f in flags if f['flag_category'] == 'value_play']
    assert len(value_flags) == 1
    assert value_flags[0]['severity'] == 'green'


def test_wr_low_salary_no_value(rules_engine):
    """Test cheap WR without strong value gets yellow flag."""
    flags = rules_engine.evaluate_player(
        player_name='Cheap WR',
        team='KC',
        position='WR',
        salary=3500,
        projected_points=8.0,  # 8.0 / 3.5 = 2.29x (not enough)
        projected_ceiling=12.0,
        snaps=30,
        routes=22
    )
    
    # Should have low salary warning
    salary_flags = [f for f in flags if f['flag_category'] == 'low_salary']
    assert len(salary_flags) == 1
    assert salary_flags[0]['severity'] == 'yellow'


# ===== TE Tests =====

def test_te_blocking_te_red_flag(rules_engine):
    """Test blocking TE gets red flags."""
    flags = rules_engine.evaluate_player(
        player_name='Blocking TE',
        team='KC',
        position='TE',
        salary=3500,
        projected_points=6.0,
        projected_ceiling=10.0,
        snaps=15,
        routes=8
    )
    
    # Should have blocking TE and low routes flags
    blocking_flags = [f for f in flags if f['flag_category'] == 'blocking_te']
    route_flags = [f for f in flags if f['flag_category'] == 'low_routes']
    
    assert len(blocking_flags) == 1
    assert blocking_flags[0]['severity'] == 'red'
    assert len(route_flags) == 1
    assert route_flags[0]['severity'] == 'red'


def test_te_low_salary_red_flag(rules_engine):
    """Test TE under $3K gets red flag."""
    flags = rules_engine.evaluate_player(
        player_name='Cheap TE',
        team='KC',
        position='TE',
        salary=2800,
        projected_points=5.0,
        projected_ceiling=8.0,
        snaps=25,
        routes=15
    )
    
    # Should have low salary flag
    salary_flags = [f for f in flags if f['flag_category'] == 'low_salary']
    assert len(salary_flags) == 1
    assert salary_flags[0]['severity'] == 'red'


def test_te_good_value(rules_engine):
    """Test good TE (route-runner) has no red flags."""
    flags = rules_engine.evaluate_player(
        player_name='Good TE',
        team='KC',
        position='TE',
        salary=5500,
        projected_points=12.0,
        projected_ceiling=18.0,
        snaps=48,
        routes=32
    )
    
    # Should have no red flags
    red_flags = [f for f in flags if f['severity'] == 'red']
    assert len(red_flags) == 0


# ===== DST Tests =====

def test_dst_weak_oline_matchup_green_flag(rules_engine):
    """Test DST facing bottom 5 O-line gets green flag."""
    flags = rules_engine.evaluate_player(
        player_name='Chiefs DST',
        team='KC',
        position='DST',
        salary=3200,
        projected_points=9.0,
        opponent_team='CAR',
        opponent_oline_rank=30
    )
    
    # Should have weak O-line matchup flag
    oline_flags = [f for f in flags if f['flag_category'] == 'weak_oline_matchup']
    assert len(oline_flags) == 1
    assert oline_flags[0]['severity'] == 'green'
    assert '30/32' in oline_flags[0]['message']


def test_dst_strong_oline_matchup_yellow_flag(rules_engine):
    """Test DST facing top 10 O-line gets yellow flag."""
    flags = rules_engine.evaluate_player(
        player_name='Bills DST',
        team='BUF',
        position='DST',
        salary=2800,
        projected_points=6.0,
        opponent_team='KC',
        opponent_oline_rank=5
    )
    
    # Should have strong O-line matchup warning
    oline_flags = [f for f in flags if f['flag_category'] == 'strong_oline_matchup']
    assert len(oline_flags) == 1
    assert oline_flags[0]['severity'] == 'yellow'


# ===== Integration Tests =====

def test_evaluate_and_store_flags(rules_engine, db_session):
    """Test evaluating multiple players and storing flags."""
    players = [
        {
            'player_name': 'Patrick Mahomes',
            'team': 'KC',
            'position': 'QB',
            'salary': 8500,
            'projected_points': 24.0,
            'projected_ceiling': 32.0
        },
        {
            'player_name': 'Committee Back',
            'team': 'KC',
            'position': 'RB',
            'salary': 5000,
            'projected_points': 10.0,
            'projected_ceiling': 15.0,
            'attempts': 8
        }
    ]
    
    results = rules_engine.evaluate_and_store(players)
    
    # Check results returned
    assert 'Patrick Mahomes' in results
    assert 'Committee Back' in results
    assert len(results['Patrick Mahomes']) > 0
    assert len(results['Committee Back']) > 0
    
    # Check flags stored in database
    flags = db_session.query(NarrativeFlag).all()
    assert len(flags) > 0
    
    # Check specific flags
    mahomes_flags = [f for f in flags if f.player_name == 'Patrick Mahomes']
    assert len(mahomes_flags) > 0
    assert mahomes_flags[0].week == 1
    assert mahomes_flags[0].team == 'KC'


def test_get_team_itt(rules_engine):
    """Test getting ITT for teams."""
    # High ITT team
    kc_itt = rules_engine.get_team_itt('KC')
    assert kc_itt == 27.8
    
    # Low ITT team
    chi_itt = rules_engine.get_team_itt('CHI')
    assert chi_itt == 19.8
    
    # Non-existent team
    fake_itt = rules_engine.get_team_itt('FAKE')
    assert fake_itt is None


def test_store_flags(rules_engine, db_session):
    """Test storing flags to database."""
    flags = [
        {
            'flag_category': 'low_itt',  # Use a valid category from the map
            'message': 'Test message',
            'severity': 'yellow'
        }
    ]
    
    rules_engine.store_flags('Test Player', 'KC', 'QB', flags)
    
    # Query database
    stored_flags = db_session.query(NarrativeFlag).filter_by(
        player_name='Test Player'
    ).all()
    
    assert len(stored_flags) == 1
    assert stored_flags[0].flag_category == 'itt'  # Mapped from 'low_itt'
    assert stored_flags[0].message == 'Test message'
    assert stored_flags[0].severity == 'yellow'
    assert stored_flags[0].flag_type == 'caution'  # Mapped from 'yellow'
    assert stored_flags[0].position == 'QB'
    assert stored_flags[0].team == 'KC'
    assert stored_flags[0].week == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

