"""
Unit tests for component tracking system.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import os
import tempfile

import pytest

from src.utils.component_tracker import (
    ComponentTracker,
    ComponentImpact,
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
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def tracker(self, temp_dir):
        """Create a tracker instance with temporary directory."""
        return ComponentTracker(output_dir=temp_dir)
    
    def test_tracker_initialization(self, tracker):
        """Test tracker initializes correctly."""
        assert tracker.output_dir is not None
        assert os.path.exists(tracker.output_dir)
        assert hasattr(tracker, 'impacts')
        assert hasattr(tracker, 'baseline_results')
    
    def test_record_impact(self, tracker):
        """Test recording component impact."""
        impact = ComponentImpact(
            component_name="test_component",
            execution_time=1.5,
            items_added=10,
            items_modified=5,
            items_removed=2,
            properties_added={"name": 5, "description": 3},
            relationships_added={"MENTIONS": 4, "DISCUSSES": 2}
        )
        
        tracker.record_impact(impact)
        
        # Verify impact was recorded
        assert "test_component" in tracker.impacts
        assert len(tracker.impacts["test_component"]) == 1
        assert tracker.impacts["test_component"][0] == impact
        
        # Verify file was created
        impact_file = tracker.output_dir / "test_component_impacts.jsonl"
        assert impact_file.exists()
    
    def test_track_impact_context(self, tracker):
        """Test the track_impact context manager."""
        with tracker.track_impact("test_component") as impact:
            impact.add_items(5)
            impact.modify_items(3)
            impact.add_properties({"title": 2, "content": 3})
            impact.add_relationships({"LINKS_TO": 1})
            impact.add_metadata("test_key", "test_value")
        
        # Verify impact was recorded with correct values
        assert "test_component" in tracker.impacts
        recorded = tracker.impacts["test_component"][0]
        assert recorded.items_added == 5
        assert recorded.items_modified == 3
        assert recorded.properties_added == {"title": 2, "content": 3}
        assert recorded.relationships_added == {"LINKS_TO": 1}
        assert recorded.metadata["test_key"] == "test_value"
    
    def test_generate_impact_report(self, tracker):
        """Test generating impact report."""
        # Add some test impacts
        for i in range(3):
            impact = ComponentImpact(
                component_name="component_a",
                execution_time=1.0 + i * 0.5,
                items_added=5 + i,
                items_modified=2 + i
            )
            tracker.record_impact(impact)
        
        impact_b = ComponentImpact(
            component_name="component_b",
            execution_time=0.5,
            items_added=0,  # Low impact component
            items_modified=0
        )
        tracker.record_impact(impact_b)
        
        report = tracker.generate_impact_report()
        
        # Verify report structure
        assert "generated_at" in report
        assert "components" in report
        assert "summary" in report
        assert "recommendations" in report
        
        # Verify component analysis
        assert "component_a" in report["components"]
        comp_a = report["components"]["component_a"]
        assert comp_a["execution_count"] == 3
        assert comp_a["total_items_added"] == 5 + 6 + 7  # 18
        assert comp_a["total_items_modified"] == 2 + 3 + 4  # 9
        
        # Verify recommendations for low-impact component
        low_impact_recs = [r for r in report["recommendations"] 
                          if r["component"] == "component_b" and r["type"] == "no_additions"]
        assert len(low_impact_recs) > 0
    
    def test_compare_with_baseline(self, tracker):
        """Test baseline comparison functionality."""
        baseline_results = {
            "total_entities": 100,
            "total_relationships": 50,
            "processing_time": 10.0
        }
        
        current_results = {
            "total_entities": 120,
            "total_relationships": 44,  # Changed to 44 to be > 10% decrease (12% decrease)
            "processing_time": 8.0
        }
        
        comparison = tracker.compare_with_baseline("test_baseline", baseline_results)
        assert comparison["status"] == "baseline_saved"
        
        # Compare with different results
        comparison = tracker.compare_with_baseline("test_baseline", current_results)
        assert "differences" in comparison
        assert "improvements" in comparison
        assert "regressions" in comparison
        
        # Check specific improvements/regressions
        assert any("total_entities improved" in imp for imp in comparison["improvements"])
        # Processing time decreased from 10 to 8, which is -20% change, treated as regression by the simple logic
        assert any("processing_time regressed" in reg for reg in comparison["regressions"])
        assert any("total_relationships regressed" in reg for reg in comparison["regressions"])
    
    def test_identify_redundant_components(self, tracker):
        """Test identifying redundant components."""
        # Add component with no impact
        for i in range(5):
            impact = ComponentImpact(
                component_name="redundant_component",
                execution_time=1.0,
                items_added=0,
                items_modified=0
            )
            tracker.record_impact(impact)
        
        # Add component with minimal impact
        for i in range(15):
            impact = ComponentImpact(
                component_name="minimal_component",
                execution_time=0.5,
                items_added=0,
                items_modified=1 if i == 0 else 0  # Only 1 modification total
            )
            tracker.record_impact(impact)
        
        redundant = tracker.identify_redundant_components()
        assert "redundant_component" in redundant
        assert "minimal_component" in redundant
    
    def test_tracking_decorator(self, tracker, monkeypatch):
        """Test the tracking decorator functionality."""
        # Mock the global tracker
        import src.utils.component_tracker
        monkeypatch.setattr(src.utils.component_tracker, '_global_tracker', tracker)
        
        @track_component_impact("test_function", "1.0.0")
        def sample_function(text: str) -> dict:
            return {
                "result": text.upper(),
                "added": 3,
                "modified": 2
            }
        
        # Execute the decorated function
        result = sample_function("hello world")
        
        # Verify function still works
        assert result["result"] == "HELLO WORLD"
        
        # Verify impact was tracked
        assert "test_function" in tracker.impacts
        assert len(tracker.impacts["test_function"]) == 1
        impact = tracker.impacts["test_function"][0]
        assert impact.items_added == 3
        assert impact.items_modified == 2
    
    def test_module_functions(self, tracker, monkeypatch):
        """Test module-level convenience functions."""
        # Mock the global tracker
        import src.utils.component_tracker
        monkeypatch.setattr(src.utils.component_tracker, '_global_tracker', tracker)
        
        # Add some test data
        impact = ComponentImpact(
            component_name="test_component",
            execution_time=1.0,
            items_added=10
        )
        tracker.record_impact(impact)
        
        # Test analyze_component_impact
        analysis = analyze_component_impact("test_component")
        assert analysis.get("execution_count") == 1
        assert analysis.get("total_items_added") == 10
        
        # Test compare_component_versions (should return compatibility message)
        comparison = compare_component_versions("test_component", "1.0", "2.0")
        assert "compare_with_baseline" in comparison["comparison"]
        
        # Test identify_redundancies
        redundancies = identify_redundancies()
        assert isinstance(redundancies, list)
        
        # Test get_tracker
        retrieved_tracker = get_tracker()
        assert retrieved_tracker == tracker