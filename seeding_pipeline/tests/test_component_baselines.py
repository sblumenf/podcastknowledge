"""
Baseline comparison tests for component impact analysis.

These tests run the extraction pipeline with different component configurations
to measure the impact of each enhancement.
"""

from pathlib import Path
from typing import Dict, Any, List
import json

import pytest

from src.core.config import PipelineConfig
from src.core.feature_flags import FeatureFlag, set_flag, get_all_flags
from src.pipeline.enhanced_knowledge_pipeline import EnhancedKnowledgePipeline
from src.utils.component_tracker import get_component_tracker
# Test transcript for baseline comparisons
TEST_TRANSCRIPT = """
Host: Welcome to our podcast. I'm John Smith, and today we're talking with 
Dr. Sarah Johnson about artificial intelligence in healthcare.

Dr. Johnson: Thanks for having me, John. I've been working in this field for 
over 20 years, and the progress we've seen is remarkable.

Host: Can you tell us about some specific applications?

Dr. Johnson: Absolutely. One of the most exciting areas is early disease detection. 
We're using machine learning to identify patterns that human doctors might miss. 
As I always say, "AI doesn't replace doctors, it empowers them."

Host: That's a great point. What about concerns regarding patient privacy?

Dr. Johnson: Privacy is paramount. We follow strict HIPAA guidelines and use 
advanced encryption. The key is transparency - patients need to understand 
how their data is being used.

Host: Thank you for those insights. Next week, we'll be talking with 
Professor Michael Chen about quantum computing.
"""


