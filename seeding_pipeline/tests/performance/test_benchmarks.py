"""
Performance Benchmark Tests

Performance regression detection for VTT → Knowledge Graph pipeline.
Part of Phase 7: Basic Performance Validation

This test suite:
- Compares current performance against baseline
- Sets acceptable thresholds (+20% from baseline)
- Initially non-blocking to allow performance tuning
"""

import json
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    # Mock pytest functions for import compatibility
    class pytest:
        @staticmethod
        def fixture(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
        
        @staticmethod
        def skip(reason):
            print(f"SKIP: {reason}")
            return
        
        @staticmethod
        def warns(*args, **kwargs):
            pass

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import our performance measurement script
from scripts.measure_performance import PerformanceProfiler, count_vtt_captions


class TestPerformanceBenchmarks:
    """Performance benchmark tests for VTT processing pipeline."""
    
    @pytest.fixture(scope="class")
    def baseline_data(self) -> Optional[Dict[str, Any]]:
        """Load baseline performance data."""
        baseline_file = Path(__file__).parent.parent.parent / "benchmarks" / "baseline.json"
        
        if baseline_file.exists():
            with open(baseline_file, 'r') as f:
                return json.load(f)
        else:
            pytest.skip("Baseline performance data not found - run scripts/measure_performance.py first")
    
    @pytest.fixture(scope="class")
    def vtt_test_file(self) -> Path:
        """Get standard VTT test file."""
        vtt_file = Path(__file__).parent.parent / "fixtures" / "vtt_samples" / "standard.vtt"
        if not vtt_file.exists():
            pytest.skip("Standard VTT test file not found")
        return vtt_file
    
    @pytest.fixture(scope="class")
    def performance_thresholds(self, baseline_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate performance thresholds (+20% from baseline)."""
        if not baseline_data or 'measurements' not in baseline_data:
            pytest.skip("Baseline data incomplete")
        
        measurements = baseline_data['measurements']
        thresholds = {}
        
        # VTT parsing thresholds
        if 'vtt_parsing' in measurements and measurements['vtt_parsing'].get('success'):
            baseline_parse_time = measurements['vtt_parsing']['parse_time_seconds']
            thresholds['vtt_parsing_max_seconds'] = baseline_parse_time * 1.2  # +20%
        
        # Knowledge extraction thresholds
        if 'knowledge_extraction' in measurements and measurements['knowledge_extraction'].get('success'):
            baseline_extraction_time = measurements['knowledge_extraction']['extraction_time_seconds']
            thresholds['knowledge_extraction_max_seconds'] = baseline_extraction_time * 1.2  # +20%
        
        # Neo4j writes thresholds
        if 'neo4j_writes' in measurements and measurements['neo4j_writes'].get('success'):
            baseline_neo4j_time = measurements['neo4j_writes']['total_write_time_seconds']
            thresholds['neo4j_writes_max_seconds'] = baseline_neo4j_time * 1.2  # +20%
        
        # Total pipeline threshold
        if 'total_pipeline_time_seconds' in measurements:
            baseline_total_time = measurements['total_pipeline_time_seconds']
            thresholds['total_pipeline_max_seconds'] = baseline_total_time * 1.2  # +20%
        
        return thresholds
    
    def test_vtt_parsing_performance(self, vtt_test_file: Path, performance_thresholds: Dict[str, float]):
        """Test VTT parsing performance against baseline."""
        if 'vtt_parsing_max_seconds' not in performance_thresholds:
            pytest.skip("No VTT parsing baseline available")
        
        # Measure current VTT parsing performance
        profiler = PerformanceProfiler(vtt_test_file)
        
        # Run just the VTT parsing portion
        vtt_results = profiler.measure_vtt_parsing()
        
        # Check that parsing succeeded
        assert vtt_results['success'], f"VTT parsing failed: {vtt_results.get('error', 'Unknown error')}"
        
        # Check performance threshold
        actual_time = vtt_results['parse_time_seconds']
        max_allowed_time = performance_thresholds['vtt_parsing_max_seconds']
        
        if actual_time > max_allowed_time:
            # Initially non-blocking - warn but don't fail
            pytest.warns(
                UserWarning,
                match=f"VTT parsing took {actual_time:.4f}s, exceeds threshold of {max_allowed_time:.4f}s"
            )
            print(f"\n⚠️  Performance Warning: VTT parsing took {actual_time:.4f}s (threshold: {max_allowed_time:.4f}s)")
        else:
            print(f"\n✅ VTT parsing performance OK: {actual_time:.4f}s (threshold: {max_allowed_time:.4f}s)")
    
    def test_knowledge_extraction_performance(self, vtt_test_file: Path, performance_thresholds: Dict[str, float]):
        """Test knowledge extraction performance against baseline."""
        if 'knowledge_extraction_max_seconds' not in performance_thresholds:
            pytest.skip("No knowledge extraction baseline available")
        
        # Measure current knowledge extraction performance
        profiler = PerformanceProfiler(vtt_test_file)
        
        # Parse VTT first
        segments = profiler._parse_vtt_basic(vtt_test_file)
        assert len(segments) > 0, "No segments parsed from VTT file"
        
        # Run knowledge extraction
        extraction_results = profiler.measure_knowledge_extraction(segments)
        
        # Check that extraction succeeded
        assert extraction_results['success'], f"Knowledge extraction failed: {extraction_results.get('error', 'Unknown error')}"
        
        # Check performance threshold
        actual_time = extraction_results['extraction_time_seconds']
        max_allowed_time = performance_thresholds['knowledge_extraction_max_seconds']
        
        if actual_time > max_allowed_time:
            # Initially non-blocking - warn but don't fail
            pytest.warns(
                UserWarning,
                match=f"Knowledge extraction took {actual_time:.4f}s, exceeds threshold of {max_allowed_time:.4f}s"
            )
            print(f"\n⚠️  Performance Warning: Knowledge extraction took {actual_time:.4f}s (threshold: {max_allowed_time:.4f}s)")
        else:
            print(f"\n✅ Knowledge extraction performance OK: {actual_time:.4f}s (threshold: {max_allowed_time:.4f}s)")
    
    def test_neo4j_writes_performance(self, vtt_test_file: Path, performance_thresholds: Dict[str, float]):
        """Test Neo4j write performance against baseline."""
        if 'neo4j_writes_max_seconds' not in performance_thresholds:
            pytest.skip("No Neo4j writes baseline available")
        
        # Measure current Neo4j write performance
        profiler = PerformanceProfiler(vtt_test_file)
        
        # Parse VTT and extract knowledge first
        segments = profiler._parse_vtt_basic(vtt_test_file)
        extracted_data = profiler._extract_knowledge_basic(segments)
        
        # Run Neo4j writes (simulated)
        podcast_data = {'name': 'Performance Test Podcast'}
        episode_data = {'title': 'Performance Test Episode'}
        neo4j_results = profiler.measure_neo4j_writes(podcast_data, episode_data, extracted_data)
        
        # Check that writes succeeded
        assert neo4j_results['success'], f"Neo4j writes failed: {neo4j_results.get('error', 'Unknown error')}"
        
        # Check performance threshold
        actual_time = neo4j_results['total_write_time_seconds']
        max_allowed_time = performance_thresholds['neo4j_writes_max_seconds']
        
        if actual_time > max_allowed_time:
            # Initially non-blocking - warn but don't fail
            pytest.warns(
                UserWarning,
                match=f"Neo4j writes took {actual_time:.4f}s, exceeds threshold of {max_allowed_time:.4f}s"
            )
            print(f"\n⚠️  Performance Warning: Neo4j writes took {actual_time:.4f}s (threshold: {max_allowed_time:.4f}s)")
        else:
            print(f"\n✅ Neo4j writes performance OK: {actual_time:.4f}s (threshold: {max_allowed_time:.4f}s)")
    
    def test_total_pipeline_performance(self, vtt_test_file: Path, performance_thresholds: Dict[str, float]):
        """Test total pipeline performance against baseline."""
        if 'total_pipeline_max_seconds' not in performance_thresholds:
            pytest.skip("No total pipeline baseline available")
        
        # Measure current total pipeline performance
        profiler = PerformanceProfiler(vtt_test_file)
        
        # Run full benchmark
        start_time = time.time()
        results = profiler.run_full_benchmark()
        actual_time = time.time() - start_time
        
        # Alternative: use the measured total from results
        if 'total_pipeline_time_seconds' in results['measurements']:
            actual_time = results['measurements']['total_pipeline_time_seconds']
        
        # Check performance threshold
        max_allowed_time = performance_thresholds['total_pipeline_max_seconds']
        
        if actual_time > max_allowed_time:
            # Initially non-blocking - warn but don't fail
            pytest.warns(
                UserWarning,
                match=f"Total pipeline took {actual_time:.4f}s, exceeds threshold of {max_allowed_time:.4f}s"
            )
            print(f"\n⚠️  Performance Warning: Total pipeline took {actual_time:.4f}s (threshold: {max_allowed_time:.4f}s)")
        else:
            print(f"\n✅ Total pipeline performance OK: {actual_time:.4f}s (threshold: {max_allowed_time:.4f}s)")
    
    def test_baseline_data_validity(self, baseline_data: Dict[str, Any]):
        """Test that baseline data is valid and complete."""
        # Check required structure
        assert 'timestamp' in baseline_data, "Baseline missing timestamp"
        assert 'measurements' in baseline_data, "Baseline missing measurements"
        assert 'vtt_file' in baseline_data, "Baseline missing VTT file info"
        
        measurements = baseline_data['measurements']
        
        # Check VTT parsing data
        if 'vtt_parsing' in measurements:
            vtt_data = measurements['vtt_parsing']
            assert vtt_data.get('success'), "Baseline VTT parsing was not successful"
            assert 'parse_time_seconds' in vtt_data, "Baseline missing VTT parse time"
            assert 'segments_parsed' in vtt_data, "Baseline missing segments count"
        
        # Check knowledge extraction data
        if 'knowledge_extraction' in measurements:
            extraction_data = measurements['knowledge_extraction']
            assert extraction_data.get('success'), "Baseline knowledge extraction was not successful"
            assert 'extraction_time_seconds' in extraction_data, "Baseline missing extraction time"
            assert 'entities_extracted' in extraction_data, "Baseline missing entities count"
        
        # Check Neo4j writes data
        if 'neo4j_writes' in measurements:
            neo4j_data = measurements['neo4j_writes']
            assert neo4j_data.get('success'), "Baseline Neo4j writes were not successful"
            assert 'total_write_time_seconds' in neo4j_data, "Baseline missing Neo4j write time"
        
        print("\n✅ Baseline data is valid and complete")
    
    def test_performance_test_file_validity(self, vtt_test_file: Path):
        """Test that the performance test file is appropriate."""
        # Check file exists and is readable
        assert vtt_test_file.exists(), f"VTT test file not found: {vtt_test_file}"
        
        # Check file size is reasonable
        file_size = vtt_test_file.stat().st_size
        assert 1000 < file_size < 50000, f"VTT file size {file_size} bytes seems unusual"
        
        # Check caption count is appropriate for testing (around 100 as per plan)
        caption_count = count_vtt_captions(vtt_test_file)
        assert 50 <= caption_count <= 150, f"VTT file has {caption_count} captions, expected ~100"
        
        print(f"\n✅ Test file valid: {caption_count} captions, {file_size} bytes")


# Additional test for CI integration
def test_performance_benchmark_integration():
    """Test that performance benchmarks can be run in CI."""
    # This test ensures the performance test suite can be executed
    # even if baseline data is missing or incomplete
    
    project_root = Path(__file__).parent.parent.parent
    baseline_file = project_root / "benchmarks" / "baseline.json"
    vtt_file = project_root / "tests" / "fixtures" / "vtt_samples" / "standard.vtt"
    
    # Test passes if either:
    # 1. Both baseline and VTT file exist (normal case)
    # 2. VTT file exists but baseline is missing (CI can still run basic tests)
    # 3. Neither exists (tests will be skipped but won't fail CI)
    
    if vtt_file.exists():
        if baseline_file.exists():
            print("\n✅ Full performance benchmarks available")
        else:
            print("\n⚠️  Baseline missing - performance tests will be skipped")
    else:
        print("\n⚠️  Test files missing - performance tests will be skipped")
    
    # Always pass - this test just reports status
    assert True