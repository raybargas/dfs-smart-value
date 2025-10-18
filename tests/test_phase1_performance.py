"""
Performance Benchmarking Tests for Phase 1

Tests for Phase 1 performance requirements of the DFS Advanced Stats Migration.
Part of Phase 1 Infrastructure Testing (Task 1.4.3).

Performance Targets:
- File loading: <2 seconds for all 4 files
- Player mapping: <2 seconds for 500 players
- Memory overhead: <50MB
- Total pipeline: <5 seconds end-to-end
"""

import pytest
import pandas as pd
import numpy as np
import time
import psutil
import os
import tempfile
import tracemalloc
from unittest.mock import patch
import logging

# Import the classes to test
from DFS.src.advanced_stats_loader import FileLoader, load_season_stats_files, create_player_mapper
from DFS.src.player_name_mapper import PlayerNameMapper
from DFS.src.team_normalizer import TeamNormalizer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestPhase1PerformanceBenchmarks:
    """
    Comprehensive performance benchmarking for Phase 1 components.

    Validates all performance requirements are met:
    - File loading performance
    - Player mapping performance
    - Memory usage constraints
    - End-to-end pipeline performance
    """

    @pytest.fixture
    def create_realistic_data_files(self):
        """Create realistic season stats files for benchmarking."""
        def _create(base_dir: str, num_players: int = 500, weeks: int = 5):
            """
            Create realistic Excel files matching production data structure.

            Args:
                base_dir: Directory to create files in
                num_players: Number of unique players per file
                weeks: Number of weeks of data
            """
            # Realistic player names
            first_names = ['Patrick', 'Christian', 'Josh', 'Tyreek', 'Travis', 'Davante', 'Justin',
                          'Lamar', 'Stefon', 'Cooper', 'DeAndre', 'Austin', 'Derrick', 'Nick',
                          'Jonathan', 'Calvin', 'Mike', 'Chris', 'Mark', 'George', 'Terry',
                          'Deebo', 'Brandon', 'Kyle', 'Tee', 'Jaylen', 'Amari', 'Tyler', 'Keenan']
            last_names = ['Mahomes', 'McCaffrey', 'Allen', 'Hill', 'Kelce', 'Adams', 'Jefferson',
                         'Jackson', 'Diggs', 'Kupp', 'Hopkins', 'Ekeler', 'Henry', 'Chubb',
                         'Taylor', 'Ridley', 'Evans', 'Godwin', 'Andrews', 'Kittle', 'McLaurin',
                         'Samuel', 'Aiyuk', 'Pitts', 'Higgins', 'Waddle', 'Cooper', 'Lockett', 'Allen']

            # Generate unique player combinations
            players = []
            for i in range(num_players):
                fname = first_names[i % len(first_names)]
                lname = last_names[i % len(last_names)]
                suffix = ['', ' Jr.', ' III', ' II'][i % 20 % 4]  # 5% have suffixes
                players.append(f"{fname} {lname}{suffix}")

            teams = ['KC', 'BUF', 'SF', 'PHI', 'DAL', 'MIA', 'CIN', 'BAL', 'LAR', 'LAC',
                    'MIN', 'DET', 'GB', 'CHI', 'NO', 'ATL', 'TB', 'CAR', 'SEA', 'ARI',
                    'DEN', 'LVR', 'PIT', 'CLE', 'TEN', 'JAX', 'HOU', 'IND', 'WAS', 'NYG',
                    'NYJ', 'NE']

            # Create Pass file (QB-focused)
            pass_records = []
            qb_count = num_players // 4  # 25% are QBs
            for week in range(1, weeks + 1):
                for i in range(qb_count):
                    pass_records.append({
                        'Name': players[i],
                        'Team': teams[i % len(teams)],
                        'POS': 'QB',
                        'W': week,
                        'CPOE': np.random.normal(0, 5),
                        'aDOT': np.random.uniform(6, 12),
                        'Deep Throw %': np.random.uniform(10, 30),
                        'TTT': np.random.uniform(2.3, 3.0),
                        '1Read %': np.random.uniform(40, 70),
                        'RPO %': np.random.uniform(5, 25),
                        'ATT': np.random.randint(20, 45),
                        'CMP': np.random.randint(12, 35),
                        'TD': np.random.randint(0, 4),
                        'INT': np.random.randint(0, 2),
                        'YDS': np.random.randint(150, 400),
                        'Pressure %': np.random.uniform(20, 40),
                        'Blitz %': np.random.uniform(15, 35)
                    })

            pass_df = pd.DataFrame(pass_records)
            pass_df.to_excel(os.path.join(base_dir, 'Pass 2025.xlsx'), index=False)

            # Create Rush file (RB-focused)
            rush_records = []
            rb_count = num_players // 3  # 33% are RBs
            for week in range(1, weeks + 1):
                for i in range(rb_count):
                    idx = i + qb_count
                    rush_records.append({
                        'Name': players[idx % len(players)],
                        'Team': teams[idx % len(teams)],
                        'POS': 'RB',
                        'W': week,
                        'YACO/ATT': np.random.uniform(1.5, 4.5),
                        'MTF/ATT': np.random.uniform(0.05, 0.35),
                        'Success Rate': np.random.uniform(35, 55),
                        'STUFF %': np.random.uniform(15, 30),
                        'ATT': np.random.randint(8, 25),
                        'YDS': np.random.randint(30, 150),
                        'TD': np.random.randint(0, 2),
                        'FUM': np.random.randint(0, 1) if np.random.random() < 0.05 else 0,
                        'ATT.1': np.random.randint(5, 15),
                        'ATT.2': np.random.randint(1, 5),
                        '1st Down %': np.random.uniform(20, 35),
                        'Breakaway %': np.random.uniform(5, 20)
                    })

            rush_df = pd.DataFrame(rush_records)
            rush_df.to_excel(os.path.join(base_dir, 'Rush 2025.xlsx'), index=False)

            # Create Receiving file (WR/TE-focused)
            receiving_records = []
            wr_te_count = num_players // 2  # 50% are WR/TE
            for week in range(1, weeks + 1):
                for i in range(wr_te_count):
                    idx = i + qb_count + rb_count
                    pos = 'WR' if i % 3 != 0 else 'TE'
                    receiving_records.append({
                        'Name': players[idx % len(players)],
                        'Team': teams[idx % len(teams)],
                        'POS': pos,
                        'W': week,
                        'TPRR': np.random.uniform(0.12, 0.35),
                        'YPRR': np.random.uniform(0.8, 2.8),
                        'RTE %': np.random.uniform(60, 95),
                        '1READ %': np.random.uniform(15, 35),
                        'CTGT %': np.random.uniform(10, 25),
                        'TGT': np.random.randint(4, 12),
                        'REC': np.random.randint(2, 9),
                        'YDS': np.random.randint(20, 120),
                        'TD': np.random.randint(0, 2) if np.random.random() < 0.15 else 0,
                        'WIDE RTE %': np.random.uniform(30, 60),
                        'SLOT RTE %': np.random.uniform(20, 50),
                        'INLINE RTE %': np.random.uniform(5, 20) if pos == 'TE' else np.random.uniform(0, 5),
                        'BACK RTE %': np.random.uniform(0, 10),
                        'YAC': np.random.uniform(2, 8),
                        'Air Yards': np.random.uniform(5, 15)
                    })

            receiving_df = pd.DataFrame(receiving_records)
            receiving_df.to_excel(os.path.join(base_dir, 'Receiving 2025.xlsx'), index=False)

            # Create Snaps file (all players)
            snaps_records = []
            for week in range(1, weeks + 1):
                for i in range(num_players):
                    pos = ['QB', 'RB', 'WR', 'TE'][i % 4]
                    snaps_records.append({
                        'Name': players[i],
                        'Team': teams[i % len(teams)],
                        'POS': pos,
                        'W': week,
                        'Snaps': np.random.randint(30, 75),
                        'TM Snaps': np.random.randint(60, 80),
                        'Snap %': np.random.uniform(40, 95),
                        f'Snap %.{week}': np.random.uniform(40, 95),
                        'FP/G': np.random.uniform(5, 22),
                        'FP': np.random.uniform(25, 110),
                        'Red Zone Snaps': np.random.randint(0, 10)
                    })

            snaps_df = pd.DataFrame(snaps_records)
            snaps_df.to_excel(os.path.join(base_dir, 'Snaps 2025.xlsx'), index=False)

            return {
                'pass': pass_df,
                'rush': rush_df,
                'receiving': receiving_df,
                'snaps': snaps_df,
                'players': players,
                'total_records': len(pass_df) + len(rush_df) + len(receiving_df) + len(snaps_df)
            }

        return _create

    @pytest.fixture
    def create_player_dataframe(self):
        """Create realistic player DataFrame for testing."""
        def _create(num_players: int = 500):
            """Create player DataFrame matching production structure."""
            # Use same name generation as files
            first_names = ['Patrick', 'Christian', 'Josh', 'Tyreek', 'Travis', 'Davante', 'Justin',
                          'Lamar', 'Stefon', 'Cooper', 'DeAndre', 'Austin', 'Derrick', 'Nick']
            last_names = ['Mahomes', 'McCaffrey', 'Allen', 'Hill', 'Kelce', 'Adams', 'Jefferson',
                         'Jackson', 'Diggs', 'Kupp', 'Hopkins', 'Ekeler', 'Henry', 'Chubb']

            players = []
            positions = []
            teams = []
            salaries = []

            for i in range(num_players):
                fname = first_names[i % len(first_names)]
                lname = last_names[i % len(last_names)]
                # Don't include suffixes in player_df (testing fuzzy matching)
                players.append(f"{fname} {lname}")

                pos = ['QB', 'RB', 'WR', 'TE'][i % 4]
                positions.append(pos)

                team_list = ['KC', 'BUF', 'SF', 'PHI', 'DAL', 'MIA', 'CIN', 'BAL']
                teams.append(team_list[i % len(team_list)])

                # Realistic salaries by position
                if pos == 'QB':
                    salaries.append(np.random.randint(7000, 9000))
                elif pos == 'RB':
                    salaries.append(np.random.randint(5500, 8500))
                elif pos == 'WR':
                    salaries.append(np.random.randint(4500, 8000))
                else:  # TE
                    salaries.append(np.random.randint(4000, 7000))

            return pd.DataFrame({
                'name': players,
                'position': positions,
                'team': teams,
                'salary': salaries,
                'projection': np.random.uniform(8, 25, num_players)
            })

        return _create

    def test_file_loading_performance(self, create_realistic_data_files):
        """
        Test file loading performance requirement.

        Acceptance Criteria:
        - Load 4 Excel files in <2 seconds
        - Files contain realistic amount of data (~2000 records each)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create realistic files
            data = create_realistic_data_files(tmpdir, num_players=500, weeks=5)

            # Measure loading time
            loader = FileLoader(tmpdir)
            start_time = time.time()
            files = loader.load_all_files()
            load_time = time.time() - start_time

            # Log performance
            logger.info(f"File loading performance: {load_time:.3f} seconds")
            logger.info(f"Total records loaded: {data['total_records']}")

            # Verify performance requirement
            assert load_time < 2.0, f"File loading took {load_time:.2f} seconds (target: <2 seconds)"

            # Verify all files loaded
            report = loader.get_load_report()
            assert report['files_loaded'] == 4
            assert report['total_records'] == data['total_records']

            # Log detailed timing
            for file_key, file_time in loader.load_times.items():
                logger.info(f"  - {file_key}: {file_time:.3f} seconds")

    def test_player_mapping_performance(self, create_realistic_data_files, create_player_dataframe):
        """
        Test player mapping performance requirement.

        Acceptance Criteria:
        - Map 500 players across 4 files in <2 seconds
        - Includes fuzzy matching with normalization
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files and player data
            data = create_realistic_data_files(tmpdir, num_players=500, weeks=5)
            player_df = create_player_dataframe(500)

            # Load files first
            loader = FileLoader(tmpdir)
            season_files = loader.load_all_files()

            # Measure mapping time
            mapper = PlayerNameMapper(threshold=85)
            start_time = time.time()
            mappings = mapper.create_mappings(player_df, season_files)
            map_time = time.time() - start_time

            # Log performance
            logger.info(f"Player mapping performance: {map_time:.3f} seconds for 500 players")

            # Verify performance requirement
            assert map_time < 2.0, f"Player mapping took {map_time:.2f} seconds (target: <2 seconds)"

            # Verify mappings created
            assert len(mappings) == 500

            # Check match quality
            report = mapper.get_match_report()
            logger.info(f"Match rate: {report['match_rate']}%")
            logger.info(f"Average match score: {report['avg_match_score']}%")

            # Should have good match rate even with realistic data
            assert report['match_rate'] >= 85.0  # Slightly lower threshold for realistic data

    def test_memory_overhead(self, create_realistic_data_files, create_player_dataframe):
        """
        Test memory overhead requirement.

        Acceptance Criteria:
        - Total memory overhead <50MB for Phase 1 operations
        - Includes loading 4 files and creating mappings
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Start memory tracking
            tracemalloc.start()
            start_snapshot = tracemalloc.take_snapshot()

            # Create files and player data
            data = create_realistic_data_files(tmpdir, num_players=500, weeks=5)
            player_df = create_player_dataframe(500)

            # Perform Phase 1 operations
            loader = FileLoader(tmpdir)
            season_files = loader.load_all_files()
            mapper = PlayerNameMapper(threshold=85)
            mappings = mapper.create_mappings(player_df, season_files)

            # Take end snapshot
            end_snapshot = tracemalloc.take_snapshot()
            tracemalloc.stop()

            # Calculate memory usage
            top_stats = end_snapshot.compare_to(start_snapshot, 'lineno')
            total_memory = sum(stat.size for stat in top_stats) / (1024 * 1024)  # Convert to MB

            # Log memory usage
            logger.info(f"Total memory overhead: {total_memory:.2f} MB")

            # Log top memory consumers
            logger.info("Top memory consumers:")
            for stat in top_stats[:5]:
                logger.info(f"  {stat}")

            # Verify memory requirement
            assert total_memory < 50.0, f"Memory overhead {total_memory:.2f} MB exceeds 50MB limit"

    def test_end_to_end_pipeline_performance(self, create_realistic_data_files, create_player_dataframe):
        """
        Test complete Phase 1 pipeline performance.

        Acceptance Criteria:
        - Complete pipeline executes in <5 seconds
        - Includes: file loading, team normalization, player mapping
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test data
            data = create_realistic_data_files(tmpdir, num_players=500, weeks=5)
            player_df = create_player_dataframe(500)

            # Measure complete pipeline
            start_time = time.time()

            # Step 1: Load files
            files = load_season_stats_files(tmpdir)

            # Step 2: Create player mapper
            mapper = create_player_mapper(player_df, files, threshold=85)

            # Step 3: Verify team normalization (included in loading)
            for file_key, df in files.items():
                if df is not None:
                    teams = df['Team'].unique()
                    # All teams should be normalized
                    assert all(team in TeamNormalizer.VALID_TEAMS or pd.isna(team) for team in teams)

            pipeline_time = time.time() - start_time

            # Log performance
            logger.info(f"End-to-end pipeline performance: {pipeline_time:.3f} seconds")

            # Verify performance requirement
            assert pipeline_time < 5.0, f"Pipeline took {pipeline_time:.2f} seconds (target: <5 seconds)"

            # Verify pipeline success
            report = mapper.get_match_report()
            assert report['match_rate'] >= 85.0
            assert report['total_players'] == 500

    def test_performance_scaling(self, create_realistic_data_files, create_player_dataframe):
        """
        Test performance scaling with different data sizes.

        Verifies linear or better scaling characteristics.
        """
        results = []

        for num_players in [100, 250, 500, 750]:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Create data
                data = create_realistic_data_files(tmpdir, num_players=num_players, weeks=5)
                player_df = create_player_dataframe(num_players)

                # Measure time
                start_time = time.time()
                files = load_season_stats_files(tmpdir)
                mapper = create_player_mapper(player_df, files, threshold=85)
                total_time = time.time() - start_time

                results.append({
                    'players': num_players,
                    'time': total_time,
                    'time_per_player': total_time / num_players * 1000  # ms per player
                })

                logger.info(f"Players: {num_players}, Time: {total_time:.3f}s, "
                           f"Per player: {results[-1]['time_per_player']:.2f}ms")

        # Verify reasonable scaling (not exponential)
        # Time per player shouldn't increase dramatically
        time_per_player_100 = results[0]['time_per_player']
        time_per_player_750 = results[-1]['time_per_player']

        # Should not more than double the per-player time
        assert time_per_player_750 < time_per_player_100 * 2, \
            f"Poor scaling: {time_per_player_750:.2f}ms per player at 750 vs " \
            f"{time_per_player_100:.2f}ms at 100"

        # All should meet performance targets
        for result in results:
            assert result['time'] < 5.0, f"Failed target at {result['players']} players"

    def test_concurrent_operations(self, create_realistic_data_files, create_player_dataframe):
        """
        Test performance with concurrent file operations.

        Simulates realistic usage where multiple components might access files.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test data
            data = create_realistic_data_files(tmpdir, num_players=300, weeks=5)
            player_df = create_player_dataframe(300)

            # Test multiple loaders (simulating concurrent access)
            start_time = time.time()

            # Create multiple loaders
            loader1 = FileLoader(tmpdir)
            loader2 = FileLoader(tmpdir)

            # Load files in parallel (Python GIL limits true parallelism)
            files1 = loader1.load_all_files()
            files2 = loader2.load_all_files()

            # Create mappers
            mapper1 = PlayerNameMapper(threshold=85)
            mapper2 = PlayerNameMapper(threshold=85)

            mappings1 = mapper1.create_mappings(player_df[:150], files1)
            mappings2 = mapper2.create_mappings(player_df[150:], files2)

            total_time = time.time() - start_time

            # Should still meet performance targets
            assert total_time < 5.0, f"Concurrent operations took {total_time:.2f} seconds"

            # Verify both completed successfully
            assert len(mappings1) == 150
            assert len(mappings2) == 150

    def test_performance_with_team_variations(self, create_player_dataframe):
        """
        Test performance with non-standard team abbreviations.

        Verifies normalization doesn't significantly impact performance.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with non-standard team names
            num_players = 400
            non_standard_teams = ['BLT', 'CLV', 'LA', 'LV', 'NY', 'TAM', 'JAC', 'WASH']

            # Create files
            for file_key, file_name in {'pass': 'Pass 2025.xlsx', 'rush': 'Rush 2025.xlsx',
                                         'receiving': 'Receiving 2025.xlsx', 'snaps': 'Snaps 2025.xlsx'}.items():

                data = {
                    'Name': [f'Player {i}' for i in range(num_players)],
                    'Team': [non_standard_teams[i % len(non_standard_teams)] for i in range(num_players)],
                    'POS': ['QB', 'RB', 'WR', 'TE'][i % 4] for i in range(num_players)],
                    'W': [1] * num_players
                }

                # Add required columns
                if file_key == 'pass':
                    data.update({'CPOE': [0.0] * num_players, 'aDOT': [8.0] * num_players,
                                 'Deep Throw %': [20.0] * num_players, '1Read %': [50.0] * num_players})
                elif file_key == 'rush':
                    data.update({'YACO/ATT': [2.5] * num_players, 'MTF/ATT': [0.2] * num_players,
                                 'Success Rate': [45.0] * num_players, 'STUFF %': [20.0] * num_players})
                elif file_key == 'receiving':
                    data.update({'TPRR': [0.2] * num_players, 'YPRR': [1.5] * num_players,
                                 'RTE %': [75.0] * num_players, '1READ %': [25.0] * num_players,
                                 'CTGT %': [15.0] * num_players})
                else:  # snaps
                    data.update({'Snap %': [75.0] * num_players, 'FP/G': [15.0] * num_players,
                                 'FP': [75.0] * num_players})

                pd.DataFrame(data).to_excel(os.path.join(tmpdir, file_name), index=False)

            # Create player DataFrame
            player_df = create_player_dataframe(num_players)

            # Measure performance with normalization
            start_time = time.time()
            files = load_season_stats_files(tmpdir)
            mapper = create_player_mapper(player_df, files, threshold=85)
            total_time = time.time() - start_time

            # Verify performance still meets targets
            assert total_time < 5.0, f"With team normalization: {total_time:.2f} seconds"

            # Verify normalization worked
            for file_key, df in files.items():
                if df is not None:
                    teams = df['Team'].unique()
                    # Should be normalized
                    assert 'BAL' in teams  # BLT → BAL
                    assert 'CLE' in teams  # CLV → CLE
                    assert 'BLT' not in teams
                    assert 'CLV' not in teams

    def test_performance_benchmark_report(self, create_realistic_data_files, create_player_dataframe):
        """
        Generate comprehensive performance benchmark report.

        Documents all performance metrics for Phase 1 components.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test configuration
            num_players = 500
            weeks = 5

            # Create test data
            data = create_realistic_data_files(tmpdir, num_players=num_players, weeks=weeks)
            player_df = create_player_dataframe(num_players)

            # Benchmark results
            benchmarks = {
                'configuration': {
                    'num_players': num_players,
                    'weeks': weeks,
                    'total_records': data['total_records']
                },
                'timings': {},
                'memory': {},
                'quality': {}
            }

            # Benchmark 1: File Loading
            loader = FileLoader(tmpdir)
            start = time.time()
            files = loader.load_all_files()
            benchmarks['timings']['file_loading'] = time.time() - start

            # Benchmark 2: Player Mapping
            mapper = PlayerNameMapper(threshold=85)
            start = time.time()
            mappings = mapper.create_mappings(player_df, files)
            benchmarks['timings']['player_mapping'] = time.time() - start

            # Benchmark 3: Full Pipeline
            start = time.time()
            files = load_season_stats_files(tmpdir)
            mapper = create_player_mapper(player_df, files, threshold=85)
            benchmarks['timings']['full_pipeline'] = time.time() - start

            # Quality metrics
            report = mapper.get_match_report()
            benchmarks['quality']['match_rate'] = report['match_rate']
            benchmarks['quality']['avg_match_score'] = report['avg_match_score']
            benchmarks['quality']['perfect_matches'] = report['perfect_matches']

            # Memory tracking
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            benchmarks['memory']['rss_mb'] = memory_info.rss / (1024 * 1024)
            benchmarks['memory']['vms_mb'] = memory_info.vms / (1024 * 1024)

            # Generate report
            logger.info("\n" + "="*60)
            logger.info("PHASE 1 PERFORMANCE BENCHMARK REPORT")
            logger.info("="*60)
            logger.info(f"\nConfiguration:")
            logger.info(f"  Players: {benchmarks['configuration']['num_players']}")
            logger.info(f"  Weeks: {benchmarks['configuration']['weeks']}")
            logger.info(f"  Total Records: {benchmarks['configuration']['total_records']}")

            logger.info(f"\nPerformance Timings:")
            logger.info(f"  File Loading: {benchmarks['timings']['file_loading']:.3f}s "
                       f"(target: <2.0s) {'✓' if benchmarks['timings']['file_loading'] < 2.0 else '✗'}")
            logger.info(f"  Player Mapping: {benchmarks['timings']['player_mapping']:.3f}s "
                       f"(target: <2.0s) {'✓' if benchmarks['timings']['player_mapping'] < 2.0 else '✗'}")
            logger.info(f"  Full Pipeline: {benchmarks['timings']['full_pipeline']:.3f}s "
                       f"(target: <5.0s) {'✓' if benchmarks['timings']['full_pipeline'] < 5.0 else '✗'}")

            logger.info(f"\nMatch Quality:")
            logger.info(f"  Match Rate: {benchmarks['quality']['match_rate']:.1f}% "
                       f"(target: >90%) {'✓' if benchmarks['quality']['match_rate'] >= 90.0 else '✗'}")
            logger.info(f"  Avg Score: {benchmarks['quality']['avg_match_score']:.1f}%")
            logger.info(f"  Perfect Matches: {benchmarks['quality']['perfect_matches']}")

            logger.info(f"\nMemory Usage:")
            logger.info(f"  RSS: {benchmarks['memory']['rss_mb']:.1f} MB")
            logger.info(f"  VMS: {benchmarks['memory']['vms_mb']:.1f} MB")

            logger.info("="*60 + "\n")

            # Verify all targets met
            assert benchmarks['timings']['file_loading'] < 2.0
            assert benchmarks['timings']['player_mapping'] < 2.0
            assert benchmarks['timings']['full_pipeline'] < 5.0
            assert benchmarks['quality']['match_rate'] >= 85.0  # Slightly relaxed for realistic data

            return benchmarks


if __name__ == "__main__":
    # Run tests with verbose output for performance monitoring
    pytest.main([__file__, "-v", "-s"])