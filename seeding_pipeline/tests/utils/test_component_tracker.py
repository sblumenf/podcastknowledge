"""
Unit tests for component tracking system.
"""

import os
import tempfile
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.utils.component_tracker import (
    ComponentTracker,
    ComponentMetrics,
    ComponentContribution,
    ComponentDependency,
    track_component_impact,
    analyze_component_impact,
    compare_component_versions,
    identify_redundancies,
    get_tracker
)


class TestComponentTracker:
    """Test cases for ComponentTracker class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def tracker(self, temp_db):
        """Create a tracker instance with temporary database."""
        return ComponentTracker(storage_path=temp_db)
    
    def test_tracker_initialization(self, tracker):
        """Test tracker initializes correctly."""
        assert tracker.enabled
        assert tracker.storage_path is not None
        assert os.path.exists(tracker.storage_path)
    
    def test_tracker_disabled(self, temp_db):
        """Test tracker behavior when disabled."""
        with patch.dict(os.environ, {'ENABLE_COMPONENT_TRACKING': 'false'}):
            tracker = ComponentTracker(storage_path=temp_db)
            assert not tracker.enabled
            
            # Should not create database when disabled
            metrics = ComponentMetrics(
                component_name="test",
                version="1.0",
                execution_time=1.0,
                memory_usage=None,
                input_size=100,
                output_size=200,
                timestamp=datetime.now().isoformat(),
                episode_id=None,
                segment_id=None,
                success=True
            )
            tracker.track_metrics(metrics)  # Should not raise error
    
    def test_track_metrics(self, tracker):
        """Test tracking component metrics."""
        metrics = ComponentMetrics(
            component_name="test_component",
            version="1.0.0",
            execution_time=1.5,
            memory_usage=1024.0,
            input_size=500,
            output_size=600,
            timestamp=datetime.now().isoformat(),
            episode_id="ep_123",
            segment_id="seg_456",
            success=True
        )
        
        tracker.track_metrics(metrics)
        
        # Verify metrics were stored
        summary = tracker.get_metrics_summary("test_component")
        assert summary['total_executions'] == 1
        assert summary['avg_execution_time'] == 1.5
        assert summary['successful_runs'] == 1
        assert summary['failed_runs'] == 0
        assert summary['success_rate'] == 1.0
    
    def test_track_contribution(self, tracker):
        """Test tracking component contributions."""
        contribution = ComponentContribution(
            component_name="test_component",
            contribution_type="metadata_added",
            details={"fields": ["timestamp", "confidence"]},
            count=2,
            timestamp=datetime.now().isoformat()
        )
        
        tracker.track_contribution(contribution)
        
        # Verify by checking analysis
        impact = analyze_component_impact("test_component")
        assert len(impact['contributions']) > 0
        assert impact['contributions'][0]['type'] == "metadata_added"
        assert impact['contributions'][0]['total_count'] == 2
    
    def test_register_dependency(self, tracker):
        """Test registering component dependencies."""
        dependency = ComponentDependency(
            component_name="quote_extractor",
            depends_on=["segment_preprocessor"],
            required_by=["metadata_enricher"],
            can_disable_if="no quotes needed"
        )
        
        tracker.register_dependency(dependency)
        # Test passes if no exception is raised
    
    def test_tracking_decorator(self, tracker):
        """Test the tracking decorator functionality."""
        # Clear global tracker and set our test tracker
        import src.utils.component_tracker
        src.utils.component_tracker._tracker = tracker
        
        @track_component_impact("test_function", "1.0.0")
        def sample_function(text: str, episode_id: str = None) -> dict:
            return {
                "result": text.upper(),
                "metrics": {
                    "type": "text_transformation",
                    "details": {"transformation": "uppercase"},
                    "count": 1
                }
            }
        
        # Execute the decorated function
        result = sample_function("hello world", episode_id="ep_123")
        
        assert result["result"] == "HELLO WORLD"
        
        # Check metrics were tracked
        summary = tracker.get_metrics_summary("test_function")
        assert summary['total_executions'] == 1
        assert summary['successful_runs'] == 1
        assert summary['success_rate'] == 1.0
    
    def test_tracking_decorator_with_error(self, tracker):
        """Test decorator handles errors correctly."""
        import src.utils.component_tracker
        src.utils.component_tracker._tracker = tracker
        
        @track_component_impact("error_function", "1.0.0")
        def error_function():
            raise ValueError("Test error")
        
        # Execute and expect error
        with pytest.raises(ValueError):
            error_function()
        
        # Check failure was tracked
        summary = tracker.get_metrics_summary("error_function")
        assert summary['total_executions'] == 1
        assert summary['successful_runs'] == 0
        assert summary['failed_runs'] == 1
        assert summary['success_rate'] == 0.0


class TestAnalysisUtilities:
    """Test cases for analysis utility functions."""
    
    @pytest.fixture
    def populated_tracker(self, temp_db):
        """Create a tracker with sample data."""
        tracker = ComponentTracker(storage_path=temp_db)
        
        # Add sample metrics
        for i in range(10):
            metrics = ComponentMetrics(
                component_name="component_a",
                version="1.0.0",
                execution_time=1.0 + i * 0.1,
                memory_usage=None,
                input_size=100,
                output_size=150,
                timestamp=datetime.now().isoformat(),
                episode_id=f"ep_{i}",
                segment_id=None,
                success=True
            )
            tracker.track_metrics(metrics)
        
        # Add some v2 metrics
        for i in range(5):
            metrics = ComponentMetrics(
                component_name="component_a",
                version="2.0.0",
                execution_time=0.8 + i * 0.1,
                memory_usage=None,
                input_size=100,
                output_size=150,
                timestamp=datetime.now().isoformat(),
                episode_id=f"ep_{i}",
                segment_id=None,
                success=True
            )
            tracker.track_metrics(metrics)
        
        # Add contributions
        contribution = ComponentContribution(
            component_name="component_a",
            contribution_type="entities_extracted",
            details={"types": ["Person", "Organization"]},
            count=25,
            timestamp=datetime.now().isoformat()
        )
        tracker.track_contribution(contribution)
        
        return tracker
    
    def test_analyze_component_impact(self, populated_tracker):
        """Test component impact analysis."""
        import src.utils.component_tracker
        src.utils.component_tracker._tracker = populated_tracker
        
        impact = analyze_component_impact("component_a")
        
        assert impact['component_name'] == "component_a"
        assert 'metrics_summary' in impact
        assert impact['metrics_summary']['total_executions'] == 15  # 10 + 5
        assert len(impact['contributions']) > 0
        assert 'recommendation' in impact
    
    def test_compare_versions(self, populated_tracker):
        """Test version comparison functionality."""
        import src.utils.component_tracker
        src.utils.component_tracker._tracker = populated_tracker
        
        comparison = compare_component_versions("component_a", "1.0.0", "2.0.0")
        
        assert 'version_comparison' in comparison
        assert "1.0.0" in comparison['version_comparison']
        assert "2.0.0" in comparison['version_comparison']
        
        # v2 should be faster based on our test data
        v1_time = comparison['version_comparison']["1.0.0"]['avg_execution_time']
        v2_time = comparison['version_comparison']["2.0.0"]['avg_execution_time']
        assert v2_time < v1_time
    
    def test_identify_redundancies(self, temp_db):
        """Test redundancy identification."""
        tracker = ComponentTracker(storage_path=temp_db)
        import src.utils.component_tracker
        src.utils.component_tracker._tracker = tracker
        
        # Add overlapping contributions
        for component in ["comp_1", "comp_2"]:
            contribution = ComponentContribution(
                component_name=component,
                contribution_type="metadata_injection",
                details={},
                count=10,
                timestamp=datetime.now().isoformat()
            )
            tracker.track_contribution(contribution)
        
        redundancies = identify_redundancies()
        
        assert len(redundancies) > 0
        assert redundancies[0]['component1'] == "comp_1"
        assert redundancies[0]['component2'] == "comp_2"
        assert redundancies[0]['shared_contribution'] == "metadata_injection"
        assert redundancies[0]['overlap_ratio'] == 1.0  # Same count


class TestRecommendations:
    """Test recommendation generation logic."""
    
    def test_recommendation_for_slow_component(self):
        """Test recommendation for slow components."""
        from src.utils.component_tracker import _generate_recommendation
        
        summary = {
            'success_rate': 0.95,
            'avg_execution_time': 6.0  # Slow
        }
        contributions = [{'total_count': 100}]
        
        recommendation = _generate_recommendation(summary, contributions)
        assert "slow" in recommendation.lower()
        assert "optimization" in recommendation.lower()
    
    def test_recommendation_for_unreliable_component(self):
        """Test recommendation for unreliable components."""
        from src.utils.component_tracker import _generate_recommendation
        
        summary = {
            'success_rate': 0.8,  # Low success rate
            'avg_execution_time': 1.0
        }
        contributions = [{'total_count': 100}]
        
        recommendation = _generate_recommendation(summary, contributions)
        assert "reliability" in recommendation.lower()
    
    def test_recommendation_for_low_impact_component(self):
        """Test recommendation for low impact components."""
        from src.utils.component_tracker import _generate_recommendation
        
        summary = {
            'success_rate': 1.0,
            'avg_execution_time': 1.0
        }
        contributions = [{'total_count': 5}]  # Low contribution
        
        recommendation = _generate_recommendation(summary, contributions)
        assert "minimal impact" in recommendation.lower()
        assert "removal" in recommendation.lower()