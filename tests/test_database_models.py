"""
Test Suite for Database Models (Phase 2C - Narrative Intelligence)

Tests for SQLAlchemy ORM models:
- VegasLine model and ITT calculations
- InjuryReport model and severity scoring
- NarrativeFlag model and color coding
- APICallLog model and status tracking
- Database migrations and schema
- CRUD operations and queries
- Performance benchmarks
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from database_models import (
    Base, VegasLine, InjuryReport, NarrativeFlag, APICallLog,
    create_session, get_vegas_lines_by_week, get_itt_for_team,
    get_injury_reports_by_week, get_active_injuries_by_week,
    get_flags_for_player, get_recent_api_calls
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def test_db():
    """Create a test database in memory."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestVegasLineModel:
    """Tests for VegasLine model."""
    
    def test_create_vegas_line(self, test_db):
        """Test creating a VegasLine entry."""
        line = VegasLine(
            week=5,
            game_id="KC_LV",
            home_team="LV",
            away_team="KC",
            home_spread=7.0,
            away_spread=-7.0,
            total=52.5,
            home_itt=22.75,  # (52.5/2) - (7/2) = 22.75
            away_itt=29.75   # (52.5/2) + (7/2) = 29.75
        )
        
        test_db.add(line)
        test_db.commit()
        
        # Verify saved correctly
        saved_line = test_db.query(VegasLine).filter_by(game_id="KC_LV").first()
        assert saved_line is not None
        assert saved_line.home_team == "LV"
        assert saved_line.away_team == "KC"
        assert saved_line.total == 52.5
        assert saved_line.home_itt == 22.75
        assert saved_line.away_itt == 29.75
    
    def test_get_itt_method(self, test_db):
        """Test get_itt() method for team lookup."""
        line = VegasLine(
            week=5,
            game_id="DAL_PHI",
            home_team="PHI",
            away_team="DAL",
            home_spread=-3.0,
            total=48.5,
            home_itt=25.75,  # (48.5/2) + (3/2)
            away_itt=22.75   # (48.5/2) - (3/2)
        )
        
        test_db.add(line)
        test_db.commit()
        
        # Test get_itt for each team
        assert line.get_itt("PHI") == 25.75
        assert line.get_itt("DAL") == 22.75
        assert line.get_itt("GB") is None  # Team not in game
    
    def test_unique_constraint(self, test_db):
        """Test unique constraint on (week, game_id)."""
        line1 = VegasLine(week=5, game_id="KC_LV", home_team="LV", away_team="KC", total=52.5)
        test_db.add(line1)
        test_db.commit()
        
        # Try to insert duplicate
        line2 = VegasLine(week=5, game_id="KC_LV", home_team="LV", away_team="KC", total=53.0)
        test_db.add(line2)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            test_db.commit()
    
    def test_check_constraints(self, test_db):
        """Test check constraints on total and ITT."""
        # Invalid total (negative)
        line = VegasLine(week=5, game_id="TEST", home_team="A", away_team="B", total=-10.0)
        test_db.add(line)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            test_db.commit()


