"""
Unit tests for HistoricalDataManager

Tests slate creation, player pool snapshot storage, and historical data retrieval.
"""

import pytest
import pandas as pd
import sys
import os
import tempfile
from datetime import date
from pathlib import Path

# Add the src directory to the path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from historical_data_manager import HistoricalDataManager, create_slate_from_dfs_data
from database_models import Base, Slate, HistoricalPlayerPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    db_path = temp_file.name
    temp_file.close()
    
    # Create tables
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    
    yield db_path
    
    # Cleanup
    os.unlink(db_path)


@pytest.fixture
def manager(temp_db):
    """Create HistoricalDataManager instance."""
    mgr = HistoricalDataManager(db_path=temp_db)
    yield mgr
    mgr.close()


@pytest.fixture
def sample_player_data():
    """Create sample player DataFrame."""
    return pd.DataFrame({
        'player_id': ['mahomes_kc', 'kelce_kc', 'allen_buf'],
        'player_name': ['Patrick Mahomes', 'Travis Kelce', 'Josh Allen'],
        'position': ['QB', 'TE', 'QB'],
        'team': ['KC', 'KC', 'BUF'],
        'opponent': ['BUF', 'BUF', 'KC'],
        'salary': [8500, 7200, 8000],
        'projection': [24.5, 14.2, 22.8],
        'ceiling': [35.0, 22.0, 33.0],
        'ownership': [25.0, 18.0, 22.0],
        'smart_value': [0.85, 0.72, 0.81]
    })


class TestSlateCreation:
    """Test suite for slate creation."""
    
    def test_create_slate_success(self, manager):
        """Test successful slate creation."""
        slate_id = manager.create_slate(
            week=6,
            season=2024,
            site='DraftKings',
            contest_type='Classic',
            games=['KC@BUF', 'SF@LAR']
        )
        
        assert slate_id == '2024-W6-DK-CLASSIC'
        
        # Verify in database
        slate = manager.session.query(Slate).filter(
            Slate.slate_id == slate_id
        ).first()
        
        assert slate is not None
        assert slate.week == 6
        assert slate.season == 2024
        assert slate.site == 'DraftKings'
        assert slate.contest_type == 'Classic'
    
    def test_create_slate_duplicate_raises_error(self, manager):
        """Test that creating duplicate slate raises error."""
        manager.create_slate(
            week=6,
            season=2024,
            site='DraftKings',
            contest_type='Classic',
            games=['KC@BUF']
        )
        
        with pytest.raises(ValueError, match="already exists"):
            manager.create_slate(
                week=6,
                season=2024,
                site='DraftKings',
                contest_type='Classic',
                games=['KC@BUF']
            )
    
    def test_create_slate_invalid_week(self, manager):
        """Test that invalid week raises error."""
        with pytest.raises(ValueError, match="Invalid week"):
            manager.create_slate(
                week=19,
                season=2024,
                site='DraftKings',
                contest_type='Classic',
                games=['KC@BUF']
            )
    
    def test_create_slate_invalid_season(self, manager):
        """Test that invalid season raises error."""
        with pytest.raises(ValueError, match="Invalid season"):
            manager.create_slate(
                week=6,
                season=2050,
                site='DraftKings',
                contest_type='Classic',
                games=['KC@BUF']
            )
    
    def test_generate_slate_id_formats(self, manager):
        """Test slate ID generation for different sites."""
        test_cases = [
            ('DraftKings', 'Classic', '2024-W6-DK-CLASSIC'),
            ('FanDuel', 'Classic', '2024-W6-FD-CLASSIC'),
            ('Yahoo', 'Showdown', '2024-W6-YH-SHOWDOWN'),
        ]
        
        for site, contest_type, expected_id in test_cases:
            slate_id = manager._generate_slate_id(6, 2024, site, contest_type)
            assert slate_id == expected_id


