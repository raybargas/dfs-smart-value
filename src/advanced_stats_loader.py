"""
Advanced Stats Loader Module

Main orchestrator for loading and validating 4 Excel season stats files with graceful degradation.
Part of DFS Advanced Stats Migration (2025-10-18) - Phase 1 Infrastructure.

This module provides the FileLoader class which coordinates:
- Loading 4 Excel files (Pass, Rush, Receiving, Snaps)
- Schema validation with required columns
- File existence and validity checks
- Graceful degradation (continues with 2-3 files if some missing)
- Integration with TeamNormalizer and PlayerNameMapper

Performance Target: <2 seconds for loading all 4 files
"""

import os
import logging
import time
from typing import Dict, List, Optional
import pandas as pd

# Handle both module and direct import
try:
    from .team_normalizer import TeamNormalizer
    from .player_name_mapper import PlayerNameMapper, PlayerMapping, normalize_name
except ImportError:
    # Fallback for direct execution
    from team_normalizer import TeamNormalizer
    from player_name_mapper import PlayerNameMapper, PlayerMapping, normalize_name

# Configure logging
logger = logging.getLogger(__name__)

# Required columns by file type
REQUIRED_COLUMNS = {
    'pass': ['Name', 'Team', 'POS', 'W', 'CPOE', 'aDOT', 'Deep Throw %', '1Read %'],
    'rush': ['Name', 'Team', 'POS', 'W', 'YACO/ATT', 'MTF/ATT', 'Success Rate', 'STUFF %'],
    'receiving': ['Name', 'Team', 'POS', 'W', 'TPRR', 'YPRR', 'RTE %', '1READ %', 'CTGT %'],
    'snaps': ['Name', 'Team', 'POS', 'W', 'Snap %', 'FP/G', 'FP']
}

# File naming patterns
FILE_PATTERNS = {
    'pass': 'Pass 2025.xlsx',
    'rush': 'Rush 2025.xlsx',
    'receiving': 'Receiving 2025.xlsx',
    'snaps': 'Snaps 2025.xlsx'
}

# Optional columns for extended functionality
OPTIONAL_COLUMNS = {
    'pass': ['TTT', 'RPO %', 'ATT', 'CMP', 'TD', 'INT', 'Pressure %', 'Blitz %'],
    'rush': ['ATT.1', 'ATT.2', 'YDS', 'TD', 'FUM', '1st Down %', 'Breakaway %'],
    'receiving': ['WIDE RTE %', 'SLOT RTE %', 'INLINE RTE %', 'BACK RTE %', 'YAC', 'Air Yards'],
    'snaps': ['Snap %.1', 'Snap %.2', 'Snap %.3', 'Snap %.4', 'Snap %.5', 'Red Zone Snaps']
}