class TestInjuryReportModel:
    """Tests for InjuryReport model."""
    
    def test_create_injury_report(self, test_db):
        """Test creating an InjuryReport entry."""
        injury = InjuryReport(
            week=5,
            player_name="Christian McCaffrey",
            team="SF",
            position="RB",
            injury_status="Q",
            practice_status="Limited",
            body_part="Hamstring",
            description="Limited in practice due to hamstring"
        )
        
        test_db.add(injury)
        test_db.commit()
        
        # Verify saved correctly
        saved = test_db.query(InjuryReport).filter_by(player_name="Christian McCaffrey").first()
        assert saved is not None
        assert saved.injury_status == "Q"
        assert saved.practice_status == "Limited"
        assert saved.body_part == "Hamstring"
    
    def test_is_active_injury_property(self, test_db):
        """Test is_active_injury property."""
        q_injury = InjuryReport(week=5, player_name="Player1", team="A", injury_status="Q")
        d_injury = InjuryReport(week=5, player_name="Player2", team="B", injury_status="D")
        o_injury = InjuryReport(week=5, player_name="Player3", team="C", injury_status="O")
        ir_injury = InjuryReport(week=5, player_name="Player4", team="D", injury_status="IR")
        no_injury = InjuryReport(week=5, player_name="Player5", team="E", injury_status=None)
        
        assert q_injury.is_active_injury is True
        assert d_injury.is_active_injury is True
        assert o_injury.is_active_injury is True
        assert ir_injury.is_active_injury is False
        assert no_injury.is_active_injury is False
    
    def test_severity_score_property(self, test_db):
        """Test severity_score property."""
        q_injury = InjuryReport(week=5, player_name="P1", team="A", injury_status="Q")
        d_injury = InjuryReport(week=5, player_name="P2", team="B", injury_status="D")
        o_injury = InjuryReport(week=5, player_name="P3", team="C", injury_status="O")
        ir_injury = InjuryReport(week=5, player_name="P4", team="D", injury_status="IR")
        
        assert q_injury.severity_score == 2
        assert d_injury.severity_score == 3
        assert o_injury.severity_score == 4
        assert ir_injury.severity_score == 5
        assert ir_injury.severity_score > o_injury.severity_score > d_injury.severity_score > q_injury.severity_score
    
    def test_unique_constraint(self, test_db):
        """Test unique constraint on (week, player_name, team)."""
        injury1 = InjuryReport(week=5, player_name="Patrick Mahomes", team="KC", injury_status="Q")
        test_db.add(injury1)
        test_db.commit()
        
        # Try to insert duplicate
        injury2 = InjuryReport(week=5, player_name="Patrick Mahomes", team="KC", injury_status="D")
        test_db.add(injury2)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            test_db.commit()


class TestNarrativeFlagModel:
    """Tests for NarrativeFlag model."""
    
    def test_create_narrative_flag(self, test_db):
        """Test creating a NarrativeFlag entry."""
        flag = NarrativeFlag(
            week=5,
            player_name="Davante Adams",
            team="LV",
            position="WR",
            flag_type="warning",
            flag_category="salary_ceiling",
            message="Salary/Ceiling ratio: 4.2 (exceeds 3.5 threshold) - Overpriced for upside",
            severity="red"
        )
        
        test_db.add(flag)
        test_db.commit()
        
        # Verify saved correctly
        saved = test_db.query(NarrativeFlag).filter_by(player_name="Davante Adams").first()
        assert saved is not None
        assert saved.flag_category == "salary_ceiling"
        assert saved.severity == "red"
        assert "4.2" in saved.message
    
    def test_color_code_property(self, test_db):
        """Test color_code property."""
        green_flag = NarrativeFlag(
            week=5, player_name="P1", team="A", position="QB",
            flag_type="optimal", flag_category="itt", message="Good ITT", severity="green"
        )
        yellow_flag = NarrativeFlag(
            week=5, player_name="P2", team="B", position="RB",
            flag_type="caution", flag_category="committee", message="Committee", severity="yellow"
        )
        red_flag = NarrativeFlag(
            week=5, player_name="P3", team="C", position="WR",
            flag_type="warning", flag_category="itt", message="Low ITT", severity="red"
        )
        
        assert green_flag.color_code == "#1a472a"
        assert yellow_flag.color_code == "#4a4419"
        assert red_flag.color_code == "#4a1a1a"
    
    def test_check_constraints(self, test_db):
        """Test check constraints on flag fields."""
        # Invalid severity
        flag = NarrativeFlag(
            week=5, player_name="P1", team="A", position="QB",
            flag_type="warning", flag_category="itt", message="Test", severity="blue"
        )
        test_db.add(flag)
        
        with pytest.raises(Exception):  # Should raise IntegrityError
            test_db.commit()