class TestPlayerPoolSnapshot:
    """Test suite for player pool snapshot storage."""
    
    def test_store_player_pool_success(self, manager, sample_player_data):
        """Test successful player pool storage."""
        # Create slate first
        slate_id = manager.create_slate(
            week=6,
            season=2024,
            site='DraftKings',
            contest_type='Classic',
            games=['KC@BUF']
        )
        
        # Store player pool
        count = manager.store_player_pool_snapshot(
            slate_id=slate_id,
            player_data=sample_player_data,
            smart_value_profile='GPP_Balanced_v3.0',
            projection_source='manual',
            ownership_source='fantasylabs'
        )
        
        assert count == 3
        
        # Verify in database
        players = manager.session.query(HistoricalPlayerPool).filter(
            HistoricalPlayerPool.slate_id == slate_id
        ).all()
        
        assert len(players) == 3
        
        # Verify player data (order not guaranteed)
        player_names = [p.player_name for p in players]
        assert 'Patrick Mahomes' in player_names
        assert 'Travis Kelce' in player_names
        assert 'Josh Allen' in player_names
        
        # Check one player's attributes
        mahomes = [p for p in players if p.player_name == 'Patrick Mahomes'][0]
        assert mahomes.smart_value_profile == 'GPP_Balanced_v3.0'
        assert mahomes.projection_source == 'manual'
    
    def test_store_player_pool_slate_not_found(self, manager, sample_player_data):
        """Test that storing to non-existent slate raises error."""
        with pytest.raises(ValueError, match="Slate .* not found"):
            manager.store_player_pool_snapshot(
                slate_id='2024-W99-DK-CLASSIC',
                player_data=sample_player_data
            )
    
    def test_store_player_pool_missing_columns(self, manager):
        """Test that missing required columns raises error."""
        # Create slate
        slate_id = manager.create_slate(
            week=6,
            season=2024,
            site='DraftKings',
            contest_type='Classic',
            games=['KC@BUF']
        )
        
        # Invalid data (missing required columns)
        invalid_data = pd.DataFrame({
            'player_name': ['Patrick Mahomes'],
            'position': ['QB']
            # Missing: team, salary, projection
        })
        
        with pytest.raises(ValueError, match="Missing required columns"):
            manager.store_player_pool_snapshot(
                slate_id=slate_id,
                player_data=invalid_data
            )


class TestActualPointsUpdate:
    """Test suite for updating actual fantasy points."""
    
    def test_update_actual_points_success(self, manager, sample_player_data):
        """Test successful actual points update."""
        # Setup: Create slate and store players
        slate_id = manager.create_slate(
            week=6,
            season=2024,
            site='DraftKings',
            contest_type='Classic',
            games=['KC@BUF']
        )
        manager.store_player_pool_snapshot(slate_id, sample_player_data)
        
        # Update actuals
        actuals = {
            'Patrick Mahomes': 28.4,
            'Travis Kelce': 14.2,
            'Josh Allen': 31.6
        }
        
        count = manager.update_actual_points(slate_id, actuals)
        assert count == 3
        
        # Verify in database
        players = manager.session.query(HistoricalPlayerPool).filter(
            HistoricalPlayerPool.slate_id == slate_id
        ).all()
        
        # Verify actual points (order not guaranteed)
        player_actuals = {p.player_name: p.actual_points for p in players}
        assert player_actuals['Patrick Mahomes'] == 28.4
        assert player_actuals['Travis Kelce'] == 14.2
        assert player_actuals['Josh Allen'] == 31.6
    
    def test_update_actual_points_partial_match(self, manager, sample_player_data):
        """Test updating actuals with partial matches."""
        # Setup
        slate_id = manager.create_slate(
            week=6,
            season=2024,
            site='DraftKings',
            contest_type='Classic',
            games=['KC@BUF']
        )
        manager.store_player_pool_snapshot(slate_id, sample_player_data)
        
        # Update only 2 out of 3 players
        actuals = {
            'Patrick Mahomes': 28.4,
            'Josh Allen': 31.6
            # Travis Kelce not included
        }
        
        count = manager.update_actual_points(slate_id, actuals)
        assert count == 2
    
    def test_update_actual_points_slate_not_found(self, manager):
        """Test that updating non-existent slate raises error."""
        actuals = {'Patrick Mahomes': 28.4}
        
        with pytest.raises(ValueError, match="No players found"):
            manager.update_actual_points('2024-W99-DK-CLASSIC', actuals)


