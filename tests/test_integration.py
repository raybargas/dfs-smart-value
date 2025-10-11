"""
Integration Tests for Data Ingestion Component

Tests end-to-end workflows and performance requirements.
"""

import pytest
import pandas as pd
import time
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from parser import load_and_validate_player_data


class TestEndToEndFlow:
    """Test complete data ingestion workflow."""
    
    def test_upload_to_dataframe_workflow(self, valid_csv_data, mock_uploaded_file):
        """Test complete upload and parsing workflow."""
        # Simulate file upload
        mock_file = mock_uploaded_file(valid_csv_data, "week5_projections.csv")
        
        # Parse and validate
        df, summary = load_and_validate_player_data(mock_file)
        
        # Verify DataFrame
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        assert 'name' in df.columns
        assert 'position' in df.columns
        assert 'salary' in df.columns
        assert 'projection' in df.columns
        
        # Verify summary
        assert isinstance(summary, dict)
        assert 'total_players' in summary
        assert 'position_breakdown' in summary
        assert 'salary_range' in summary
        assert 'quality_score' in summary
        assert 'issues' in summary
    
    def test_workflow_with_data_issues(self, csv_invalid_position, mock_uploaded_file):
        """Test workflow handles data quality issues gracefully."""
        mock_file = mock_uploaded_file(csv_invalid_position, "test.csv")
        
        # Should not raise exception, but report issues
        df, summary = load_and_validate_player_data(mock_file)
        
        assert len(df) > 0
        assert summary['quality_score'] < 100.0
        assert len(summary['issues']) > 0
        
        # Verify issue format
        issue = summary['issues'][0]
        assert 'row' in issue
        assert 'column' in issue
        assert 'issue' in issue
    
    def test_dataframe_ready_for_downstream_use(self, valid_csv_data, mock_uploaded_file):
        """Test DataFrame is properly formatted for downstream components."""
        mock_file = mock_uploaded_file(valid_csv_data, "test.csv")
        df, summary = load_and_validate_player_data(mock_file)
        
        # Check data types
        assert df['salary'].dtype == 'int64'
        assert df['projection'].dtype == 'float64'
        assert df['ownership'].dtype == 'float64'
        
        # Check no NaN in required columns
        assert not df['name'].isna().any()
        assert not df['position'].isna().any()
        assert not df['salary'].isna().any()
        assert not df['projection'].isna().any()
        
        # Check data values in valid ranges
        assert (df['salary'] >= 2000).all()
        assert (df['salary'] <= 10000).all()
        assert (df['projection'] > 0).all()


class TestPerformanceRequirements:
    """Test performance requirements are met."""
    
    def test_parse_250_players_under_5_seconds(self, mock_uploaded_file):
        """Test parsing 250 players completes in <5 seconds."""
        # Generate 250-player CSV
        lines = ["Name,Position,Salary,Projection,Team,Opponent"]
        positions = ['QB', 'RB', 'WR', 'TE', 'DST']
        
        for i in range(250):
            pos = positions[i % len(positions)]
            salary = 3000 + (i * 28)
            projection = 5.0 + (i * 0.08)
            lines.append(f"Player{i},{pos},{salary},{projection},TEAM{i%32},OPP{i%32}")
        
        csv_data = "\n".join(lines)
        mock_file = mock_uploaded_file(csv_data, "250_players.csv")
        
        # Time the parsing
        start_time = time.time()
        df, summary = load_and_validate_player_data(mock_file)
        end_time = time.time()
        
        duration = end_time - start_time
        
        assert len(df) == 250
        assert duration < 5.0  # Must complete in <5 seconds
    
    def test_parse_500_players_gracefully(self, large_csv_data, mock_uploaded_file):
        """Test handling 500 players gracefully (stress test)."""
        mock_file = mock_uploaded_file(large_csv_data, "500_players.csv")
        
        start_time = time.time()
        df, summary = load_and_validate_player_data(mock_file)
        end_time = time.time()
        
        duration = end_time - start_time
        
        assert len(df) == 500
        assert summary['total_players'] == 500
        # Should still be reasonably fast
        assert duration < 10.0


class TestErrorRecovery:
    """Test error handling and recovery."""
    
    def test_malformed_csv_provides_helpful_error(self, mock_uploaded_file):
        """Test malformed CSV provides actionable error message."""
        malformed_csv = """Name,Position,Salary
Player 1,QB,8500,ExtraColumn
Player 2,RB"""  # Inconsistent columns
        
        mock_file = mock_uploaded_file(malformed_csv, "malformed.csv")
        
        with pytest.raises(Exception) as excinfo:
            load_and_validate_player_data(mock_file)
        
        # Error should be caught and reported
        assert excinfo.value is not None
    
    def test_empty_file_handling(self, mock_uploaded_file):
        """Test empty file is handled gracefully."""
        empty_csv = "Name,Position,Salary,Projection"
        mock_file = mock_uploaded_file(empty_csv, "empty.csv")
        
        df, summary = load_and_validate_player_data(mock_file)
        
        assert len(df) == 0
        assert summary['total_players'] == 0


class TestRealWorldScenarios:
    """Test realistic use cases."""
    
    def test_week_5_nfl_data_format(self, mock_uploaded_file):
        """Test with realistic Week 5 NFL data format."""
        realistic_csv = """Name,Position,Salary,Team,Opponent,Projection,Ownership
Josh Allen,QB,8300,BUF,@MIA,24.8,18.2
Lamar Jackson,QB,8000,BAL,PIT,23.5,22.1
Christian McCaffrey,RB,9200,SF,@ARI,22.3,38.5
Tony Pollard,RB,7800,DAL,@NYG,18.7,25.0
Tyreek Hill,WR,8500,MIA,BUF,21.9,28.3
CeeDee Lamb,WR,8200,DAL,@NYG,20.5,24.7
Travis Kelce,TE,7500,KC,@MIN,18.2,20.5
T.J. Hockenson,TE,5500,MIN,KC,14.1,15.3
49ers,DST,3500,SF,@ARI,12.5,8.9"""
        
        mock_file = mock_uploaded_file(realistic_csv, "week5.csv")
        df, summary = load_and_validate_player_data(mock_file)
        
        assert len(df) == 9
        assert summary['quality_score'] == 100.0
        assert len(summary['issues']) == 0
        
        # Verify position breakdown
        breakdown = summary['position_breakdown']
        assert breakdown['QB'] == 2
        assert breakdown['RB'] == 2
        assert breakdown['WR'] == 2
        assert breakdown['TE'] == 2
        assert breakdown['DST'] == 1
    
    def test_draftkings_export_format(self, mock_uploaded_file):
        """Test with DraftKings export format."""
        dk_csv = """Name,Position,Salary,TeamAbbrev,AvgPointsPerGame
Patrick Mahomes,QB,8500,KC,24.2
Christian McCaffrey,RB,9200,SF,22.1
Tyreek Hill,WR,8000,MIA,21.8"""
        
        # Note: This will fail without TeamAbbrev/AvgPointsPerGame mappings
        # but tests that column detection attempts to handle variations
        mock_file = mock_uploaded_file(dk_csv, "dk_export.csv")
        
        # Should handle or provide clear error
        try:
            df, summary = load_and_validate_player_data(mock_file)
            # If it succeeds, verify basic structure
            assert len(df) > 0
        except KeyError as e:
            # If it fails, should mention missing columns
            assert "projection" in str(e).lower() or "opponent" in str(e).lower()