class TestAPICallLogModel:
    """Tests for APICallLog model."""
    
    def test_create_api_call_log(self, test_db):
        """Test creating an APICallLog entry."""
        log = APICallLog(
            api_name="the_odds_api",
            endpoint="https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds",
            status_code=200,
            response_time_ms=1250
        )
        
        test_db.add(log)
        test_db.commit()
        
        # Verify saved correctly
        saved = test_db.query(APICallLog).filter_by(api_name="the_odds_api").first()
        assert saved is not None
        assert saved.status_code == 200
        assert saved.response_time_ms == 1250
    
    def test_is_success_property(self, test_db):
        """Test is_success property."""
        success_200 = APICallLog(api_name="the_odds_api", endpoint="/test", status_code=200)
        success_201 = APICallLog(api_name="the_odds_api", endpoint="/test", status_code=201)
        client_error = APICallLog(api_name="the_odds_api", endpoint="/test", status_code=404)
        server_error = APICallLog(api_name="the_odds_api", endpoint="/test", status_code=500)
        
        assert success_200.is_success is True
        assert success_201.is_success is True
        assert client_error.is_success is False
        assert server_error.is_success is False
    
    def test_is_rate_limited_property(self, test_db):
        """Test is_rate_limited property."""
        success = APICallLog(api_name="the_odds_api", endpoint="/test", status_code=200)
        rate_limited = APICallLog(api_name="the_odds_api", endpoint="/test", status_code=429)
        
        assert success.is_rate_limited is False
        assert rate_limited.is_rate_limited is True


class TestHelperFunctions:
    """Tests for helper query functions."""
    
    def test_get_vegas_lines_by_week(self, test_db):
        """Test get_vegas_lines_by_week function."""
        # Add lines for multiple weeks
        line1 = VegasLine(week=5, game_id="G1", home_team="A", away_team="B", total=50.0)
        line2 = VegasLine(week=5, game_id="G2", home_team="C", away_team="D", total=45.0)
        line3 = VegasLine(week=6, game_id="G3", home_team="E", away_team="F", total=48.0)
        
        test_db.add_all([line1, line2, line3])
        test_db.commit()
        
        # Query week 5
        week5_lines = get_vegas_lines_by_week(test_db, 5)
        assert len(week5_lines) == 2
        assert all(line.week == 5 for line in week5_lines)
        
        # Query week 6
        week6_lines = get_vegas_lines_by_week(test_db, 6)
        assert len(week6_lines) == 1
        assert week6_lines[0].week == 6
    
    def test_get_itt_for_team(self, test_db):
        """Test get_itt_for_team function."""
        line = VegasLine(
            week=5, game_id="KC_LV", home_team="LV", away_team="KC",
            home_itt=22.75, away_itt=29.75
        )
        test_db.add(line)
        test_db.commit()
        
        # Query ITT for teams
        kc_itt = get_itt_for_team(test_db, "KC", 5)
        lv_itt = get_itt_for_team(test_db, "LV", 5)
        sf_itt = get_itt_for_team(test_db, "SF", 5)
        
        assert kc_itt == 29.75
        assert lv_itt == 22.75
        assert sf_itt is None
    
    def test_get_active_injuries_by_week(self, test_db):
        """Test get_active_injuries_by_week function."""
        # Add injuries with different statuses
        q_injury = InjuryReport(week=5, player_name="P1", team="A", injury_status="Q")
        d_injury = InjuryReport(week=5, player_name="P2", team="B", injury_status="D")
        o_injury = InjuryReport(week=5, player_name="P3", team="C", injury_status="O")
        ir_injury = InjuryReport(week=5, player_name="P4", team="D", injury_status="IR")
        
        test_db.add_all([q_injury, d_injury, o_injury, ir_injury])
        test_db.commit()
        
        # Query active injuries (Q, D, O only)
        active = get_active_injuries_by_week(test_db, 5)
        assert len(active) == 3
        assert all(inj.injury_status in ['Q', 'D', 'O'] for inj in active)
    
    def test_get_flags_for_player(self, test_db):
        """Test get_flags_for_player function."""
        # Add multiple flags for a player
        flag1 = NarrativeFlag(
            week=5, player_name="Saquon Barkley", team="PHI", position="RB",
            flag_type="warning", flag_category="itt", message="Low ITT", severity="yellow"
        )
        flag2 = NarrativeFlag(
            week=5, player_name="Saquon Barkley", team="PHI", position="RB",
            flag_type="warning", flag_category="salary_ceiling", message="Overpriced", severity="red"
        )
        flag3 = NarrativeFlag(
            week=5, player_name="Other Player", team="SF", position="WR",
            flag_type="optimal", flag_category="itt", message="Good ITT", severity="green"
        )
        
        test_db.add_all([flag1, flag2, flag3])
        test_db.commit()
        
        # Query flags for Saquon
        saquon_flags = get_flags_for_player(test_db, "Saquon Barkley", "PHI", 5)
        assert len(saquon_flags) == 2
        assert all(flag.player_name == "Saquon Barkley" for flag in saquon_flags)
    
    def test_get_recent_api_calls(self, test_db):
        """Test get_recent_api_calls function."""
        now = datetime.utcnow()
        
        # Add API calls at different times
        recent_call = APICallLog(
            api_name="the_odds_api", endpoint="/test",
            status_code=200, called_at=now
        )
        old_call = APICallLog(
            api_name="the_odds_api", endpoint="/test",
            status_code=200, called_at=now - timedelta(hours=48)
        )
        
        test_db.add_all([recent_call, old_call])
        test_db.commit()
        
        # Query calls in last 24 hours
        recent_calls = get_recent_api_calls(test_db, "the_odds_api", hours=24)
        assert len(recent_calls) == 1
        assert recent_calls[0].called_at >= now - timedelta(hours=24)