class TestHistoricalSnapshotRetrieval:
    """Test suite for loading historical snapshots."""
    
    def test_load_historical_snapshot_success(self, manager, sample_player_data):
        """Test successful snapshot loading."""
        # Setup
        slate_id = manager.create_slate(
            week=6,
            season=2024,
            site='DraftKings',
            contest_type='Classic',
            games=['KC@BUF']
        )
        manager.store_player_pool_snapshot(slate_id, sample_player_data)
        
        # Load snapshot
        df = manager.load_historical_snapshot(slate_id)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert 'player_name' in df.columns
        assert 'salary' in df.columns
        assert 'projection' in df.columns
        assert 'actual_points' in df.columns
        
        # Verify player names (order not guaranteed)
        assert 'Patrick Mahomes' in df['player_name'].values
        assert 'Travis Kelce' in df['player_name'].values
        assert 'Josh Allen' in df['player_name'].values
    
    def test_load_historical_snapshot_with_actuals(self, manager, sample_player_data):
        """Test loading snapshot with actual points included."""
        # Setup
        slate_id = manager.create_slate(
            week=6,
            season=2024,
            site='DraftKings',
            contest_type='Classic',
            games=['KC@BUF']
        )
        manager.store_player_pool_snapshot(slate_id, sample_player_data)
        
        # Update actuals
        actuals = {'Patrick Mahomes': 28.4, 'Travis Kelce': 14.2, 'Josh Allen': 31.6}
        manager.update_actual_points(slate_id, actuals)
        
        # Load with actuals
        df = manager.load_historical_snapshot(slate_id, include_actuals=True)
        
        # Verify actual points (order not guaranteed)
        mahomes_row = df[df['player_name'] == 'Patrick Mahomes'].iloc[0]
        kelce_row = df[df['player_name'] == 'Travis Kelce'].iloc[0]
        allen_row = df[df['player_name'] == 'Josh Allen'].iloc[0]
        
        assert mahomes_row['actual_points'] == 28.4
        assert kelce_row['actual_points'] == 14.2
        assert allen_row['actual_points'] == 31.6
    
    def test_load_historical_snapshot_without_actuals(self, manager, sample_player_data):
        """Test loading snapshot without actual points."""
        # Setup
        slate_id = manager.create_slate(
            week=6,
            season=2024,
            site='DraftKings',
            contest_type='Classic',
            games=['KC@BUF']
        )
        manager.store_player_pool_snapshot(slate_id, sample_player_data)
        
        # Load without actuals
        df = manager.load_historical_snapshot(slate_id, include_actuals=False)
        
        assert 'actual_points' not in df.columns
    
    def test_load_historical_snapshot_not_found(self, manager):
        """Test that loading non-existent slate raises error."""
        with pytest.raises(ValueError, match="No data found"):
            manager.load_historical_snapshot('2024-W99-DK-CLASSIC')


class TestQueryAvailableWeeks:
    """Test suite for querying available weeks."""
    
    def test_get_available_weeks_success(self, manager, sample_player_data):
        """Test getting available weeks."""
        # Create multiple slates
        for week in [6, 7, 8]:
            slate_id = manager.create_slate(
                week=week,
                season=2024,
                site='DraftKings',
                contest_type='Classic',
                games=['KC@BUF']
            )
            manager.store_player_pool_snapshot(slate_id, sample_player_data)
        
        # Query available weeks
        weeks = manager.get_available_weeks(season=2024)
        
        assert len(weeks) == 3
        assert weeks[0]['week'] == 6
        assert weeks[1]['week'] == 7
        assert weeks[2]['week'] == 8
        assert weeks[0]['player_count'] == 3
    
    def test_get_available_weeks_filtered_by_site(self, manager, sample_player_data):
        """Test getting available weeks filtered by site."""
        # Create slates for different sites
        slate_dk = manager.create_slate(6, 2024, 'DraftKings', 'Classic', ['KC@BUF'])
        slate_fd = manager.create_slate(6, 2024, 'FanDuel', 'Classic', ['KC@BUF'])
        
        manager.store_player_pool_snapshot(slate_dk, sample_player_data)
        manager.store_player_pool_snapshot(slate_fd, sample_player_data)
        
        # Query DraftKings only
        weeks = manager.get_available_weeks(season=2024, site='DraftKings')
        
        assert len(weeks) == 1
        assert weeks[0]['site'] == 'DraftKings'
    
    def test_get_available_weeks_empty(self, manager):
        """Test getting available weeks when none exist."""
        weeks = manager.get_available_weeks(season=2024)
        assert len(weeks) == 0


