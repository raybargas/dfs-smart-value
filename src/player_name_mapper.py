"""
Player Name Mapper Module

Efficient player name mapping using one-time fuzzy matching for the DFS Advanced Stats Migration.
Part of Phase 1 Infrastructure (2025-10-18).

This module provides:
- PlayerNameMapper: One-time fuzzy matching with caching for performance
- Bulk DataFrame operations (NO iterrows for performance)
- Name normalization with suffix handling
- Position and team-aware matching

Performance Target: <2 seconds for 500 players across 4 files
"""

import pandas as pd
import numpy as np
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set
from fuzzywuzzy import fuzz, process
import time

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class PlayerMapping:
    """
    Result of player name fuzzy matching across all stats files.

    Stores the best match found in each file along with match quality scores.
    """
    original_name: str           # Name from player_df
    normalized_name: str         # Normalized for matching
    position: str                # Player position
    team: str                    # Player team (normalized)

    # Matched names in each file
    matched_name_pass: Optional[str] = None
    matched_name_rush: Optional[str] = None
    matched_name_receiving: Optional[str] = None
    matched_name_snaps: Optional[str] = None

    # Match quality scores (0-100)
    match_score_pass: float = 0.0
    match_score_rush: float = 0.0
    match_score_receiving: float = 0.0
    match_score_snaps: float = 0.0

    def get_best_match_score(self) -> float:
        """Get the best match score across all files."""
        scores = [
            self.match_score_pass,
            self.match_score_rush,
            self.match_score_receiving,
            self.match_score_snaps
        ]
        non_zero = [s for s in scores if s > 0]
        return max(non_zero) if non_zero else 0.0

    def has_any_match(self) -> bool:
        """Check if player has at least one match."""
        return any([
            self.matched_name_pass,
            self.matched_name_rush,
            self.matched_name_receiving,
            self.matched_name_snaps
        ])


def normalize_name(name: str) -> str:
    """
    Normalize player name for matching.

    Transformations:
        - Lowercase
        - Remove suffixes (Jr., Sr., III, II, IV)
        - Remove periods and apostrophes
        - Normalize hyphens to spaces
        - Collapse multiple spaces

    Examples:
        "Patrick Mahomes II" → "patrick mahomes"
        "De'Von Achane" → "devon achane"
        "Clyde Edwards-Helaire" → "clyde edwards helaire"

    Args:
        name: Raw player name

    Returns:
        Normalized name for fuzzy matching
    """
    if pd.isna(name):
        return ""

    # Convert to lowercase
    normalized = str(name).lower().strip()

    # Remove common suffixes (order matters - longer first)
    suffixes = [' iii', ' jr.', ' sr.', ' iv', ' ii', ' jr', ' sr', ' v']
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)].strip()
            break  # Only remove one suffix

    # Remove punctuation
    normalized = normalized.replace('.', '')
    normalized = normalized.replace("'", '')
    normalized = normalized.replace('-', ' ')
    normalized = normalized.replace(',', '')

    # Normalize whitespace (collapse multiple spaces)
    normalized = ' '.join(normalized.split())

    return normalized