class FileLoader:
    """
    Handles loading of season stats files with graceful degradation.

    Features:
    - Loads 4 Excel files from seasonStats directory
    - Validates file existence, readability, and size
    - Validates schema (required columns)
    - Graceful degradation: continues if 1-2 files missing
    - Automatic team normalization
    - Performance optimized: <2 seconds for all 4 files

    Usage:
        loader = FileLoader("DFS/seasonStats/")
        files = loader.load_all_files()
        report = loader.get_load_report()
    """

    def __init__(self, season_stats_dir: str = "DFS/seasonStats/"):
        """
        Initialize FileLoader.

        Args:
            season_stats_dir: Directory containing the 4 Excel files

        Raises:
            FileNotFoundError: If season_stats_dir doesn't exist
        """
        self.season_stats_dir = os.path.abspath(season_stats_dir)
        self.loaded_files: Dict[str, Optional[pd.DataFrame]] = {}
        self.load_errors: Dict[str, str] = {}
        self.load_warnings: List[str] = []
        self.load_times: Dict[str, float] = {}

        # Validate directory exists
        if not os.path.exists(self.season_stats_dir):
            raise FileNotFoundError(
                f"ERR-ADV-001: Season stats directory not found: {self.season_stats_dir}"
            )

        logger.info(f"FileLoader initialized with directory: {self.season_stats_dir}")

    def load_all_files(self) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Load all 4 season stats files with validation and normalization.

        Returns:
            Dictionary with keys: 'pass', 'rush', 'receiving', 'snaps'
            Values are DataFrames if successful, None if failed.

        Performance: <2 seconds for all files
        """
        start_time = time.time()
        logger.info(f"Loading season stats files from {self.season_stats_dir}")

        for file_key, file_pattern in FILE_PATTERNS.items():
            file_start = time.time()
            file_path = os.path.join(self.season_stats_dir, file_pattern)

            try:
                # Step 1: Check file validity
                if not self._check_file_valid(file_path, file_key):
                    self.loaded_files[file_key] = None
                    continue

                # Step 2: Load Excel file
                logger.info(f"Loading {file_pattern}...")
                df = pd.read_excel(file_path)

                load_time = time.time() - file_start
                self.load_times[file_key] = load_time

                logger.info(
                    f"Successfully loaded {file_pattern} "
                    f"({len(df)} records, {len(df.columns)} columns) "
                    f"in {load_time:.2f} seconds"
                )

                # Step 3: Validate schema
                if not self.validate_file_schema(file_key, df):
                    self.loaded_files[file_key] = None
                    continue

                # Step 4: Log optional columns status
                self._check_optional_columns(file_key, df)

                # Step 5: Normalize team abbreviations
                df = TeamNormalizer.normalize_dataframe(df)

                # Step 6: Store the processed DataFrame
                self.loaded_files[file_key] = df

            except Exception as e:
                error_msg = f"ERR-ADV-002: Failed to load {file_pattern}: {str(e)}"
                logger.error(error_msg)
                self.load_errors[file_key] = error_msg
                self.loaded_files[file_key] = None

        # Calculate totals
        total_time = time.time() - start_time
        files_loaded = sum(1 for df in self.loaded_files.values() if df is not None)
        files_failed = len(self.loaded_files) - files_loaded

        # Performance check
        if total_time > 2.0:
            logger.warning(
                f"ERR-ADV-005: Performance benchmark exceeded - "
                f"Loading took {total_time:.2f} seconds (target: <2 seconds)"
            )

        # Validate minimum files requirement
        if files_loaded < 2:
            logger.error(
                f"Critical: Only {files_loaded} files loaded. "
                f"Need at least 2 files for meaningful analysis."
            )
        elif files_failed > 0:
            logger.warning(
                f"Graceful degradation: {files_failed} files failed to load, "
                f"continuing with {files_loaded} files"
            )
        else:
            logger.info(
                f"✅ All {files_loaded} files loaded successfully "
                f"in {total_time:.2f} seconds"
            )

        # Validate team consistency across files
        if files_loaded > 1:
            self._validate_team_consistency()

        return self.loaded_files

    def _check_file_valid(self, file_path: str, file_key: str) -> bool:
        """
        Check if file exists and is valid before loading.

        Validates:
        - File existence
        - Read permissions
        - File format (.xlsx)
        - File size (<50MB error, >10MB warning)

        Args:
            file_path: Path to file
            file_key: File type key

        Returns:
            True if file is valid, False otherwise
        """
        # Check existence
        if not os.path.exists(file_path):
            error_msg = f"File not found: {file_path}"
            logger.error(error_msg)
            self.load_errors[file_key] = error_msg
            return False

        # Check readable
        if not os.access(file_path, os.R_OK):
            error_msg = f"File not readable: {file_path}"
            logger.error(error_msg)
            self.load_errors[file_key] = error_msg
            return False

        # Check file extension
        if not file_path.endswith('.xlsx'):
            error_msg = f"ERR-ADV-002: Invalid file format (expected .xlsx): {file_path}"
            logger.error(error_msg)
            self.load_errors[file_key] = error_msg
            return False

        # Check file size
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if file_size_mb > 50:
            error_msg = f"File too large (>50MB): {file_path} ({file_size_mb:.1f} MB)"
            logger.error(error_msg)
            self.load_errors[file_key] = error_msg
            return False

        if file_size_mb > 10:
            warning_msg = f"Large file size warning: {file_path} ({file_size_mb:.1f} MB)"
            logger.warning(warning_msg)
            self.load_warnings.append(warning_msg)

        if file_size_mb < 0.001:  # Less than 1KB
            error_msg = f"File appears to be empty: {file_path} ({file_size_mb*1024:.1f} KB)"
            logger.error(error_msg)
            self.load_errors[file_key] = error_msg
            return False

        return True

    def validate_file_schema(self, file_key: str, df: pd.DataFrame) -> bool:
        """
        Validate that required columns exist in loaded DataFrame.

        Args:
            file_key: One of 'pass', 'rush', 'receiving', 'snaps'
            df: Loaded DataFrame

        Returns:
            True if all required columns present, False otherwise
        """
        if file_key not in REQUIRED_COLUMNS:
            logger.error(f"Unknown file key: {file_key}")
            return False

        required_cols = REQUIRED_COLUMNS[file_key]
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            error_msg = f"ERR-ADV-003: Missing required columns in {file_key}: {missing_cols}"
            logger.error(error_msg)
            self.load_errors[file_key] = error_msg
            return False

        # Check for empty required columns
        empty_cols = []
        for col in required_cols:
            if df[col].isna().all():
                empty_cols.append(col)

        if empty_cols:
            warning_msg = f"Required columns are empty in {file_key}: {empty_cols}"
            logger.warning(warning_msg)
            self.load_warnings.append(warning_msg)

        logger.info(f"✅ Schema validation passed for {file_key}")
        return True

    def _check_optional_columns(self, file_key: str, df: pd.DataFrame):
        """
        Check for optional columns and log their availability.

        Args:
            file_key: File type key
            df: Loaded DataFrame
        """
        if file_key not in OPTIONAL_COLUMNS:
            return

        optional_cols = OPTIONAL_COLUMNS[file_key]
        available_optional = [col for col in optional_cols if col in df.columns]
        missing_optional = [col for col in optional_cols if col not in df.columns]

        if available_optional:
            logger.info(f"Optional columns available in {file_key}: {available_optional}")

        if missing_optional:
            logger.debug(f"Optional columns missing in {file_key}: {missing_optional}")

    def _validate_team_consistency(self):
        """
        Validate team consistency across loaded files.

        Logs warnings for teams that appear in some files but not others.
        """
        # Use TeamNormalizer's validation method
        loaded_dfs = {k: v for k, v in self.loaded_files.items() if v is not None}

        if len(loaded_dfs) < 2:
            return

        validation_report = TeamNormalizer.validate_team_consistency(loaded_dfs)

        if validation_report['warnings']:
            for warning in validation_report['warnings']:
                self.load_warnings.append(warning)

        logger.info(
            f"Team consistency check: {len(validation_report['common_teams'])} common teams "
            f"across {len(loaded_dfs)} files"
        )

    def get_load_report(self) -> Dict:
        """
        Generate comprehensive report of load success/failures.

        Returns:
            {
                'files_loaded': int,
                'files_failed': int,
                'errors': Dict[str, str],
                'warnings': List[str],
                'load_times': Dict[str, float],
                'total_records': int,
                'file_details': Dict[str, Dict]
            }
        """
        files_loaded = sum(1 for df in self.loaded_files.values() if df is not None)
        files_failed = len(self.loaded_files) - files_loaded

        # Collect detailed file information
        file_details = {}
        total_records = 0

        for file_key, df in self.loaded_files.items():
            if df is not None:
                file_details[file_key] = {
                    'records': len(df),
                    'columns': len(df.columns),
                    'load_time': self.load_times.get(file_key, 0.0),
                    'unique_players': df['Name'].nunique() if 'Name' in df.columns else 0,
                    'unique_teams': df['Team'].nunique() if 'Team' in df.columns else 0,
                    'weeks': sorted(df['W'].unique().tolist()) if 'W' in df.columns else []
                }
                total_records += len(df)
            else:
                file_details[file_key] = None

        return {
            'files_loaded': files_loaded,
            'files_failed': files_failed,
            'errors': self.load_errors,
            'warnings': self.load_warnings,
            'load_times': self.load_times,
            'total_load_time': sum(self.load_times.values()),
            'total_records': total_records,
            'file_details': file_details
        }

    def get_file(self, file_key: str) -> Optional[pd.DataFrame]:
        """
        Get a specific loaded file by key.

        Args:
            file_key: One of 'pass', 'rush', 'receiving', 'snaps'

        Returns:
            DataFrame if loaded, None otherwise
        """
        return self.loaded_files.get(file_key)

    def get_all_files(self) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Get all loaded files.

        Returns:
            Dictionary of loaded DataFrames
        """
        return self.loaded_files

    def has_minimum_files(self) -> bool:
        """
        Check if minimum number of files loaded (at least 2).

        Returns:
            True if at least 2 files loaded successfully
        """
        files_loaded = sum(1 for df in self.loaded_files.values() if df is not None)
        return files_loaded >= 2


