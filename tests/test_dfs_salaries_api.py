"""
Unit tests for DFS Salaries API Client.

Tests the MySportsFeeds DFS Salaries API client with mocked responses.
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.api.dfs_salaries_api import DFSSalariesAPIClient, fetch_salaries
from src.api.base_client import APIError, RateLimitError, TimeoutError


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_api_key():
    """Mock API key for testing."""
    return "test_api_key_12345"


@pytest.fixture
def mock_db_path(tmp_path):
    """Create temporary database path."""
    return str(tmp_path / "test_dfs.db")


@pytest.fixture
def client(mock_api_key, mock_db_path):
    """Create DFS Salaries API client with mocked database."""
    with patch('src.api.dfs_salaries_api.create_engine'), \
         patch('src.api.dfs_salaries_api.sessionmaker'):
        client = DFSSalariesAPIClient(api_key=mock_api_key, db_path=mock_db_path)
        yield client
        client.close()


@pytest.fixture
def mock_dfs_response():
    """Mock successful DFS API response."""
    return {
        "lastUpdatedOn": "2024-10-15T10:30:00.000Z",
        "dfsPlayers": [
            {
                "dfsSource": "DRAFTKINGS",
                "player": {
                    "id": 10001,
                    "firstName": "Patrick",
                    "lastName": "Mahomes",
                    "position": "QB",
                    "currentTeam": {"abbreviation": "KC"}
                },
                "salary": 8500,
                "fantasyPointsProjection": 24.5
            },
            {
                "dfsSource": "DRAFTKINGS",
                "player": {
                    "id": 10002,
                    "firstName": "Travis",
                    "lastName": "Kelce",
                    "position": "TE",
                    "currentTeam": {"abbreviation": "KC"}
                },
                "salary": 7200,
                "fantasyPointsProjection": 18.3
            },
            {
                "dfsSource": "FANDUEL",  # Different site, should be filtered
                "player": {
                    "id": 10003,
                    "firstName": "Tyreek",
                    "lastName": "Hill",
                    "position": "WR",
                    "currentTeam": {"abbreviation": "MIA"}
                },
                "salary": 9000,
                "fantasyPointsProjection": 22.1
            }
        ]
    }


@pytest.fixture
def mock_empty_response():
    """Mock empty DFS API response."""
    return {
        "lastUpdatedOn": "2024-10-15T10:30:00.000Z",
        "dfsPlayers": []
    }


# ============================================================================
# TEST CLIENT INITIALIZATION
# ============================================================================

def test_client_initialization(mock_api_key, mock_db_path):
    """Test DFS client initializes correctly."""
    with patch('src.api.dfs_salaries_api.create_engine'), \
         patch('src.api.dfs_salaries_api.sessionmaker'):
        client = DFSSalariesAPIClient(api_key=mock_api_key, db_path=mock_db_path)
        
        assert client.api_name == "mysportsfeeds_dfs"
        assert client.base_url == "https://api.mysportsfeeds.com/v2.1/pull/nfl"
        assert client.api_key == mock_api_key
        assert client.timeout == 15
        assert client.max_retries == 3
        
        client.close()


def test_supported_sites(client):
    """Test get_supported_sites returns correct list."""
    sites = client.get_supported_sites()
    
    assert 'draftkings' in sites
    assert 'fanduel' in sites
    assert 'fantasydraft' in sites
    assert 'yahoo' in sites
    assert len(sites) == 4


# ============================================================================
# TEST FETCH CURRENT WEEK SALARIES
# ============================================================================

def test_fetch_current_week_salaries_success(client, mock_dfs_response):
    """Test fetching current week salaries successfully."""
    with patch.object(client, '_make_request', return_value=mock_dfs_response):
        df = client.fetch_current_week_salaries(site='draftkings')
        
        # Check DataFrame structure
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2  # Only DraftKings players (FanDuel filtered out)
        assert list(df.columns) == [
            'player_id', 'player_name', 'position', 'team',
            'opponent', 'salary', 'projection'
        ]
        
        # Check data types
        assert df['salary'].dtype == int
        
        # Check first player (Mahomes)
        mahomes = df.iloc[0]
        assert mahomes['player_name'] == "Patrick Mahomes"
        assert mahomes['position'] == "QB"
        assert mahomes['team'] == "KC"
        assert mahomes['salary'] == 8500
        assert mahomes['projection'] == 24.5
        
        # Check second player (Kelce)
        kelce = df.iloc[1]
        assert kelce['player_name'] == "Travis Kelce"
        assert kelce['position'] == "TE"
        assert kelce['team'] == "KC"
        assert kelce['salary'] == 7200


def test_fetch_current_week_salaries_fanduel(client, mock_dfs_response):
    """Test fetching FanDuel salaries."""
    with patch.object(client, '_make_request', return_value=mock_dfs_response):
        df = client.fetch_current_week_salaries(site='fanduel')
        
        # Should only get FanDuel players
        assert len(df) == 1
        assert df.iloc[0]['player_name'] == "Tyreek Hill"
        assert df.iloc[0]['salary'] == 9000


def test_fetch_current_week_salaries_empty(client, mock_empty_response):
    """Test fetching when no players available."""
    with patch.object(client, '_make_request', return_value=mock_empty_response):
        df = client.fetch_current_week_salaries(site='draftkings')
        
        # Should return empty DataFrame with correct columns
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert list(df.columns) == [
            'player_id', 'player_name', 'position', 'team',
            'opponent', 'salary', 'projection'
        ]


def test_fetch_current_week_salaries_invalid_site(client):
    """Test fetching with invalid site raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported site"):
        client.fetch_current_week_salaries(site='invalid_site')


