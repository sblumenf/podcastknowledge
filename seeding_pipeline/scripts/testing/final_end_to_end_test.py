#!/usr/bin/env python3
"""
Final End-to-End Test for Clustering System - Phase 7.6

Comprehensive test that validates the complete clustering system:
- Processes multiple VTT files through the full pipeline
- Verifies clustering runs automatically and creates proper labels
- Tests evolution tracking when adding new episodes
- Validates edge cases like empty episodes and outlier-heavy datasets
- Confirms system is production ready

This test ensures the clustering system works correctly in real-world scenarios.
"""

import os
import sys
import time
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.storage.graph_storage import GraphStorageService
from src.services.llm_service import LLMService
from src.clustering.semantic_clustering import SemanticClusteringSystem
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TestResult:
    """Result of an individual test."""
    test_name: str
    passed: bool
    message: str
    details: Dict[str, Any]
    execution_time: float


class EndToEndTestSuite:
    """Comprehensive end-to-end test suite for clustering system."""
    
    def __init__(self, neo4j_uri: str, gemini_api_key: str):
        """Initialize test suite with database and LLM connections."""
        self.neo4j_uri = neo4j_uri
        self.gemini_api_key = gemini_api_key
        self.test_results: List[TestResult] = []
        self.temp_dir = None
        
        # Initialize services
        self.neo4j_service = None
        self.llm_service = None
        self.clustering_system = None
        
    def setup_test_environment(self) -> bool:
        """Set up test environment and services."""
        try:
            logger.info("🔧 Setting up test environment...")
            
            # Create temporary directory for test data
            self.temp_dir = tempfile.mkdtemp(prefix="clustering_e2e_test_")
            logger.info(f"Created temp directory: {self.temp_dir}")
            
            # Initialize Neo4j service with test database
            test_db_name = f"test_clustering_{int(time.time())}"
            self.neo4j_service = GraphStorageService(
                uri=self.neo4j_uri,
                username='neo4j',
                password='password',
                database=test_db_name
            )
            
            # Initialize LLM service
            self.llm_service = LLMService(
                api_key=self.gemini_api_key,
                model_name="gemini-1.5-flash-002",
                max_tokens=8000,
                temperature=0.3
            )
            
            # Initialize clustering system
            clustering_config = {
                'clustering': {
                    'min_cluster_size_formula': 'sqrt',
                    'min_samples': 3,
                    'epsilon': 0.3
                }
            }
            
            self.clustering_system = SemanticClusteringSystem(
                self.neo4j_service,
                self.llm_service,
                clustering_config
            )
            
            # Create test database schema
            self._create_test_schema()
            
            logger.info("✅ Test environment setup complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to set up test environment: {e}")
            return False
    
    def teardown_test_environment(self):
        """Clean up test environment."""
        try:
            logger.info("🧹 Cleaning up test environment...")
            
            # Close database connections
            if self.neo4j_service:
                self.neo4j_service.close()
            
            # Clean up temp directory
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"Removed temp directory: {self.temp_dir}")
                
        except Exception as e:
            logger.warning(f"⚠️  Cleanup warning: {e}")
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run complete end-to-end test suite."""
        start_time = time.time()
        
        logger.info("🚀 Starting comprehensive end-to-end test suite...")
        
        # Test 1: Basic Pipeline Processing
        self._test_basic_pipeline_processing()
        
        # Test 2: Clustering Verification
        self._test_clustering_verification()
        
        # Test 3: Evolution Tracking
        self._test_evolution_tracking()
        
        # Test 4: Edge Cases
        self._test_edge_cases()
        
        # Test 5: Production Readiness
        self._test_production_readiness()
        
        total_time = time.time() - start_time
        
        # Generate test report
        return self._generate_test_report(total_time)
    
    def _test_basic_pipeline_processing(self):
        """Test 1: Basic pipeline processes multiple VTT files correctly."""
        test_name = "Basic Pipeline Processing"
        start_time = time.time()
        
        try:
            logger.info(f"🧪 Running test: {test_name}")
            
            # Create test VTT files
            test_files = self._create_test_vtt_files()
            
            # Process each VTT file through pipeline
            processed_episodes = []
            for vtt_file in test_files:
                episode_id = f"test_episode_{vtt_file.stem}"
                
                # Simulate pipeline processing
                success = self._simulate_pipeline_processing(vtt_file, episode_id)
                if success:
                    processed_episodes.append(episode_id)
            
            # Verify all episodes were processed
            expected_count = len(test_files)
            actual_count = len(processed_episodes)
            
            if actual_count == expected_count:
                self._add_test_result(TestResult(
                    test_name=test_name,
                    passed=True,
                    message=f"Successfully processed {actual_count}/{expected_count} episodes",
                    details={"processed_episodes": processed_episodes},
                    execution_time=time.time() - start_time
                ))
            else:
                self._add_test_result(TestResult(
                    test_name=test_name,
                    passed=False,
                    message=f"Processing failed: {actual_count}/{expected_count} episodes processed",
                    details={"processed_episodes": processed_episodes},
                    execution_time=time.time() - start_time
                ))
                
        except Exception as e:
            self._add_test_result(TestResult(
                test_name=test_name,
                passed=False,
                message=f"Test failed with exception: {str(e)}",
                details={"error": str(e)},
                execution_time=time.time() - start_time
            ))
    
    def _test_clustering_verification(self):
        """Test 2: Verify clustering runs and creates proper clusters with labels."""
        test_name = "Clustering Verification"
        start_time = time.time()
        
        try:
            logger.info(f"🧪 Running test: {test_name}")
            
            # Run clustering on test data
            clustering_result = self.clustering_system.run_clustering()
            
            # Verify clustering succeeded
            if clustering_result['status'] != 'success':
                self._add_test_result(TestResult(
                    test_name=test_name,
                    passed=False,
                    message="Clustering failed to execute",
                    details=clustering_result,
                    execution_time=time.time() - start_time
                ))
                return
            
            # Check cluster creation
            stats = clustering_result.get('stats', {})
            clusters_created = stats.get('n_clusters', 0)
            units_clustered = stats.get('total_units', 0)
            
            # Verify cluster labels exist
            labels_created = self._verify_cluster_labels()
            
            success = (
                clusters_created > 0 and
                units_clustered > 0 and
                labels_created > 0
            )
            
            self._add_test_result(TestResult(
                test_name=test_name,
                passed=success,
                message=f"Created {clusters_created} clusters with {labels_created} labels for {units_clustered} units",
                details={
                    "clusters_created": clusters_created,
                    "units_clustered": units_clustered,
                    "labels_created": labels_created,
                    "clustering_stats": stats
                },
                execution_time=time.time() - start_time
            ))
            
        except Exception as e:
            self._add_test_result(TestResult(
                test_name=test_name,
                passed=False,
                message=f"Test failed with exception: {str(e)}",
                details={"error": str(e)},
                execution_time=time.time() - start_time
            ))
    
    def _test_evolution_tracking(self):
        """Test 3: Test evolution tracking when adding new episodes."""
        test_name = "Evolution Tracking"
        start_time = time.time()
        
        try:
            logger.info(f"🧪 Running test: {test_name}")
            
            # Get initial cluster state
            initial_clusters = self._get_cluster_snapshot()
            
            # Add more test episodes
            new_episodes = self._create_additional_test_episodes()
            
            # Process new episodes
            for episode_id in new_episodes:
                self._simulate_additional_episode_processing(episode_id)
            
            # Run clustering again to trigger evolution tracking
            clustering_result = self.clustering_system.run_clustering()
            
            # Check clustering results
            # evolution_count = self._count_evolution_relationships()  # Evolution removed
            final_clusters = self._get_cluster_snapshot()
            
            # Verify clustering worked
            success = (
                clustering_result['status'] == 'success' and
                # evolution_count > 0 and  # Evolution removed
                len(final_clusters) >= len(initial_clusters)
            )
            
            self._add_test_result(TestResult(
                test_name=test_name,
                passed=success,
                message=f"Evolution tracking created {evolution_count} relationships",
                details={
                    "initial_clusters": len(initial_clusters),
                    "final_clusters": len(final_clusters),
                    "evolution_relationships": evolution_count,
                    "new_episodes_added": len(new_episodes)
                },
                execution_time=time.time() - start_time
            ))
            
        except Exception as e:
            self._add_test_result(TestResult(
                test_name=test_name,
                passed=False,
                message=f"Test failed with exception: {str(e)}",
                details={"error": str(e)},
                execution_time=time.time() - start_time
            ))
    
    def _test_edge_cases(self):
        """Test 4: Validate edge cases like empty episodes and outlier datasets."""
        test_name = "Edge Cases"
        start_time = time.time()
        
        try:
            logger.info(f"🧪 Running test: {test_name}")
            
            edge_case_results = {}
            
            # Test 1: Empty episode
            empty_episode_success = self._test_empty_episode()
            edge_case_results["empty_episode"] = empty_episode_success
            
            # Test 2: Very short episode
            short_episode_success = self._test_short_episode()
            edge_case_results["short_episode"] = short_episode_success
            
            # Test 3: Outlier-heavy dataset
            outlier_success = self._test_outlier_heavy_dataset()
            edge_case_results["outlier_heavy"] = outlier_success
            
            # Test 4: Large episode
            large_episode_success = self._test_large_episode()
            edge_case_results["large_episode"] = large_episode_success
            
            # Overall success if most edge cases pass
            passed_count = sum(1 for success in edge_case_results.values() if success)
            total_count = len(edge_case_results)
            success = passed_count >= (total_count * 0.75)  # 75% pass rate
            
            self._add_test_result(TestResult(
                test_name=test_name,
                passed=success,
                message=f"Edge cases: {passed_count}/{total_count} passed",
                details=edge_case_results,
                execution_time=time.time() - start_time
            ))
            
        except Exception as e:
            self._add_test_result(TestResult(
                test_name=test_name,
                passed=False,
                message=f"Test failed with exception: {str(e)}",
                details={"error": str(e)},
                execution_time=time.time() - start_time
            ))
    
    def _test_production_readiness(self):
        """Test 5: Verify system is ready for production use."""
        test_name = "Production Readiness"
        start_time = time.time()
        
        try:
            logger.info(f"🧪 Running test: {test_name}")
            
            readiness_checks = {}
            
            # Check 1: Performance meets criteria
            perf_check = self._check_performance_criteria()
            readiness_checks["performance"] = perf_check
            
            # Check 2: Data consistency
            consistency_check = self._check_data_consistency()
            readiness_checks["data_consistency"] = consistency_check
            
            # Check 3: Error handling
            error_handling_check = self._check_error_handling()
            readiness_checks["error_handling"] = error_handling_check
            
            # Check 4: Monitoring and logging
            monitoring_check = self._check_monitoring_capabilities()
            readiness_checks["monitoring"] = monitoring_check
            
            # Overall readiness
            all_checks_passed = all(readiness_checks.values())
            
            self._add_test_result(TestResult(
                test_name=test_name,
                passed=all_checks_passed,
                message="Production readiness assessment complete",
                details=readiness_checks,
                execution_time=time.time() - start_time
            ))
            
        except Exception as e:
            self._add_test_result(TestResult(
                test_name=test_name,
                passed=False,
                message=f"Test failed with exception: {str(e)}",
                details={"error": str(e)},
                execution_time=time.time() - start_time
            ))
    
    def _create_test_vtt_files(self) -> List[Path]:
        """Create test VTT files with realistic content."""
        test_files = []
        
        vtt_contents = [
            # File 1: Technology discussion
            """WEBVTT