# Convenience functions for quick loading
def load_season_stats_files(
    season_stats_dir: str = "DFS/seasonStats/"
) -> Dict[str, Optional[pd.DataFrame]]:
    """
    Convenience function to load all season stats files.

    Args:
        season_stats_dir: Directory containing the 4 Excel files

    Returns:
        Dictionary of loaded DataFrames

    Performance: <2 seconds for all files
    """
    loader = FileLoader(season_stats_dir)
    files = loader.load_all_files()

    # Log report
    report = loader.get_load_report()
    if report['files_failed'] > 0:
        logger.warning(
            f"Failed to load {report['files_failed']} files: {report['errors']}"
        )

    return files


def create_player_mapper(
    player_df: pd.DataFrame,
    season_files: Dict[str, Optional[pd.DataFrame]],
    threshold: int = 85
) -> PlayerNameMapper:
    """
    Convenience function to create player name mappings.

    Args:
        player_df: Main player DataFrame
        season_files: Loaded season stat files
        threshold: Minimum fuzzy match score

    Returns:
        PlayerNameMapper with cached mappings

    Performance: <2 seconds for 500 players
    """
    mapper = PlayerNameMapper(threshold=threshold)
    mapper.create_mappings(player_df, season_files)

    # Log match report
    report = mapper.get_match_report()
    logger.info(
        f"Player matching complete: {report['total_players']} players, "
        f"match rate: {report['match_rate']}%, "
        f"avg score: {report['avg_match_score']}%"
    )

    if report['match_rate'] < 90:
        logger.warning(
            f"ERR-ADV-004: Player match rate below threshold - "
            f"{report['match_rate']}% (target: >90%)"
        )

    if report['no_matches']:
        logger.warning(f"{len(report['no_matches'])} players had no matches")

    return mapper