class PlayerNameMapper:
    """
    Creates player name mapping using fuzzy matching.

    CRITICAL: This performs ONE-TIME fuzzy matching upfront, then results are used
    for efficient DataFrame merge operations (NOT iterrows).

    Features:
    - Bulk preprocessing of candidate names for performance
    - Position and team-aware matching for accuracy
    - Configurable match threshold
    - Comprehensive match quality reporting

    Performance: <2 seconds for 500 players across 4 files
    """

    def __init__(self, threshold: int = 85):
        """
        Initialize PlayerNameMapper.

        Args:
            threshold: Minimum fuzzy match score (0-100) to accept a match
        """
        self.threshold = threshold
        self.mappings: Dict[str, PlayerMapping] = {}
        self._match_cache: Dict[str, Dict] = {}  # Cache for performance

    def create_mappings(
        self,
        player_df: pd.DataFrame,
        season_files: Dict[str, Optional[pd.DataFrame]]
    ) -> Dict[str, PlayerMapping]:
        """
        Create player name mappings for all files using optimized bulk operations.

        This is the MAIN ENTRY POINT that performs all fuzzy matching upfront.

        Args:
            player_df: Main player DataFrame with 'name', 'position', 'team' columns
            season_files: Dict of loaded season stat DataFrames

        Returns:
            Dictionary: {original_name: PlayerMapping object}

        Performance: <2 seconds for 500 players across 4 files
        """
        start_time = time.time()
        logger.info(f"Creating player name mappings for {len(player_df)} players...")

        # Pre-process all stats files for efficiency
        processed_files = self._preprocess_files(season_files)

        # Batch process all players (vectorized where possible)
        unique_players = player_df[['name', 'position', 'team']].drop_duplicates()

        for idx, row in unique_players.iterrows():
            player_name = row.get('name', '')
            player_team = row.get('team', '')
            player_position = row.get('position', '')

            if not player_name or pd.isna(player_name):
                continue

            # Create PlayerMapping object
            mapping = PlayerMapping(
                original_name=player_name,
                normalized_name=normalize_name(player_name),
                position=player_position,
                team=player_team
            )

            # Match against each preprocessed file
            for file_key, file_data in processed_files.items():
                if file_data is None:
                    continue

                matched_name, match_score = self._fuzzy_match_optimized(
                    player_name, player_team, player_position, file_data, file_key
                )

                # Store match results
                setattr(mapping, f'matched_name_{file_key}', matched_name)
                setattr(mapping, f'match_score_{file_key}', match_score)

            self.mappings[player_name] = mapping

        elapsed = time.time() - start_time
        logger.info(f"Created mappings for {len(self.mappings)} players in {elapsed:.2f} seconds")

        # Log match statistics
        self._log_match_statistics()

        return self.mappings

    def _preprocess_files(self, season_files: Dict[str, Optional[pd.DataFrame]]) -> Dict:
        """
        Preprocess stats files for efficient matching.

        Creates normalized name columns and position/team indices for fast lookup.

        Args:
            season_files: Raw season stat DataFrames

        Returns:
            Preprocessed file data for optimized matching
        """
        processed = {}

        for file_key, df in season_files.items():
            if df is None or df.empty:
                processed[file_key] = None
                continue

            # Create normalized names column (vectorized)
            df_copy = df.copy()
            df_copy['_normalized_name'] = df_copy['Name'].apply(normalize_name)

            # Create team and position indices for fast filtering
            team_groups = {}
            pos_groups = {}

            if 'Team' in df_copy.columns:
                team_groups = {team: group for team, group in df_copy.groupby('Team')}

            if 'POS' in df_copy.columns:
                pos_groups = {pos: group for pos, group in df_copy.groupby('POS')}

            processed[file_key] = {
                'df': df_copy,
                'team_groups': team_groups,
                'pos_groups': pos_groups,
                'all_names': df_copy[['Name', '_normalized_name']].drop_duplicates().to_dict('records')
            }

        return processed

    def _fuzzy_match_optimized(
        self,
        player_name: str,
        player_team: str,
        player_position: str,
        file_data: Dict,
        file_key: str
    ) -> Tuple[Optional[str], float]:
        """
        Optimized fuzzy matching using preprocessed data.

        Uses team and position filtering to reduce search space, then applies
        fuzzy matching only on the filtered subset.

        Args:
            player_name: Name to match
            player_team: Team for filtering
            player_position: Position for filtering
            file_data: Preprocessed file data
            file_key: File identifier for caching

        Returns:
            (best_match_name, match_score)
        """
        # Check cache first
        cache_key = f"{file_key}_{player_name}_{player_team}_{player_position}"
        if cache_key in self._match_cache:
            return self._match_cache[cache_key]

        normalized_search = normalize_name(player_name)
        df = file_data['df']

        # Strategy 1: Try exact team + position match first
        candidates = df
        if player_team and 'Team' in df.columns:
            team_candidates = df[df['Team'] == player_team]
            if not team_candidates.empty:
                candidates = team_candidates

        # Further filter by position if available
        if player_position and 'POS' in candidates.columns:
            # Handle multi-position players (e.g., "RB/WR")
            pos_candidates = candidates[
                candidates['POS'].str.contains(player_position, na=False, regex=False)
            ]
            if not pos_candidates.empty:
                candidates = pos_candidates

        if candidates.empty:
            result = (None, 0.0)
            self._match_cache[cache_key] = result
            return result

        # Get unique names from filtered candidates
        candidate_records = candidates[['Name', '_normalized_name']].drop_duplicates().to_dict('records')

        if not candidate_records:
            result = (None, 0.0)
            self._match_cache[cache_key] = result
            return result

        # Perform fuzzy matching on filtered set
        best_match = None
        best_score = 0.0

        for record in candidate_records:
            score = fuzz.ratio(normalized_search, record['_normalized_name'])
            if score > best_score:
                best_score = score
                best_match = record['Name']

        # Apply threshold
        if best_score >= self.threshold:
            result = (best_match, best_score)
        else:
            # Strategy 2: If no good match with filters, try without position filter
            if player_position and 'POS' in df.columns:
                # Try again without position filter
                return self._fuzzy_match_fallback(player_name, player_team, file_data, file_key)
            result = (None, best_score)

        self._match_cache[cache_key] = result
        return result

    def _fuzzy_match_fallback(
        self,
        player_name: str,
        player_team: str,
        file_data: Dict,
        file_key: str
    ) -> Tuple[Optional[str], float]:
        """
        Fallback matching when position-filtered matching fails.

        Tries matching with team filter only, useful for players who changed
        positions or have different position listings across files.

        Args:
            player_name: Name to match
            player_team: Team for filtering
            file_data: Preprocessed file data
            file_key: File identifier

        Returns:
            (best_match_name, match_score)
        """
        normalized_search = normalize_name(player_name)
        df = file_data['df']

        # Try with team filter only
        candidates = df
        if player_team and 'Team' in df.columns:
            team_candidates = df[df['Team'] == player_team]
            if not team_candidates.empty:
                candidates = team_candidates

        if candidates.empty:
            return (None, 0.0)

        # Get unique names
        candidate_records = candidates[['Name', '_normalized_name']].drop_duplicates().to_dict('records')

        best_match = None
        best_score = 0.0

        for record in candidate_records:
            score = fuzz.ratio(normalized_search, record['_normalized_name'])
            if score > best_score:
                best_score = score
                best_match = record['Name']

        if best_score >= self.threshold:
            return (best_match, best_score)

        return (None, best_score)

    def fuzzy_match_player(
        self,
        player_name: str,
        player_team: str,
        player_position: str,
        stats_df: pd.DataFrame
    ) -> Tuple[Optional[str], float]:
        """
        Legacy interface for single player fuzzy matching.

        Maintained for backward compatibility, but create_mappings() is preferred
        for bulk operations.

        Args:
            player_name: Name to match
            player_team: Team for additional validation
            player_position: Position for filtering
            stats_df: DataFrame to search

        Returns:
            (best_match_name, match_score)
        """
        if stats_df is None or stats_df.empty:
            return None, 0.0

        # Use the optimized version
        file_data = {
            'df': stats_df.copy(),
            'team_groups': {},
            'pos_groups': {},
            'all_names': []
        }
        file_data['df']['_normalized_name'] = file_data['df']['Name'].apply(normalize_name)

        return self._fuzzy_match_optimized(
            player_name, player_team, player_position, file_data, 'single'
        )

    def get_match_report(self) -> Dict:
        """
        Generate comprehensive report on match quality.

        Returns:
            {
                'total_players': int,
                'matched_pass': int,
                'matched_rush': int,
                'matched_receiving': int,
                'matched_snaps': int,
                'avg_match_score': float,
                'match_rate': float,  # Percentage with at least one match
                'perfect_matches': int,  # Score = 100
                'below_threshold': List[str],  # Players with low scores
                'no_matches': List[str]  # Players with no matches
            }
        """
        total = len(self.mappings)

        if total == 0:
            return {
                'total_players': 0,
                'matched_pass': 0,
                'matched_rush': 0,
                'matched_receiving': 0,
                'matched_snaps': 0,
                'avg_match_score': 0.0,
                'match_rate': 0.0,
                'perfect_matches': 0,
                'below_threshold': [],
                'no_matches': []
            }

        # Count matches by file
        matched_pass = sum(1 for m in self.mappings.values() if m.matched_name_pass)
        matched_rush = sum(1 for m in self.mappings.values() if m.matched_name_rush)
        matched_receiving = sum(1 for m in self.mappings.values() if m.matched_name_receiving)
        matched_snaps = sum(1 for m in self.mappings.values() if m.matched_name_snaps)

        # Calculate average match score
        all_scores = []
        for m in self.mappings.values():
            if m.match_score_pass > 0:
                all_scores.append(m.match_score_pass)
            if m.match_score_rush > 0:
                all_scores.append(m.match_score_rush)
            if m.match_score_receiving > 0:
                all_scores.append(m.match_score_receiving)
            if m.match_score_snaps > 0:
                all_scores.append(m.match_score_snaps)

        avg_score = np.mean(all_scores) if all_scores else 0.0

        # Count perfect matches
        perfect_matches = sum(
            1 for score in all_scores if score == 100.0
        )

        # Find problematic players
        below_threshold = []
        no_matches = []

        for name, mapping in self.mappings.items():
            if not mapping.has_any_match():
                no_matches.append(name)
            else:
                # Check if any match is below threshold
                scores = [
                    mapping.match_score_pass,
                    mapping.match_score_rush,
                    mapping.match_score_receiving,
                    mapping.match_score_snaps
                ]
                non_zero_scores = [s for s in scores if s > 0]
                if non_zero_scores and min(non_zero_scores) < self.threshold:
                    below_threshold.append(name)

        # Calculate match rate
        players_with_matches = total - len(no_matches)
        match_rate = (players_with_matches / total * 100) if total > 0 else 0.0

        return {
            'total_players': total,
            'matched_pass': matched_pass,
            'matched_rush': matched_rush,
            'matched_receiving': matched_receiving,
            'matched_snaps': matched_snaps,
            'avg_match_score': round(avg_score, 1),
            'match_rate': round(match_rate, 1),
            'perfect_matches': perfect_matches,
            'below_threshold': sorted(below_threshold),
            'no_matches': sorted(no_matches)
        }

    def _log_match_statistics(self):
        """Log detailed match statistics for monitoring."""
        report = self.get_match_report()

        logger.info(f"Player matching complete: {report['total_players']} players")
        logger.info(f"Match rate: {report['match_rate']}%")
        logger.info(f"Average match score: {report['avg_match_score']}%")
        logger.info(f"Perfect matches (100%): {report['perfect_matches']}")

        if report['match_rate'] < 90:
            logger.warning(f"Match rate below 90% target: {report['match_rate']}%")

        if report['no_matches']:
            logger.warning(f"{len(report['no_matches'])} players with no matches")
            logger.debug(f"No matches: {report['no_matches'][:10]}")  # Log first 10

        if report['below_threshold']:
            logger.warning(f"{len(report['below_threshold'])} players with low match scores")
            logger.debug(f"Below threshold: {report['below_threshold'][:10]}")  # Log first 10

    def create_mapping_dataframe(self, file_key: str) -> pd.DataFrame:
        """
        Create a DataFrame suitable for merging from mappings.

        This is used for bulk DataFrame merge operations instead of iterrows.

        Args:
            file_key: One of 'pass', 'rush', 'receiving', 'snaps'

        Returns:
            DataFrame with columns: original_name, matched_name, match_score
        """
        records = []
        for original_name, mapping in self.mappings.items():
            matched_name = getattr(mapping, f'matched_name_{file_key}', None)
            match_score = getattr(mapping, f'match_score_{file_key}', 0.0)

            if matched_name:  # Only include successful matches
                records.append({
                    'original_name': original_name,
                    'matched_name': matched_name,
                    'match_score': match_score,
                    'normalized_name': mapping.normalized_name
                })

        return pd.DataFrame(records)