"""
Pytest Configuration and Shared Fixtures

This module provides common test fixtures used across the test suite.
"""

import pytest
import pandas as pd
from io import StringIO, BytesIO
from typing import Any


@pytest.fixture
def valid_csv_data() -> str:
    """Return valid CSV data for testing."""
    return """Name,Position,Salary,Team,Opponent,Projection,Ownership
Patrick Mahomes,QB,8500,KC,LV,24.2,28.5
Christian McCaffrey,RB,9200,SF,@ARI,22.1,32.0
Tyreek Hill,WR,8000,MIA,@BUF,21.8,22.3
Travis Kelce,TE,7500,KC,LV,18.5,25.0
49ers,DST,3500,SF,@ARI,12.0,8.5"""


@pytest.fixture
def valid_csv_with_variations() -> str:
    """Return CSV with column name variations."""
    return """Player Name,Pos,Cost,Proj,Team,Opp,Own%
Patrick Mahomes,QB,8500,24.2,KC,LV,28.5
Christian McCaffrey,RB,9200,22.1,SF,@ARI,32.0"""


@pytest.fixture
def csv_missing_required_column() -> str:
    """Return CSV missing a required column (projection)."""
    return """Name,Position,Salary,Team,Opponent
Patrick Mahomes,QB,8500,KC,LV
Christian McCaffrey,RB,9200,SF,@ARI"""


@pytest.fixture
def csv_invalid_position() -> str:
    """Return CSV with invalid position values."""
    return """Name,Position,Salary,Projection
Player 1,WR1,8500,20.0
Player 2,QB,7500,18.0"""


@pytest.fixture
def csv_invalid_salary() -> str:
    """Return CSV with out-of-range salaries."""
    return """Name,Position,Salary,Projection
Player 1,QB,15000,20.0
Player 2,RB,2000,15.0"""


@pytest.fixture
def csv_invalid_projection() -> str:
    """Return CSV with invalid projections."""
    return """Name,Position,Salary,Projection
Player 1,QB,8500,-5.0
Player 2,RB,7500,0.0"""


@pytest.fixture
def csv_invalid_ownership() -> str:
    """Return CSV with invalid ownership percentages."""
    return """Name,Position,Salary,Projection,Ownership
Player 1,QB,8500,20.0,150.0
Player 2,RB,7500,18.0,-10.0"""


@pytest.fixture
def large_csv_data() -> str:
    """Generate CSV with 500 players for performance testing."""
    lines = ["Name,Position,Salary,Projection,Team,Opponent"]
    positions = ['QB', 'RB', 'WR', 'TE', 'DST']
    
    for i in range(500):
        pos = positions[i % len(positions)]
        salary = 3000 + (i * 14)  # Range from 3000 to ~10000
        projection = 5.0 + (i * 0.05)
        lines.append(f"Player{i},{pos},{salary},{projection},TEAM,OPP")
    
    return "\n".join(lines)


@pytest.fixture
def valid_dataframe() -> pd.DataFrame:
    """Return a valid DataFrame for testing."""
    return pd.DataFrame({
        'name': ['Patrick Mahomes', 'Christian McCaffrey', 'Tyreek Hill'],
        'position': ['QB', 'RB', 'WR'],
        'salary': [8500, 9200, 8000],
        'projection': [24.2, 22.1, 21.8],
        'team': ['KC', 'SF', 'MIA'],
        'opponent': ['LV', '@ARI', '@BUF'],
        'ownership': [28.5, 32.0, 22.3]
    })


@pytest.fixture
def mock_uploaded_file():
    """Factory fixture for creating mock uploaded file objects."""
    class MockUploadedFile:
        def __init__(self, content: str, filename: str):
            self.name = filename
            self.content = content
            self._stringio = StringIO(content)
        
        def read(self):
            return self._stringio.read()
        
        def seek(self, pos):
            return self._stringio.seek(pos)
        
        def __iter__(self):
            return iter(self._stringio)
    
    def _create_mock(content: str, filename: str = "test_data.csv"):
        return MockUploadedFile(content, filename)
    
    return _create_mock

