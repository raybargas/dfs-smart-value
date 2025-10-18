"""
Metric Definitions Module

Centralized configuration for all advanced metrics in the DFS Advanced Stats Migration.
Part of Phase 2: Tier 1 Metrics Implementation (2025-10-18).

This module provides:
- MetricDefinition dataclass for metric metadata
- MetricRegistry class with Tier 1 and Tier 2 metric configurations
- Helper methods for position and file-based metric retrieval

Performance: Lightweight configuration module with <0.01 second access times
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)


class MetricTier(Enum):
    """Metric tier classification for prioritization."""
    TIER_1 = 1  # Highest ROI metrics - immediate implementation
    TIER_2 = 2  # High value metrics - secondary implementation
    TIER_3 = 3  # Nice to have metrics - future consideration


class ScoreComponent(Enum):
    """Smart Value score components that metrics contribute to."""
    OPPORTUNITY = 'OPPORTUNITY'
    BASE = 'BASE'
    LEVERAGE = 'LEVERAGE'
    MATCHUP = 'MATCHUP'
    RISK = 'RISK'


@dataclass
class MetricDefinition:
    """Configuration for an advanced metric.

    Attributes:
        metric_id: Internal identifier (e.g., 'adv_tprr')
        display_name: UI display name (e.g., 'TPRR')
        tooltip: User-facing description
        source_file: Which file contains this metric ('pass', 'rush', 'receiving', 'snaps')
        source_column: Column name in source file
        higher_is_better: Direction indicator for optimization
        tier: Priority level (1=highest, 2=high, 3=nice to have)
        positions: List of applicable positions ['WR', 'TE', etc.]
        score_component: Which Smart Value component this feeds into
        weight_factor: Multiplier when integrating into score (default 1.0)
        data_type: Expected data type (float, int, etc.)
        valid_range: Optional (min, max) validation range
    """
    metric_id: str
    display_name: str
    tooltip: str
    source_file: str
    source_column: str
    higher_is_better: bool
    tier: int
    positions: List[str]
    score_component: str
    weight_factor: float = 1.0
    data_type: type = float
    valid_range: Optional[Tuple[float, float]] = None

    def validate_value(self, value: any) -> bool:
        """Validate that a value is within expected range.

        Args:
            value: Value to validate

        Returns:
            True if valid, False otherwise
        """
        if value is None:
            return True  # None is valid (missing data)

        # Type check
        try:
            typed_value = self.data_type(value)
        except (ValueError, TypeError):
            return False

        # Range check
        if self.valid_range:
            min_val, max_val = self.valid_range
            return min_val <= typed_value <= max_val

        return True

    def normalize_value(self, value: any) -> Optional[float]:
        """Normalize value to 0-1 scale based on valid range.

        Args:
            value: Raw value to normalize

        Returns:
            Normalized value [0, 1] or None if invalid
        """
        if not self.validate_value(value):
            return None

        if value is None:
            return None

        typed_value = self.data_type(value)

        if self.valid_range:
            min_val, max_val = self.valid_range
            if max_val > min_val:
                normalized = (typed_value - min_val) / (max_val - min_val)
                return max(0.0, min(1.0, normalized))  # Clamp to [0, 1]

        # If no range, can't normalize
        return typed_value


class MetricRegistry:
    """Central registry for all advanced metric definitions.

    This class contains all metric configurations organized by tier,
    with helper methods for retrieving metrics by various criteria.
    """

    # ============================
    # TIER 1 METRICS (Highest ROI)
    # ============================

    TIER_1_METRICS = {
        'adv_tprr': MetricDefinition(
            metric_id='adv_tprr',
            display_name='TPRR',
            tooltip='Targets Per Route Run - measures true target share independent of snap count',
            source_file='receiving',
            source_column='TPRR',
            higher_is_better=True,
            tier=1,
            positions=['WR', 'TE'],
            score_component='OPPORTUNITY',
            weight_factor=1.0,
            data_type=float,
            valid_range=(0.0, 1.0)
        ),
        'adv_yprr': MetricDefinition(
            metric_id='adv_yprr',
            display_name='YPRR',
            tooltip='Yards Per Route Run - efficiency metric that accounts for snap quality',
            source_file='receiving',
            source_column='YPRR',
            higher_is_better=True,
            tier=1,
            positions=['WR', 'TE'],
            score_component='OPPORTUNITY',
            weight_factor=1.0,
            data_type=float,
            valid_range=(0.0, 10.0)
        ),
        'adv_rte_pct': MetricDefinition(
            metric_id='adv_rte_pct',
            display_name='RTE%',
            tooltip='Route Participation % - percentage of pass plays where player ran a route',
            source_file='receiving',
            source_column='RTE %',
            higher_is_better=True,
            tier=1,
            positions=['WR', 'TE'],
            score_component='OPPORTUNITY',
            weight_factor=1.0,
            data_type=float,
            valid_range=(0.0, 100.0)
        ),
        'adv_yaco_att': MetricDefinition(
            metric_id='adv_yaco_att',
            display_name='YACO/ATT',
            tooltip='Yards After Contact per Attempt - measures RB elusiveness independent of O-line',
            source_file='rush',
            source_column='YACO/ATT',
            higher_is_better=True,
            tier=1,
            positions=['RB'],
            score_component='BASE',
            weight_factor=1.0,
            data_type=float,
            valid_range=(0.0, 10.0)
        ),
        'adv_success_rate': MetricDefinition(
            metric_id='adv_success_rate',
            display_name='Success Rate',
            tooltip='Rushing Success Rate - percentage of runs gaining expected yards (floor metric)',
            source_file='rush',
            source_column='Success Rate',
            higher_is_better=True,
            tier=1,
            positions=['RB'],
            score_component='RISK',
            weight_factor=1.0,
            data_type=float,
            valid_range=(0.0, 100.0)
        ),
    }

    # ============================
    # TIER 2 METRICS (High Value)
    # ============================

    TIER_2_METRICS = {
        'adv_cpoe': MetricDefinition(
            metric_id='adv_cpoe',
            display_name='CPOE',
            tooltip='Completion % Over Expected - measures QB accuracy vs difficulty',
            source_file='pass',
            source_column='CPOE',
            higher_is_better=True,
            tier=2,
            positions=['QB'],
            score_component='BASE',
            weight_factor=1.0,
            data_type=float,
            valid_range=(-20.0, 20.0)
        ),
        'adv_adot': MetricDefinition(
            metric_id='adv_adot',
            display_name='aDOT',
            tooltip='Average Depth of Target - indicates game script and ceiling potential',
            source_file='pass',
            source_column='aDOT',
            higher_is_better=True,
            tier=2,
            positions=['QB'],
            score_component='MATCHUP',
            weight_factor=1.0,
            data_type=float,
            valid_range=(0.0, 20.0)
        ),
        'adv_deep_throw_pct': MetricDefinition(
            metric_id='adv_deep_throw_pct',
            display_name='Deep Throw%',
            tooltip='Deep Throw % - percentage of throws >20 yards downfield (boom potential)',
            source_file='pass',
            source_column='Deep Throw %',
            higher_is_better=True,
            tier=2,
            positions=['QB'],
            score_component='LEVERAGE',
            weight_factor=1.0,
            data_type=float,
            valid_range=(0.0, 50.0)
        ),
        'adv_1read_pct': MetricDefinition(
            metric_id='adv_1read_pct',
            display_name='1Read%',
            tooltip='First Read % - measures designed targets and QB trust',
            source_file='receiving',  # Also in 'pass' for QBs
            source_column='1READ %',
            higher_is_better=True,
            tier=2,
            positions=['WR', 'TE', 'RB', 'QB'],
            score_component='OPPORTUNITY',
            weight_factor=1.0,
            data_type=float,
            valid_range=(0.0, 100.0)
        ),
        'adv_mtf_att': MetricDefinition(
            metric_id='adv_mtf_att',
            display_name='MTF/ATT',
            tooltip='Missed Tackles Forced per Attempt - breakaway ability and ceiling indicator',
            source_file='rush',
            source_column='MTF/ATT',
            higher_is_better=True,
            tier=2,
            positions=['RB'],
            score_component='LEVERAGE',
            weight_factor=1.0,
            data_type=float,
            valid_range=(0.0, 1.0)
        ),
    }

    # ============================
    # TIER 3 METRICS (Nice to Have)
    # ============================
    # Future expansion - not implemented in Phase 2/3

    TIER_3_METRICS = {}

    @classmethod
    def get_all_metrics(cls) -> Dict[str, MetricDefinition]:
        """Get all metric definitions across all tiers.

        Returns:
            Dictionary mapping metric_id to MetricDefinition
        """
        all_metrics = {}
        all_metrics.update(cls.TIER_1_METRICS)
        all_metrics.update(cls.TIER_2_METRICS)
        all_metrics.update(cls.TIER_3_METRICS)
        return all_metrics

    @classmethod
    def get_metrics_for_position(cls, position: str) -> List[MetricDefinition]:
        """Get all applicable metrics for a specific position.

        Args:
            position: Player position (e.g., 'QB', 'RB', 'WR', 'TE')

        Returns:
            List of MetricDefinition objects applicable to this position
        """
        all_metrics = cls.get_all_metrics()
        position_metrics = []

        for metric in all_metrics.values():
            if position in metric.positions:
                position_metrics.append(metric)

        # Sort by tier (1 first) then by metric_id for consistency
        position_metrics.sort(key=lambda m: (m.tier, m.metric_id))

        return position_metrics

    @classmethod
    def get_metrics_for_file(cls, file_key: str) -> List[MetricDefinition]:
        """Get all metrics that come from a specific source file.

        Args:
            file_key: Source file identifier ('pass', 'rush', 'receiving', 'snaps')

        Returns:
            List of MetricDefinition objects from this file
        """
        all_metrics = cls.get_all_metrics()
        file_metrics = []

        for metric in all_metrics.values():
            if metric.source_file == file_key:
                file_metrics.append(metric)

        # Sort by tier (1 first) then by metric_id
        file_metrics.sort(key=lambda m: (m.tier, m.metric_id))

        return file_metrics

    @classmethod
    def get_metrics_by_tier(cls, tier: int) -> Dict[str, MetricDefinition]:
        """Get all metrics of a specific tier.

        Args:
            tier: Tier level (1, 2, or 3)

        Returns:
            Dictionary mapping metric_id to MetricDefinition for specified tier
        """
        if tier == 1:
            return cls.TIER_1_METRICS.copy()
        elif tier == 2:
            return cls.TIER_2_METRICS.copy()
        elif tier == 3:
            return cls.TIER_3_METRICS.copy()
        else:
            logger.warning(f"Invalid tier {tier} requested. Returning empty dict.")
            return {}

    @classmethod
    def get_metrics_by_component(cls, component: str) -> List[MetricDefinition]:
        """Get all metrics that contribute to a specific score component.

        Args:
            component: Score component name ('OPPORTUNITY', 'BASE', 'LEVERAGE', etc.)

        Returns:
            List of MetricDefinition objects for this component
        """
        all_metrics = cls.get_all_metrics()
        component_metrics = []

        for metric in all_metrics.values():
            if metric.score_component == component:
                component_metrics.append(metric)

        # Sort by tier then metric_id
        component_metrics.sort(key=lambda m: (m.tier, m.metric_id))

        return component_metrics

    @classmethod
    def validate_metric_data(cls, metric_id: str, value: any) -> Tuple[bool, Optional[str]]:
        """Validate a value for a specific metric.

        Args:
            metric_id: Metric identifier
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        all_metrics = cls.get_all_metrics()

        if metric_id not in all_metrics:
            return False, f"Unknown metric: {metric_id}"

        metric = all_metrics[metric_id]

        if not metric.validate_value(value):
            return False, f"Invalid value for {metric.display_name}: {value}"

        return True, None

    @classmethod
    def get_metric_summary(cls) -> Dict[str, Dict]:
        """Get summary statistics about registered metrics.

        Returns:
            Dictionary with counts by tier, position, file, and component
        """
        all_metrics = cls.get_all_metrics()

        summary = {
            'total_metrics': len(all_metrics),
            'by_tier': {
                'tier_1': len(cls.TIER_1_METRICS),
                'tier_2': len(cls.TIER_2_METRICS),
                'tier_3': len(cls.TIER_3_METRICS)
            },
            'by_file': {},
            'by_position': {},
            'by_component': {}
        }

        # Count by file
        for file_key in ['pass', 'rush', 'receiving', 'snaps']:
            summary['by_file'][file_key] = len(cls.get_metrics_for_file(file_key))

        # Count by position
        for position in ['QB', 'RB', 'WR', 'TE']:
            summary['by_position'][position] = len(cls.get_metrics_for_position(position))

        # Count by component
        for component in ['OPPORTUNITY', 'BASE', 'LEVERAGE', 'MATCHUP', 'RISK']:
            summary['by_component'][component] = len(cls.get_metrics_by_component(component))

        return summary


