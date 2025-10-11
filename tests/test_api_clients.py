"""
Tests for API clients (BaseAPIClient, OddsAPIClient, MySportsFeedsClient).
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import requests
import tempfile
import os

from src.api.base_client import BaseAPIClient, APIError, RateLimitError, TimeoutError
from src.api.odds_api import OddsAPIClient
from src.api.mysportsfeeds_api import MySportsFeedsClient
from src.database_models import Base, VegasLine, InjuryReport, APICallLog

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


# ===== Fixtures =====

@pytest.fixture(scope='function')
def test_db_path():
    """Create a temporary database file for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)  # Close the file descriptor
    yield path
    # Cleanup
    try:
        os.unlink(path)
    except:
        pass


@pytest.fixture(scope='function')
def db_session(test_db_path):
    """Create shared test database with proper schema."""
    # Use the shared temporary database file
    engine = create_engine(f'sqlite:///{test_db_path}')
    
    # Create tables from ORM models
    Base.metadata.create_all(engine)
    
    # Manually create the Phase 2C tables with correct schema (drop and recreate to remove constraints)
    with engine.connect() as conn:
        # Drop and recreate api_call_log without api_name constraint for testing
        conn.execute(text("DROP TABLE IF EXISTS api_call_log"))
        
        # Create vegas_lines table
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
        
        # Create injury_reports table
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
        
        # Create api_call_log table (relaxed constraints for testing)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS api_call_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_name TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                status_code INTEGER,
                response_time_ms INTEGER,
                error_message TEXT,
                called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK(status_code IS NULL OR (status_code >= 100 AND status_code < 600)),
                CHECK(response_time_ms IS NULL OR response_time_ms >= 0)
            )
        """))
        
        # Create narrative_flags table (for completeness)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS narrative_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                team TEXT NOT NULL,
                flag_category TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL CHECK(severity IN ('green', 'yellow', 'red')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        conn.commit()
    
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def base_client(db_session, test_db_path):
    """Create BaseAPIClient instance for testing."""
    client = BaseAPIClient(
        api_name="TestAPI",
        base_url="https://api.test.com",
        api_key="test_key",
        db_path=test_db_path,
        timeout=5,
        max_retries=2,
        retry_delay=0.1
    )
    yield client
    client.close()


@pytest.fixture
def odds_client(db_session, test_db_path):
    """Create OddsAPIClient instance for testing."""
    client = OddsAPIClient(
        api_key="test_odds_key",
        db_path=test_db_path
    )
    yield client
    client.close()


@pytest.fixture
def mysportsfeeds_client(db_session, test_db_path):
    """Create MySportsFeedsClient instance for testing."""
    client = MySportsFeedsClient(
        api_key="test_msf_key",
        db_path=test_db_path
    )
    yield client
    client.close()


# ===== BaseAPIClient Tests =====

def test_base_client_initialization(base_client):
    """Test BaseAPIClient initializes correctly."""
    assert base_client.api_name == "TestAPI"
    assert base_client.base_url == "https://api.test.com"
    assert base_client.api_key == "test_key"
    assert base_client.timeout == 5
    assert base_client.max_retries == 2


@patch('src.api.base_client.requests.request')
def test_base_client_successful_request(mock_request, base_client):
    """Test successful API request."""
    # Mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.ok = True
    mock_response.json.return_value = {'data': 'test'}
    mock_response.content = b'{"data": "test"}'
    mock_request.return_value = mock_response
    
    result = base_client._make_request('test/endpoint')
    
    assert result == {'data': 'test'}
    mock_request.assert_called_once()


@patch('src.api.base_client.requests.request')
def test_base_client_rate_limit_error(mock_request, base_client):
    """Test rate limit error (429) raises RateLimitError."""
    # Mock 429 response
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.text = 'Rate limit exceeded'
    mock_response.content = b'Rate limit exceeded'
    mock_request.return_value = mock_response
    
    with pytest.raises(RateLimitError):
        base_client._make_request('test/endpoint')


@patch('src.api.base_client.requests.request')
def test_base_client_server_error_retry(mock_request, base_client):
    """Test server error (500) triggers retry logic."""
    # Mock 500 response
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.text = 'Internal server error'
    mock_response.content = b'Internal server error'
    mock_request.return_value = mock_response
    
    with pytest.raises(APIError):
        base_client._make_request('test/endpoint')
    
    # Should retry max_retries times
    assert mock_request.call_count == base_client.max_retries


@patch('src.api.base_client.requests.request')
def test_base_client_timeout_error(mock_request, base_client):
    """Test timeout raises TimeoutError."""
    # Mock timeout
    mock_request.side_effect = requests.exceptions.Timeout("Timeout")
    
    with pytest.raises(TimeoutError):
        base_client._make_request('test/endpoint')
    
    # Should retry max_retries times
    assert mock_request.call_count == base_client.max_retries


@patch('src.api.base_client.requests.request')
def test_base_client_network_error(mock_request, base_client):
    """Test network error raises APIError."""
    # Mock network error
    mock_request.side_effect = requests.exceptions.ConnectionError("Network error")
    
    with pytest.raises(APIError):
        base_client._make_request('test/endpoint')


def test_base_client_get_recent_call_count(base_client):
    """Test get_recent_call_count retrieves correct count."""
    # Log some API calls
    base_client._log_api_call('test/endpoint', 200, 1.5, 150)
    base_client._log_api_call('test/endpoint2', 200, 2.0, 200)
    
    # Get count
    count = base_client.get_recent_call_count(hours=1)
    assert count == 2


# ===== OddsAPIClient Tests =====

@patch('src.api.base_client.requests.request')
def test_odds_client_fetch_nfl_odds_success(mock_request, odds_client):
    """Test OddsAPIClient fetches and parses odds correctly."""
    # Mock successful API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.ok = True
    mock_response.content = b'[{"id": "test"}]'
    mock_response.json.return_value = [
        {
            'id': 'nfl_gb_chi_2025',
            'sport_key': 'americanfootball_nfl',
            'home_team': 'Green Bay Packers',
            'away_team': 'Chicago Bears',
            'commence_time': '2025-09-10T18:15:00Z',
            'bookmakers': [
                {
                    'key': 'draftkings',
                    'markets': [
                        {
                            'key': 'spreads',
                            'outcomes': [
                                {'name': 'Green Bay Packers', 'point': -3.5},
                                {'name': 'Chicago Bears', 'point': 3.5}
                            ]
                        },
                        {
                            'key': 'totals',
                            'outcomes': [
                                {'name': 'Over', 'point': 45.5}
                            ]
                        }
                    ]
                }
            ]
        }
    ]
    mock_request.return_value = mock_response
    
    # Fetch odds
    result = odds_client.fetch_nfl_odds(use_cache=False)
    
    assert len(result) == 1
    assert result[0]['game_id'] == 'nfl_gb_chi_2025'
    assert result[0]['home_team'] == 'Green Bay Packers'
    assert result[0]['spread_home'] == -3.5
    assert result[0]['total'] == 45.5
    assert result[0]['itt_home'] == 24.5  # (45.5 / 2) + (3.5 / 2)
    assert result[0]['itt_away'] == 21.0  # (45.5 / 2) - (3.5 / 2)


def test_odds_client_calculate_itt():
    """Test ITT calculation formula."""
    client = OddsAPIClient(api_key="test")
    
    # Test positive spread (home favored)
    itt_home, itt_away = client._calculate_itt(total=45.5, spread_home=-3.5)
    assert itt_home == 24.5
    assert itt_away == 21.0
    
    # Test positive spread (away favored - home is underdog)
    itt_home, itt_away = client._calculate_itt(total=50.0, spread_home=7.0)
    assert itt_home == 21.5  # Home is underdog, gets fewer points
    assert itt_away == 28.5  # Away is favored, gets more points
    
    # Test pick'em (spread = 0)
    itt_home, itt_away = client._calculate_itt(total=48.0, spread_home=0.0)
    assert itt_home == 24.0
    assert itt_away == 24.0
    
    # Test None values
    itt_home, itt_away = client._calculate_itt(total=None, spread_home=-3.5)
    assert itt_home is None
    assert itt_away is None
    
    client.close()


def test_odds_client_cache_behavior(odds_client, db_session):
    """Test odds caching behavior."""
    # Store test data in database
    vegas_line = VegasLine(
        week=1,
        game_id='test_game',
        home_team='Team A',
        away_team='Team B',
        home_spread=-3.5,
        away_spread=3.5,
        total=45.5,
        home_itt=24.5,
        away_itt=21.0,
        fetched_at=datetime.now()
    )
    odds_client.db_session.add(vegas_line)
    odds_client.db_session.commit()
    
    # Fetch from cache
    cached_data = odds_client._get_cached_odds(cache_ttl_hours=24)
    
    assert cached_data is not None
    assert len(cached_data) == 1
    assert cached_data[0]['game_id'] == 'test_game'
    assert cached_data[0]['itt_home'] == 24.5


# ===== MySportsFeedsClient Tests =====

@patch('src.api.base_client.requests.request')
def test_mysportsfeeds_client_fetch_injuries_success(mock_request, mysportsfeeds_client):
    """Test MySportsFeedsClient fetches and parses injuries correctly."""
    # Mock successful API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.ok = True
    mock_response.content = b'[{"PlayerID": 12345}]'
    mock_response.json.return_value = [
        {
            'PlayerID': 12345,
            'Name': 'Christian McCaffrey',
            'Team': 'SF',
            'InjuryStatus': 'Q',  # Use valid constraint value
            'PracticeStatus': 'Limited',  # Use valid constraint value
            'BodyPart': 'Hamstring',
            'InjuryDescription': 'Hamstring strain',
            'Updated': '2025-09-10T14:30:00'
        }
    ]
    mock_request.return_value = mock_response
    
    # Fetch injuries
    result = mysportsfeeds_client.fetch_injuries(season=2025, week=1, use_cache=False)
    
    assert len(result) == 1
    assert result[0]['player_name'] == 'Christian McCaffrey'
    assert result[0]['team'] == 'SF'
    assert result[0]['injury_status'] == 'Q'
    assert result[0]['body_part'] == 'Hamstring'


def test_mysportsfeeds_client_cache_behavior(mysportsfeeds_client, db_session):
    """Test injury report caching behavior."""
    # Store test data in database
    injury_report = InjuryReport(
        week=1,
        player_name='Test Player',
        team='SF',
        position='RB',
        injury_status='Q',
        practice_status='Limited',
        body_part='Hamstring',
        description='Test injury',
        updated_at=datetime.now()
    )
    mysportsfeeds_client.db_session.add(injury_report)
    mysportsfeeds_client.db_session.commit()
    
    # Fetch from cache
    cached_data = mysportsfeeds_client._get_cached_injuries(cache_ttl_hours=6)
    
    assert cached_data is not None
    assert len(cached_data) == 1
    assert cached_data[0]['player_name'] == 'Test Player'


# ===== Integration Tests =====

def test_api_call_logging(base_client):
    """Test API calls are logged to database."""
    # Log an API call
    base_client._log_api_call(
        endpoint='test/endpoint',
        response_status=200,
        response_size_kb=1.5,
        duration_ms=150,
        error_message=None
    )
    
    # Query database using the client's session
    logs = base_client.session.query(APICallLog).all()
    assert len(logs) >= 1  # At least one log (might have logs from other tests)
    # Find our log
    test_logs = [log for log in logs if log.endpoint == "test/endpoint"]
    assert len(test_logs) == 1
    assert test_logs[0].api_name == "TestAPI"
    assert test_logs[0].endpoint == "test/endpoint"
    assert test_logs[0].status_code == 200


def test_expired_cache_returns_none(odds_client):
    """Test that expired cache returns None."""
    # Store old data (25 hours ago)
    old_time = datetime.now() - timedelta(hours=25)
    vegas_line = VegasLine(
        week=1,
        game_id='old_game',
        home_team='Team A',
        away_team='Team B',
        home_spread=-3.5,
        away_spread=3.5,
        total=45.5,
        home_itt=24.5,
        away_itt=21.0,
        fetched_at=old_time
    )
    odds_client.db_session.add(vegas_line)
    odds_client.db_session.commit()
    
    # Try to fetch with 24-hour TTL
    cached_data = odds_client._get_cached_odds(cache_ttl_hours=24)
    
    assert cached_data is None or len(cached_data) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