class BaselineTestRunner:
    """Runs baseline tests with different component configurations."""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.results_dir = Path("tests/fixtures/component_baselines")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
    def run_baseline_test(self, test_name: str, flags: Dict[FeatureFlag, bool]) -> Dict[str, Any]:
        """Run a single baseline test with specific flags."""
        # Set flags
        for flag, value in flags.items():
            set_flag(flag, value)
        
        # Get component tracker
        tracker = get_component_tracker()
        
        # Run extraction
        pipeline = EnhancedKnowledgePipeline(self.config)
        pipeline.initialize_components()
        
        # Process test transcript
        result = pipeline.process_text(TEST_TRANSCRIPT, metadata={
            "episode_id": "test_episode",
            "podcast_name": "Test Podcast"
        })
        
        # Get component impact report
        impact_report = tracker.generate_impact_report()
        
        # Save results
        test_result = {
            "test_name": test_name,
            "flags": {flag.value: value for flag, value in flags.items()},
            "extraction_result": result,
            "impact_report": impact_report
        }
        
        # Save to file
        output_path = self.results_dir / f"{test_name}.json"
        with open(output_path, 'w') as f:
            json.dump(test_result, f, indent=2)
        
        return test_result
    
    def run_all_baselines(self) -> List[Dict[str, Any]]:
        """Run all baseline tests."""
        results = []
        
        # Test 1: Raw SimpleKGPipeline (no enhancements)
        results.append(self.run_baseline_test(
            "raw_pipeline",
            {
                FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION: True,
                FeatureFlag.ENABLE_TIMESTAMP_INJECTION: False,
                FeatureFlag.ENABLE_SPEAKER_INJECTION: False,
                FeatureFlag.ENABLE_QUOTE_POSTPROCESSING: False,
                FeatureFlag.ENABLE_METADATA_ENRICHMENT: False,
                FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS: False,
            }
        ))
        
        # Test 2: Only timestamp injection
        results.append(self.run_baseline_test(
            "timestamp_only",
            {
                FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION: True,
                FeatureFlag.ENABLE_TIMESTAMP_INJECTION: True,
                FeatureFlag.ENABLE_SPEAKER_INJECTION: False,
                FeatureFlag.ENABLE_QUOTE_POSTPROCESSING: False,
                FeatureFlag.ENABLE_METADATA_ENRICHMENT: False,
                FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS: False,
            }
        ))
        
        # Test 3: Only speaker injection
        results.append(self.run_baseline_test(
            "speaker_only",
            {
                FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION: True,
                FeatureFlag.ENABLE_TIMESTAMP_INJECTION: False,
                FeatureFlag.ENABLE_SPEAKER_INJECTION: True,
                FeatureFlag.ENABLE_QUOTE_POSTPROCESSING: False,
                FeatureFlag.ENABLE_METADATA_ENRICHMENT: False,
                FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS: False,
            }
        ))
        
        # Test 4: Only quote post-processing
        results.append(self.run_baseline_test(
            "quote_only",
            {
                FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION: True,
                FeatureFlag.ENABLE_TIMESTAMP_INJECTION: False,
                FeatureFlag.ENABLE_SPEAKER_INJECTION: False,
                FeatureFlag.ENABLE_QUOTE_POSTPROCESSING: True,
                FeatureFlag.ENABLE_METADATA_ENRICHMENT: False,
                FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS: False,
            }
        ))
        
        # Test 5: Only metadata enrichment
        results.append(self.run_baseline_test(
            "metadata_only",
            {
                FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION: True,
                FeatureFlag.ENABLE_TIMESTAMP_INJECTION: False,
                FeatureFlag.ENABLE_SPEAKER_INJECTION: False,
                FeatureFlag.ENABLE_QUOTE_POSTPROCESSING: False,
                FeatureFlag.ENABLE_METADATA_ENRICHMENT: True,
                FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS: False,
            }
        ))
        
        # Test 6: Only entity resolution post-processing
        results.append(self.run_baseline_test(
            "entity_resolution_only",
            {
                FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION: True,
                FeatureFlag.ENABLE_TIMESTAMP_INJECTION: False,
                FeatureFlag.ENABLE_SPEAKER_INJECTION: False,
                FeatureFlag.ENABLE_QUOTE_POSTPROCESSING: False,
                FeatureFlag.ENABLE_METADATA_ENRICHMENT: False,
                FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS: True,
            }
        ))
        
        # Test 7: All enhancements enabled
        results.append(self.run_baseline_test(
            "all_enhancements",
            {
                FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION: True,
                FeatureFlag.ENABLE_TIMESTAMP_INJECTION: True,
                FeatureFlag.ENABLE_SPEAKER_INJECTION: True,
                FeatureFlag.ENABLE_QUOTE_POSTPROCESSING: True,
                FeatureFlag.ENABLE_METADATA_ENRICHMENT: True,
                FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS: True,
            }
        ))
        
        return results
    
    def compare_results(self, baseline: str, comparison: str) -> Dict[str, Any]:
        """Compare two baseline results."""
        # Load results
        baseline_path = self.results_dir / f"{baseline}.json"
        comparison_path = self.results_dir / f"{comparison}.json"
        
        with open(baseline_path) as f:
            baseline_data = json.load(f)
        
        with open(comparison_path) as f:
            comparison_data = json.load(f)
        
        # Compare extraction results
        comparison_report = {
            "baseline": baseline,
            "comparison": comparison,
            "differences": {}
        }
        
        # Compare entity counts
        baseline_entities = len(baseline_data.get("extraction_result", {}).get("entities", []))
        comparison_entities = len(comparison_data.get("extraction_result", {}).get("entities", []))
        
        comparison_report["differences"]["entity_count"] = {
            "baseline": baseline_entities,
            "comparison": comparison_entities,
            "change": comparison_entities - baseline_entities
        }
        
        # Compare execution times
        baseline_time = baseline_data.get("impact_report", {}).get("summary", {}).get("total_time", 0)
        comparison_time = comparison_data.get("impact_report", {}).get("summary", {}).get("total_time", 0)
        
        comparison_report["differences"]["execution_time"] = {
            "baseline": baseline_time,
            "comparison": comparison_time,
            "change": comparison_time - baseline_time
        }
        
        return comparison_report