class TestSlateMetadata:
    """Test suite for slate metadata."""
    
    def test_get_slate_metadata_success(self, manager, sample_player_data):
        """Test getting slate metadata."""
        # Create slate
        slate_id = manager.create_slate(
            week=6,
            season=2024,
            site='DraftKings',
            contest_type='Classic',
            games=['KC@BUF', 'SF@LAR']
        )
        manager.store_player_pool_snapshot(slate_id, sample_player_data)
        
        # Get metadata
        metadata = manager.get_slate_metadata(slate_id)
        
        assert metadata is not None
        assert metadata['week'] == 6
        assert metadata['season'] == 2024
        assert metadata['site'] == 'DraftKings'
        assert metadata['contest_type'] == 'Classic'
        assert metadata['player_count'] == 3
        assert len(metadata['games']) == 2
    
    def test_get_slate_metadata_not_found(self, manager):
        """Test getting metadata for non-existent slate."""
        metadata = manager.get_slate_metadata('2024-W99-DK-CLASSIC')
        assert metadata is None


class TestSlateDelete:
    """Test suite for slate deletion."""
    
    def test_delete_slate_success(self, manager, sample_player_data):
        """Test successful slate deletion."""
        # Create slate
        slate_id = manager.create_slate(
            week=6,
            season=2024,
            site='DraftKings',
            contest_type='Classic',
            games=['KC@BUF']
        )
        manager.store_player_pool_snapshot(slate_id, sample_player_data)
        
        # Delete slate
        result = manager.delete_slate(slate_id)
        assert result is True
        
        # Verify deletion
        slate = manager.session.query(Slate).filter(
            Slate.slate_id == slate_id
        ).first()
        assert slate is None
        
        # Verify players deleted too
        players = manager.session.query(HistoricalPlayerPool).filter(
            HistoricalPlayerPool.slate_id == slate_id
        ).all()
        assert len(players) == 0
    
    def test_delete_slate_not_found(self, manager):
        """Test deleting non-existent slate."""
        result = manager.delete_slate('2024-W99-DK-CLASSIC')
        assert result is False


class TestConvenienceFunctions:
    """Test suite for convenience functions."""
    
    def test_create_slate_from_dfs_data(self, temp_db):
        """Test convenience function for creating slate from DFS data."""
        # Create sample DFS data
        dfs_data = pd.DataFrame({
            'player_name': ['Patrick Mahomes', 'Travis Kelce'],
            'position': ['QB', 'TE'],
            'team': ['KC', 'KC'],
            'opponent': ['BUF', 'BUF'],
            'salary': [8500, 7200],
            'projection': [24.5, 14.2],
            'ceiling': [35.0, 22.0],
            'ownership': [25.0, 18.0]
        })
        
        # Create slate using convenience function
        slate_id = create_slate_from_dfs_data(
            dfs_salaries_df=dfs_data,
            week=6,
            season=2024,
            site='DraftKings',
            contest_type='Classic',
            db_path=temp_db
        )
        
        assert slate_id == '2024-W6-DK-CLASSIC'
        
        # Verify slate was created
        manager = HistoricalDataManager(db_path=temp_db)
        try:
            metadata = manager.get_slate_metadata(slate_id)
            assert metadata is not None
            assert metadata['player_count'] == 2
        finally:
            manager.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