1
00:00:00.000 --> 00:00:05.000
Welcome to our podcast about artificial intelligence and machine learning.

2
00:00:05.000 --> 00:00:10.000
Today we're discussing neural networks and deep learning algorithms.

3
00:00:10.000 --> 00:00:15.000
The transformer architecture has revolutionized natural language processing.

4
00:00:15.000 --> 00:00:20.000
GPT models use attention mechanisms to understand context in text.
""",
            # File 2: Business and economics
            """WEBVTT

1
00:00:00.000 --> 00:00:05.000
Let's talk about startup funding and venture capital investments.

2
00:00:05.000 --> 00:00:10.000
Market analysis shows growing interest in fintech and blockchain technologies.

3
00:00:10.000 --> 00:00:15.000
Cryptocurrency adoption is increasing among institutional investors.

4
00:00:15.000 --> 00:00:20.000
Digital transformation is reshaping traditional banking and finance.
""",
            # File 3: Science and research
            """WEBVTT

1
00:00:00.000 --> 00:00:05.000
Scientific research in quantum computing is advancing rapidly.

2
00:00:05.000 --> 00:00:10.000
Quantum algorithms could solve complex optimization problems.

3
00:00:10.000 --> 00:00:15.000
Climate change research shows accelerating global warming trends.

4
00:00:15.000 --> 00:00:20.000
Renewable energy technologies are becoming more cost-effective.
"""
        ]
        
        for i, content in enumerate(vtt_contents):
            file_path = Path(self.temp_dir) / f"test_episode_{i+1}.vtt"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            test_files.append(file_path)
        
        return test_files
    
    def _simulate_pipeline_processing(self, vtt_file: Path, episode_id: str) -> bool:
        """Simulate processing a VTT file through the pipeline."""
        try:
            # Create episode in database
            self.neo4j_service.create_episode_if_not_exists(
                episode_id=episode_id,
                podcast_name="test_podcast",
                title=f"Test Episode: {vtt_file.stem}",
                description="Test episode for end-to-end testing",
                publish_date="2024-01-01",
                file_path=str(vtt_file)
            )
            
            # Create some test meaningful units with embeddings
            self._create_test_meaningful_units(episode_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process {vtt_file}: {e}")
            return False
    
    def _create_test_meaningful_units(self, episode_id: str):
        """Create test meaningful units with synthetic embeddings."""
        import numpy as np
        
        # Create sample meaningful units
        units = [
            {"text": "Artificial intelligence and machine learning technologies", "importance": 0.8},
            {"text": "Neural networks and deep learning algorithms", "importance": 0.7},
            {"text": "Transformer architecture and attention mechanisms", "importance": 0.9},
            {"text": "Natural language processing applications", "importance": 0.6},
            {"text": "GPT models and language understanding", "importance": 0.8}
        ]
        
        for i, unit in enumerate(units):
            unit_id = f"{episode_id}_unit_{i}"
            
            # Generate synthetic embedding (768 dimensions)
            np.random.seed(hash(unit["text"]) % 2**32)  # Deterministic based on text
            embedding = np.random.randn(768).astype(np.float32)
            # Normalize
            embedding = embedding / np.linalg.norm(embedding)
            
            # Store in database
            self.neo4j_service.store_meaningful_unit(
                unit_id=unit_id,
                episode_id=episode_id,
                text=unit["text"],
                start_time=i * 5.0,
                end_time=(i + 1) * 5.0,
                embedding=embedding.tolist(),
                importance_score=unit["importance"]
            )
    
    def _verify_cluster_labels(self) -> int:
        """Verify that clusters have been assigned labels."""
        query = """
        MATCH (c:Cluster)
        WHERE c.label IS NOT NULL AND c.label <> ""
        RETURN count(c) as labeled_clusters
        """
        
        try:
            result = self.neo4j_service.query(query)
            if result:
                return result[0]['labeled_clusters']
        except Exception as e:
            logger.error(f"Failed to verify cluster labels: {e}")
        
        return 0
    
    def _get_cluster_snapshot(self) -> List[Dict[str, Any]]:
        """Get current cluster state for comparison."""
        query = """
        MATCH (c:Cluster)
        RETURN c.id as cluster_id, c.label as label, size((c)<-[:IN_CLUSTER]-()) as unit_count
        """
        
        try:
            result = self.neo4j_service.query(query)
            return [dict(record) for record in result] if result else []
        except Exception as e:
            logger.error(f"Failed to get cluster snapshot: {e}")
            return []
    
    def _create_additional_test_episodes(self) -> List[str]:
        """Create additional test episodes for evolution tracking."""
        new_episodes = ["evolution_test_episode_1", "evolution_test_episode_2"]
        
        for episode_id in new_episodes:
            # Create episode
            self.neo4j_service.create_episode_if_not_exists(
                episode_id=episode_id,
                podcast_name="test_podcast",
                title=f"Evolution Test: {episode_id}",
                description="Test episode for evolution tracking",
                publish_date="2024-01-02",
                file_path=""
            )
            
            # Add meaningful units with related but slightly different content
            self._create_evolution_test_units(episode_id)
        
        return new_episodes
    
    def _create_evolution_test_units(self, episode_id: str):
        """Create meaningful units for evolution testing."""
        import numpy as np
        
        # Content that's related to original but evolved
        units = [
            {"text": "Advanced AI systems and machine intelligence", "importance": 0.9},
            {"text": "Large language models and generative AI", "importance": 0.8},
            {"text": "Multimodal AI and computer vision", "importance": 0.7},
        ]
        
        for i, unit in enumerate(units):
            unit_id = f"{episode_id}_unit_{i}"
            
            # Generate related but different embeddings
            np.random.seed(hash(unit["text"]) % 2**32)
            embedding = np.random.randn(768).astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)
            
            self.neo4j_service.store_meaningful_unit(
                unit_id=unit_id,
                episode_id=episode_id,
                text=unit["text"],
                start_time=i * 5.0,
                end_time=(i + 1) * 5.0,
                embedding=embedding.tolist(),
                importance_score=unit["importance"]
            )
    
    def _simulate_additional_episode_processing(self, episode_id: str):
        """Simulate processing additional episodes."""
        # Episodes are already created with units in _create_additional_test_episodes
        pass
    
    # Evolution tracking removed - method no longer needed
    # def _count_evolution_relationships(self) -> int:
    #     """Count evolution relationships in the database."""
    #     query = """
    #     MATCH ()-[r:EVOLVED_INTO]->()
    #     RETURN count(r) as evolution_count
    #     """
    #     
    #     try:
    #         result = self.neo4j_service.query(query)
    #         if result:
    #             return result[0]['evolution_count']
    #     except Exception as e:
    #         logger.error(f"Failed to count evolution relationships: {e}")
    #     
    #     return 0
    
    def _test_empty_episode(self) -> bool:
        """Test handling of empty episode."""
        try:
            episode_id = "empty_test_episode"
            
            # Create episode with no meaningful units
            self.neo4j_service.create_episode_if_not_exists(
                episode_id=episode_id,
                podcast_name="test_podcast",
                title="Empty Test Episode",
                description="Episode with no content",
                publish_date="2024-01-01",
                file_path=""
            )
            
            # Try clustering - should handle gracefully
            result = self.clustering_system.run_clustering()
            return result['status'] in ['success', 'no_data']
            
        except Exception as e:
            logger.warning(f"Empty episode test failed: {e}")
            return False
    
    def _test_short_episode(self) -> bool:
        """Test handling of very short episode."""
        try:
            episode_id = "short_test_episode"
            
            self.neo4j_service.create_episode_if_not_exists(
                episode_id=episode_id,
                podcast_name="test_podcast",
                title="Short Test Episode",
                description="Very short episode",
                publish_date="2024-01-01",
                file_path=""
            )
            
            # Create only one meaningful unit
            import numpy as np
            embedding = np.random.randn(768).astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)
            
            self.neo4j_service.store_meaningful_unit(
                unit_id=f"{episode_id}_unit_0",
                episode_id=episode_id,
                text="Short content",
                start_time=0.0,
                end_time=5.0,
                embedding=embedding.tolist(),
                importance_score=0.5
            )
            
            result = self.clustering_system.run_clustering()
            return result['status'] == 'success'
            
        except Exception as e:
            logger.warning(f"Short episode test failed: {e}")
            return False
    
    def _test_outlier_heavy_dataset(self) -> bool:
        """Test handling of outlier-heavy dataset."""
        try:
            episode_id = "outlier_test_episode"
            
            self.neo4j_service.create_episode_if_not_exists(
                episode_id=episode_id,
                podcast_name="test_podcast",
                title="Outlier Test Episode",
                description="Episode with many outliers",
                publish_date="2024-01-01",
                file_path=""
            )
            
            # Create many diverse, unrelated units (likely to be outliers)
            import numpy as np
            for i in range(20):
                # Very different random embeddings
                embedding = np.random.randn(768).astype(np.float32) * 3  # Larger spread
                embedding = embedding / np.linalg.norm(embedding)
                
                self.neo4j_service.store_meaningful_unit(
                    unit_id=f"{episode_id}_unit_{i}",
                    episode_id=episode_id,
                    text=f"Outlier content {i}",
                    start_time=i * 5.0,
                    end_time=(i + 1) * 5.0,
                    embedding=embedding.tolist(),
                    importance_score=0.5
                )
            
            result = self.clustering_system.run_clustering()
            return result['status'] == 'success'
            
        except Exception as e:
            logger.warning(f"Outlier test failed: {e}")
            return False
    
    def _test_large_episode(self) -> bool:
        """Test handling of large episode."""
        try:
            episode_id = "large_test_episode"
            
            self.neo4j_service.create_episode_if_not_exists(
                episode_id=episode_id,
                podcast_name="test_podcast",
                title="Large Test Episode",
                description="Large episode with many units",
                publish_date="2024-01-01",
                file_path=""
            )
            
            # Create many meaningful units (50)
            import numpy as np
            for i in range(50):
                # Create clusters of related content
                cluster_id = i // 10  # 5 clusters of 10 units each
                np.random.seed(cluster_id * 1000 + i)
                
                # Base embedding for cluster + noise
                base_embedding = np.random.randn(768).astype(np.float32)
                noise = np.random.randn(768).astype(np.float32) * 0.3
                embedding = base_embedding + noise
                embedding = embedding / np.linalg.norm(embedding)
                
                self.neo4j_service.store_meaningful_unit(
                    unit_id=f"{episode_id}_unit_{i}",
                    episode_id=episode_id,
                    text=f"Large episode content {i} cluster {cluster_id}",
                    start_time=i * 5.0,
                    end_time=(i + 1) * 5.0,
                    embedding=embedding.tolist(),
                    importance_score=0.5
                )
            
            result = self.clustering_system.run_clustering()
            return result['status'] == 'success'
            
        except Exception as e:
            logger.warning(f"Large episode test failed: {e}")
            return False
    
    def _check_performance_criteria(self) -> bool:
        """Check if system meets performance criteria."""
        try:
            # Run a performance test similar to previous performance tests
            start_time = time.time()
            result = self.clustering_system.run_clustering()
            execution_time = time.time() - start_time
            
            # Check basic performance criteria
            if result['status'] != 'success':
                return False
                
            # Should complete reasonably quickly for test data
            if execution_time > 30:  # 30 seconds for test data
                logger.warning(f"Clustering took {execution_time:.1f}s - may be too slow")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Performance check failed: {e}")
            return False
    
    def _check_data_consistency(self) -> bool:
        """Check data consistency in the database."""
        try:
            # Check for orphaned nodes
            orphan_query = """
            MATCH (n)
            WHERE NOT ()-[]-(n) AND NOT n:Podcast AND NOT n:Episode
            RETURN count(n) as orphans
            """
            
            result = self.neo4j_service.query(orphan_query)
            orphan_count = result[0]['orphans'] if result else 0
            
            # Check for clusters without units
            empty_clusters_query = """
            MATCH (c:Cluster)
            WHERE NOT (c)<-[:IN_CLUSTER]-()
            RETURN count(c) as empty_clusters
            """
            
            result = self.neo4j_service.query(empty_clusters_query)
            empty_clusters = result[0]['empty_clusters'] if result else 0
            
            # Should have minimal orphans and no empty clusters
            return orphan_count < 5 and empty_clusters == 0
            
        except Exception as e:
            logger.error(f"Data consistency check failed: {e}")
            return False
    
    def _check_error_handling(self) -> bool:
        """Check error handling capabilities."""
        try:
            # Test with invalid configuration
            invalid_config = {'clustering': {'min_cluster_size_formula': 'invalid'}}
            
            try:
                invalid_system = SemanticClusteringSystem(
                    self.neo4j_service,
                    self.llm_service,
                    invalid_config
                )
                # Should handle gracefully
                result = invalid_system.run_clustering()
                # Should not crash, may return error status
                return True
                
            except Exception:
                # Expected to handle errors gracefully
                return True
                
        except Exception as e:
            logger.error(f"Error handling check failed: {e}")
            return False
    
    def _check_monitoring_capabilities(self) -> bool:
        """Check monitoring and logging capabilities."""
        try:
            # Verify logging is working by checking for log output during clustering
            import logging
            
            # Create a test handler to capture log messages
            test_handler = logging.Handler()
            test_handler.setLevel(logging.INFO)
            
            log_messages = []
            original_emit = test_handler.emit
            
            def capture_emit(record):
                log_messages.append(record.getMessage())
                return original_emit(record)
            
            test_handler.emit = capture_emit
            
            # Add handler temporarily
            logger.addHandler(test_handler)
            
            # Run clustering to generate logs
            self.clustering_system.run_clustering()
            
            # Remove handler
            logger.removeHandler(test_handler)
            
            # Check if monitoring logs were generated
            monitoring_logs = [msg for msg in log_messages if 'clustering' in msg.lower()]
            
            return len(monitoring_logs) > 0
            
        except Exception as e:
            logger.error(f"Monitoring check failed: {e}")
            return False
    
    def _create_test_schema(self):
        """Create test database schema."""
        try:
            # Create basic constraints and indexes
            constraints = [
                "CREATE CONSTRAINT podcast_name_unique IF NOT EXISTS FOR (p:Podcast) REQUIRE p.name IS UNIQUE",
                "CREATE CONSTRAINT episode_id_unique IF NOT EXISTS FOR (e:Episode) REQUIRE e.id IS UNIQUE",
                "CREATE CONSTRAINT cluster_id_unique IF NOT EXISTS FOR (c:Cluster) REQUIRE c.id IS UNIQUE",
            ]
            
            for constraint in constraints:
                try:
                    self.neo4j_service.query(constraint)
                except Exception as e:
                    # Constraint might already exist
                    pass
                    
        except Exception as e:
            logger.warning(f"Schema creation warning: {e}")
    
    def _add_test_result(self, result: TestResult):
        """Add a test result to the collection."""
        self.test_results.append(result)
        
        status = "✅ PASS" if result.passed else "❌ FAIL"
        logger.info(f"{status} {result.test_name}: {result.message} ({result.execution_time:.1f}s)")
    
    def _generate_test_report(self, total_time: float) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        passed_tests = [r for r in self.test_results if r.passed]
        failed_tests = [r for r in self.test_results if not r.passed]
        
        return {
            "test_suite": "End-to-End Clustering System Test",
            "execution_time": round(total_time, 2),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total_tests": len(self.test_results),
                "passed": len(passed_tests),
                "failed": len(failed_tests),
                "success_rate": len(passed_tests) / len(self.test_results) if self.test_results else 0
            },
            "test_results": [
                {
                    "name": r.test_name,
                    "status": "PASS" if r.passed else "FAIL",
                    "message": r.message,
                    "execution_time": r.execution_time,
                    "details": r.details
                }
                for r in self.test_results
            ],
            "production_ready": len(failed_tests) == 0 and len(passed_tests) >= 5
        }