# Test fixtures
@pytest.fixture
def pipeline_config():
    """Create a test pipeline configuration."""
    return PipelineConfig(
        # Use test-specific settings
        checkpoint_dir=Path("test_checkpoints"),
        output_dir=Path("test_output"),
        use_gpu=False,  # Disable GPU for tests
        checkpoint_interval=1
    )

@pytest.fixture
def baseline_runner(pipeline_config):
    """Create a baseline test runner."""
    return BaselineTestRunner(pipeline_config)


# Tests
class TestComponentBaselines:
    """Test component impact through baseline comparisons."""
    
    def test_run_raw_baseline(self, baseline_runner):
        """Test raw pipeline without enhancements."""
        result = baseline_runner.run_baseline_test(
            "raw_pipeline_test",
            {
                FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION: True,
                FeatureFlag.ENABLE_TIMESTAMP_INJECTION: False,
                FeatureFlag.ENABLE_SPEAKER_INJECTION: False,
                FeatureFlag.ENABLE_QUOTE_POSTPROCESSING: False,
                FeatureFlag.ENABLE_METADATA_ENRICHMENT: False,
                FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS: False,
            }
        )
        
        assert result is not None
        assert "impact_report" in result
        assert result["test_name"] == "raw_pipeline_test"
    
    def test_component_impact_tracking(self, baseline_runner):
        """Test that component impacts are properly tracked."""
        # Run with one enhancement
        result = baseline_runner.run_baseline_test(
            "single_enhancement_test",
            {
                FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION: True,
                FeatureFlag.ENABLE_TIMESTAMP_INJECTION: True,
                FeatureFlag.ENABLE_SPEAKER_INJECTION: False,
                FeatureFlag.ENABLE_QUOTE_POSTPROCESSING: False,
                FeatureFlag.ENABLE_METADATA_ENRICHMENT: False,
                FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS: False,
            }
        )
        
        # Check impact report
        impact_report = result.get("impact_report", {})
        components = impact_report.get("components", {})
        
        # Should have tracked at least some components
        assert len(components) > 0, f"Expected components to be tracked, got: {list(components.keys())}"
        
        # Should have tracked knowledge_extractor at minimum
        assert any("knowledge_extractor" in comp.lower() for comp in components)
    
    def test_compare_baselines(self, baseline_runner):
        """Test baseline comparison functionality."""
        # Run two baselines
        baseline_runner.run_baseline_test(
            "baseline_a",
            {
                FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION: True,
                FeatureFlag.ENABLE_TIMESTAMP_INJECTION: False,
                FeatureFlag.ENABLE_SPEAKER_INJECTION: False,
                FeatureFlag.ENABLE_QUOTE_POSTPROCESSING: False,
                FeatureFlag.ENABLE_METADATA_ENRICHMENT: False,
                FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS: False,
            }
        )
        
        baseline_runner.run_baseline_test(
            "baseline_b",
            {
                FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION: True,
                FeatureFlag.ENABLE_TIMESTAMP_INJECTION: True,
                FeatureFlag.ENABLE_SPEAKER_INJECTION: True,
                FeatureFlag.ENABLE_QUOTE_POSTPROCESSING: False,
                FeatureFlag.ENABLE_METADATA_ENRICHMENT: False,
                FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS: False,
            }
        )
        
        # Compare results
        comparison = baseline_runner.compare_results("baseline_a", "baseline_b")
        
        assert "differences" in comparison
        assert "entity_count" in comparison["differences"]
        assert "execution_time" in comparison["differences"]
    
    @pytest.mark.slow
    def test_all_baselines(self, baseline_runner):
        """Test running all baseline configurations."""
        results = baseline_runner.run_all_baselines()
        
        assert len(results) == 7  # 7 different configurations
        
        # Check that each configuration produced different results
        entity_counts = []
        for result in results:
            entities = len(result.get("extraction_result", {}).get("entities", []))
            entity_counts.append(entities)
        
        # Raw pipeline should have fewer entities than full enhancement
        assert entity_counts[0] <= entity_counts[-1]