# ================================
# Unit Tests (inline for simplicity)
# ================================

def test_metric_registry():
    """Test MetricRegistry functionality."""

    # Test 1: Get all metrics
    all_metrics = MetricRegistry.get_all_metrics()
    assert len(all_metrics) == 10, f"Expected 10 metrics, got {len(all_metrics)}"

    # Test 2: Get metrics for WR position
    wr_metrics = MetricRegistry.get_metrics_for_position('WR')
    wr_metric_ids = [m.metric_id for m in wr_metrics]
    assert 'adv_tprr' in wr_metric_ids, "TPRR should be available for WR"
    assert 'adv_yprr' in wr_metric_ids, "YPRR should be available for WR"
    assert 'adv_yaco_att' not in wr_metric_ids, "YACO/ATT should NOT be available for WR"

    # Test 3: Get metrics for RB position
    rb_metrics = MetricRegistry.get_metrics_for_position('RB')
    rb_metric_ids = [m.metric_id for m in rb_metrics]
    assert 'adv_yaco_att' in rb_metric_ids, "YACO/ATT should be available for RB"
    assert 'adv_success_rate' in rb_metric_ids, "Success Rate should be available for RB"
    assert 'adv_tprr' not in rb_metric_ids, "TPRR should NOT be available for RB"

    # Test 4: Get metrics from receiving file
    receiving_metrics = MetricRegistry.get_metrics_for_file('receiving')
    receiving_ids = [m.metric_id for m in receiving_metrics]
    assert 'adv_tprr' in receiving_ids, "TPRR should be in receiving file"
    assert 'adv_yprr' in receiving_ids, "YPRR should be in receiving file"
    assert 'adv_rte_pct' in receiving_ids, "RTE% should be in receiving file"

    # Test 5: Get Tier 1 metrics
    tier1_metrics = MetricRegistry.get_metrics_by_tier(1)
    assert len(tier1_metrics) == 5, f"Expected 5 Tier 1 metrics, got {len(tier1_metrics)}"

    # Test 6: Get metrics by component
    opp_metrics = MetricRegistry.get_metrics_by_component('OPPORTUNITY')
    opp_ids = [m.metric_id for m in opp_metrics]
    assert 'adv_tprr' in opp_ids, "TPRR should contribute to OPPORTUNITY"

    # Test 7: Validate metric values
    is_valid, error = MetricRegistry.validate_metric_data('adv_tprr', 0.25)
    assert is_valid, f"0.25 should be valid for TPRR: {error}"

    is_valid, error = MetricRegistry.validate_metric_data('adv_tprr', 1.5)
    assert not is_valid, "1.5 should be invalid for TPRR (out of range)"

    # Test 8: Value normalization
    tprr_metric = MetricRegistry.TIER_1_METRICS['adv_tprr']
    normalized = tprr_metric.normalize_value(0.5)
    assert normalized == 0.5, f"0.5 TPRR should normalize to 0.5, got {normalized}"

    # Test 9: Get metric summary
    summary = MetricRegistry.get_metric_summary()
    assert summary['total_metrics'] == 10
    assert summary['by_tier']['tier_1'] == 5
    assert summary['by_tier']['tier_2'] == 5

    print("✅ All MetricRegistry tests passed!")
    return True


# Run tests if module is executed directly
if __name__ == '__main__':
    test_metric_registry()

    # Print metric summary for verification
    print("\nMetric Registry Summary:")
    print("=" * 40)
    summary = MetricRegistry.get_metric_summary()
    for key, value in summary.items():
        if isinstance(value, dict):
            print(f"{key}:")
            for sub_key, sub_value in value.items():
                print(f"  {sub_key}: {sub_value}")
        else:
            print(f"{key}: {value}")