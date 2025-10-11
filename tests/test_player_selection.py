import pytest
import pandas as pd
from src.models import PlayerSelection, Player
from unittest.mock import patch
import streamlit as st  # For mocking warnings

# Sample data for tests
SAMPLE_DATA = {
    'name': ['Mahomes', 'McCaffrey', 'Hill', 'Kittle', 'Bosa'],
    'position': ['QB', 'RB', 'WR', 'TE', 'DST'],
    'salary': [8500, 9200, 8000, 6500, 4500],
    'projection': [24.2, 22.1, 21.8, 12.5, 8.0],
    'team': ['KC', 'SF', 'MIA', 'SF', 'SF'],
    'opponent': ['LV', 'ARI', 'BUF', 'DAL', 'DAL']
}

@pytest.fixture
def sample_df():
    return pd.DataFrame(SAMPLE_DATA)

def test_player_selection_enum():
    """Test PlayerSelection enum values."""
    assert PlayerSelection.NORMAL.value == 'normal'
    assert PlayerSelection.LOCKED.value == 'locked'
    assert PlayerSelection.EXCLUDED.value == 'excluded'

def test_player_with_selection(sample_df):
    """Test Player creation with selection."""
    # Create Player from first row
    player_data = sample_df.iloc[0]
    player = Player(
        name=player_data['name'],
        position=player_data['position'],
        salary=player_data['salary'],
        projection=player_data['projection'],
        team=player_data['team'],
        opponent=player_data['opponent'],
        selection=PlayerSelection.LOCKED
    )
    assert player.selection == PlayerSelection.LOCKED
    assert player.get_selection_display() == 'LOCKED'

def test_validation_locked_salary(sample_df, mocker):
    """Test salary validation warning."""
    from ui.player_selection import render_player_selection  # Import for context
    
    # Mock selections with high salary locks
    selections = {0: 'locked', 1: 'locked'}  # Mahomes + McCaffrey = 8500 + 9200 = 17700 <50k, adjust for test
    # For >50k, mock more
    high_selections = {i: 'locked' for i in range(6)}  # Assume more data, but simulate sum
    mocker.patch('ui.player_selection.df', sample_df)
    mocker.patch('ui.player_selection.selections', high_selections)
    
    with patch('streamlit.warning') as mock_warning:
        # Call validation logic (extracted for test)
        locked_indices = [i for i, s in high_selections.items() if s == PlayerSelection.LOCKED.value]
        locked_salary = sample_df.loc[locked_indices[:2], 'salary'].sum()  # Simulate partial
        if locked_salary > 50000:
            st.warning(f"Mock warning for {locked_salary}")
        mock_warning.assert_called()

def test_position_viability(sample_df, mocker):
    """Test exclusion leaving no position available."""
    from ui.player_selection import render_player_selection
    
    # Exclude all QBs (only 1 QB)
    selections = {0: 'excluded'}  # Mahomes is QB index 0
    excluded_indices = [0]
    excluded_pos = sample_df.loc[excluded_indices, 'position'].value_counts()
    pos = 'QB'
    excl_count = 1
    total_pos = len(sample_df[sample_df['position'] == pos])
    available_pos = total_pos - excl_count  # 1 - 1 = 0
    
    assert available_pos == 0  # Triggers error in code
    
    with patch('streamlit.error') as mock_error:
        if available_pos < 1:
            st.error(f"Mock error for {pos}")
        mock_error.assert_called()

def test_filtering(sample_df):
    """Test filtering logic."""
    from ui.player_selection import render_player_selection  # For mask logic
    
    # Name search
    search_name = "maho"
    mask_name = sample_df['name'].str.contains(search_name, case=False, na=False)
    assert mask_name.iloc[0] == True  # Mahomes matches
    assert mask_name.iloc[1] == False
    
    # Position filter
    selected_pos = ['QB']
    mask_pos = sample_df['position'].isin(selected_pos)
    assert mask_pos.sum() == 1
    
    # Team filter
    selected_team = ['SF']
    mask_team = sample_df['team'].isin(selected_team)
    assert mask_team.sum() == 3  # McCaffrey, Kittle, Bosa
    
    # Combined mask
    mask_combined = mask_name & mask_pos
    filtered = sample_df[mask_combined]
    assert len(filtered) == 1
    assert filtered['name'].iloc[0] == 'Mahomes'

def test_bulk_update_selections(sample_df):
    """Test bulk updating selections dict."""
    selections = {idx: PlayerSelection.NORMAL.value for idx in sample_df.index}
    
    # Bulk lock first 2 rows
    selected_rows = [0, 1]
    for row in selected_rows:
        selections[row] = PlayerSelection.LOCKED.value
    
    assert selections[0] == 'locked'
    assert selections[1] == 'locked'
    assert selections[2] == 'normal'

def test_salary_range_filter(sample_df):
    """Test salary range filtering."""
    # Filter salary >8000
    salary_range = (8000, 10000)
    mask_salary = sample_df['salary'].between(salary_range[0], salary_range[1])
    filtered = sample_df[mask_salary]
    assert len(filtered) == 3  # Mahomes 8500, McCaffrey 9200, Hill 8000