def test_fetch_current_week_salaries_caching(client, mock_dfs_response):
    """Test caching works for repeated requests."""
    with patch.object(client, '_make_request', return_value=mock_dfs_response) as mock_request:
        # First call - should hit API
        df1 = client.fetch_current_week_salaries(site='draftkings', use_cache=True)
        assert mock_request.call_count == 1
        
        # Second call - should use cache
        df2 = client.fetch_current_week_salaries(site='draftkings', use_cache=True)
        assert mock_request.call_count == 1  # Not called again
        
        # DataFrames should be identical
        pd.testing.assert_frame_equal(df1, df2)


def test_fetch_current_week_salaries_no_cache(client, mock_dfs_response):
    """Test disabling cache makes fresh API calls."""
    with patch.object(client, '_make_request', return_value=mock_dfs_response) as mock_request:
        # First call
        client.fetch_current_week_salaries(site='draftkings', use_cache=False)
        assert mock_request.call_count == 1
        
        # Second call - should hit API again
        client.fetch_current_week_salaries(site='draftkings', use_cache=False)
        assert mock_request.call_count == 2


# ============================================================================
# TEST FETCH HISTORICAL SALARIES
# ============================================================================

def test_fetch_historical_salaries_success(client, mock_dfs_response):
    """Test fetching historical salaries successfully."""
    with patch.object(client, '_make_request', return_value=mock_dfs_response):
        df = client.fetch_historical_salaries(
            season='2024-2025-regular',
            week=10,
            site='draftkings'
        )
        
        # Check DataFrame structure
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2  # DraftKings players only
        
        # Check data
        assert df.iloc[0]['player_name'] == "Patrick Mahomes"
        assert df.iloc[1]['player_name'] == "Travis Kelce"


def test_fetch_historical_salaries_invalid_week(client):
    """Test fetching with invalid week raises ValueError."""
    with pytest.raises(ValueError, match="Invalid week"):
        client.fetch_historical_salaries(week=0, site='draftkings')
    
    with pytest.raises(ValueError, match="Invalid week"):
        client.fetch_historical_salaries(week=19, site='draftkings')