class TestMigrationIntegrity:
    """Tests for migration and schema integrity."""
    
    def test_migration_creates_all_tables(self):
        """Test that migration 002 created all expected tables."""
        db_path = Path(__file__).parent.parent / "dfs_optimizer.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for Phase 2C tables
        expected_tables = ['vegas_lines', 'injury_reports', 'narrative_flags', 'api_call_log']
        
        for table in expected_tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            result = cursor.fetchone()
            assert result is not None, f"Table {table} not found in database"
        
        conn.close()
    
    def test_indexes_created(self):
        """Test that all indexes were created."""
        db_path = Path(__file__).parent.parent / "dfs_optimizer.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for key indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indexes = cursor.fetchall()
        
        # Should have indexes on vegas_lines, injury_reports, narrative_flags, api_call_log
        index_names = [idx[0] for idx in indexes]
        assert any('vegas' in name for name in index_names)
        assert any('injury' in name for name in index_names)
        assert any('flags' in name for name in index_names)
        assert any('api' in name for name in index_names)
        
        conn.close()


class TestPerformance:
    """Performance benchmark tests."""
    
    def test_bulk_insert_performance(self, test_db):
        """Test bulk insert performance (100 records)."""
        import time
        
        # Create 100 vegas_lines entries
        lines = [
            VegasLine(
                week=5, game_id=f"G{i}", home_team=f"H{i}", away_team=f"A{i}",
                total=50.0, home_itt=25.0, away_itt=25.0
            )
            for i in range(100)
        ]
        
        start = time.time()
        test_db.add_all(lines)
        test_db.commit()
        elapsed = time.time() - start
        
        # Should complete in < 1 second
        assert elapsed < 1.0, f"Bulk insert took {elapsed:.2f}s (expected <1s)"
    
    def test_query_performance(self, test_db):
        """Test query performance with indexes."""
        import time
        
        # Add 100 records
        lines = [
            VegasLine(
                week=5, game_id=f"G{i}", home_team=f"H{i}", away_team=f"A{i}",
                total=50.0, home_itt=25.0, away_itt=25.0
            )
            for i in range(100)
        ]
        test_db.add_all(lines)
        test_db.commit()
        
        # Query by week (should use index)
        start = time.time()
        results = test_db.query(VegasLine).filter(VegasLine.week == 5).all()
        elapsed = time.time() - start
        
        assert len(results) == 100
        # Should complete in < 100ms
        assert elapsed < 0.1, f"Query took {elapsed*1000:.0f}ms (expected <100ms)"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