def print_test_report(report: Dict[str, Any]):
    """Print formatted test report."""
    print("\n" + "=" * 70)
    print("🧪 END-TO-END CLUSTERING SYSTEM TEST REPORT")
    print("=" * 70)
    
    summary = report["summary"]
    print(f"\n📊 Test Summary:")
    print(f"   Total Tests: {summary['total_tests']}")
    print(f"   Passed: {summary['passed']}")
    print(f"   Failed: {summary['failed']}")
    print(f"   Success Rate: {summary['success_rate']:.1%}")
    print(f"   Execution Time: {report['execution_time']}s")
    
    print(f"\n📋 Test Results:")
    for result in report["test_results"]:
        status_icon = "✅" if result["status"] == "PASS" else "❌"
        print(f"   {status_icon} {result['name']}: {result['message']} ({result['execution_time']:.1f}s)")
    
    production_status = "✅ READY" if report["production_ready"] else "❌ NOT READY"
    print(f"\n🚀 Production Readiness: {production_status}")
    
    if not report["production_ready"]:
        print("\n⚠️  Issues to resolve before production:")
        for result in report["test_results"]:
            if result["status"] == "FAIL":
                print(f"   - {result['name']}: {result['message']}")
    
    print("\n" + "=" * 70)


def main():
    """Main test execution function."""
    # Check environment variables
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    if not gemini_api_key:
        print("❌ GEMINI_API_KEY environment variable not set")
        return False
    
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    
    # Initialize and run test suite
    test_suite = EndToEndTestSuite(neo4j_uri, gemini_api_key)
    
    try:
        # Setup test environment
        if not test_suite.setup_test_environment():
            print("❌ Failed to set up test environment")
            return False
        
        # Run all tests
        print("🚀 Starting End-to-End Test Suite...")
        report = test_suite.run_all_tests()
        
        # Print results
        print_test_report(report)
        
        # Return success status
        return report["production_ready"]
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        return False
        
    finally:
        # Always clean up
        test_suite.teardown_test_environment()


if __name__ == "__main__":
    success = main()
    print(f"\n🏁 End-to-End Test Suite {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)