def test_fetch_historical_salaries_invalid_site(client):
    """Test fetching historical with invalid site raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported site"):
        client.fetch_historical_salaries(week=10, site='invalid_site')


def test_fetch_historical_salaries_endpoint(client, mock_dfs_response):
    """Test correct endpoint is called for historical data."""
    with patch.object(client, '_make_request', return_value=mock_dfs_response) as mock_request:
        client.fetch_historical_salaries(
            season='2024-2025-regular',
            week=12,
            site='draftkings'
        )
        
        # Check endpoint
        mock_request.assert_called_once_with('2024-2025-regular/week/12/dfs.json')


# ============================================================================
# TEST ERROR HANDLING
# ============================================================================

def test_fetch_api_error_401(client):
    """Test 401 authentication error handling."""
    with patch.object(client, '_make_request', side_effect=APIError("Authentication failed (401)")):
        with pytest.raises(APIError, match="Authentication failed"):
            client.fetch_current_week_salaries(site='draftkings')


def test_fetch_api_error_403(client):
    """Test 403 subscription error handling."""
    with patch.object(client, '_make_request', side_effect=APIError("Access forbidden (403)")):
        with pytest.raises(APIError, match="Access forbidden"):
            client.fetch_current_week_salaries(site='draftkings')


def test_fetch_api_error_404(client):
    """Test 404 not found error handling."""
    with patch.object(client, '_make_request', side_effect=APIError("Not found (404)")):
        with pytest.raises(APIError, match="Not found"):
            client.fetch_current_week_salaries(site='draftkings')


def test_fetch_rate_limit_error(client):
    """Test rate limit error handling."""
    with patch.object(client, '_make_request', side_effect=RateLimitError("Rate limit exceeded")):
        with pytest.raises(RateLimitError):
            client.fetch_current_week_salaries(site='draftkings')


def test_fetch_timeout_error(client):
    """Test timeout error handling."""
    with patch.object(client, '_make_request', side_effect=TimeoutError("Request timed out")):
        with pytest.raises(TimeoutError):
            client.fetch_current_week_salaries(site='draftkings')


# ============================================================================
# TEST RESPONSE PARSING
# ============================================================================

def test_parse_dfs_response_empty_list(client):
    """Test parsing response with empty dfsPlayers list."""
    response = {"lastUpdatedOn": "2024-10-15T10:30:00.000Z", "dfsPlayers": []}
    df = client._parse_dfs_response(response, site='draftkings')
    
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0
    assert list(df.columns) == [
        'player_id', 'player_name', 'position', 'team',
        'opponent', 'salary', 'projection'
    ]


def test_parse_dfs_response_missing_fields(client):
    """Test parsing response with missing optional fields."""
    response = {
        "dfsPlayers": [
            {
                "dfsSource": "DRAFTKINGS",
                "player": {
                    "id": 10001,
                    "firstName": "Test",
                    "lastName": "Player",
                    "currentTeam": {"abbreviation": "KC"}
                    # Missing position
                },
                "salary": 5000
                # Missing fantasyPointsProjection
            }
        ]
    }
    
    df = client._parse_dfs_response(response, site='draftkings')
    
    assert len(df) == 1
    assert df.iloc[0]['position'] == ''  # Default empty string
    assert pd.isna(df.iloc[0]['projection'])  # None becomes NaN


def test_parse_dfs_response_multiple_sites(client, mock_dfs_response):
    """Test parsing filters by correct site."""
    # Parse for DraftKings
    df_dk = client._parse_dfs_response(mock_dfs_response, site='draftkings')
    assert len(df_dk) == 2  # Mahomes, Kelce
    
    # Parse for FanDuel
    df_fd = client._parse_dfs_response(mock_dfs_response, site='fanduel')
    assert len(df_fd) == 1  # Tyreek Hill
    
    # Parse for site with no players
    df_empty = client._parse_dfs_response(mock_dfs_response, site='yahoo')
    assert len(df_empty) == 0


# ============================================================================
# TEST CONVENIENCE FUNCTION
# ============================================================================

def test_fetch_salaries_current_week(mock_api_key, mock_db_path, mock_dfs_response):
    """Test convenience function for current week."""
    with patch('src.api.dfs_salaries_api.create_engine'), \
         patch('src.api.dfs_salaries_api.sessionmaker'), \
         patch('src.api.dfs_salaries_api.DFSSalariesAPIClient.fetch_current_week_salaries', return_value=pd.DataFrame()):
        
        df = fetch_salaries(api_key=mock_api_key, site='draftkings', db_path=mock_db_path)
        
        assert isinstance(df, pd.DataFrame)


def test_fetch_salaries_historical_week(mock_api_key, mock_db_path, mock_dfs_response):
    """Test convenience function for historical week."""
    with patch('src.api.dfs_salaries_api.create_engine'), \
         patch('src.api.dfs_salaries_api.sessionmaker'), \
         patch('src.api.dfs_salaries_api.DFSSalariesAPIClient.fetch_historical_salaries', return_value=pd.DataFrame()):
        
        df = fetch_salaries(
            api_key=mock_api_key,
            site='draftkings',
            week=10,
            season='2024-2025-regular',
            db_path=mock_db_path
        )
        
        assert isinstance(df, pd.DataFrame)


# ============================================================================
# TEST SUMMARY
# ============================================================================

def test_summary():
    """
    Test Coverage Summary:
    
    ✅ Client initialization
    ✅ Fetch current week salaries (success, empty, caching)
    ✅ Fetch historical salaries (success, validation)
    ✅ Error handling (401, 403, 404, 429, timeout)
    ✅ Response parsing (empty, missing fields, multiple sites)
    ✅ Input validation (invalid site, invalid week)
    ✅ Convenience function
    
    Total: 20+ tests
    Expected Coverage: 85%+
    """
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

