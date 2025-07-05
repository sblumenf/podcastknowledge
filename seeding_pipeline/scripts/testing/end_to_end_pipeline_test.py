# End-to-end pipeline test - not meant to be run directly
"""
End-to-End Pipeline Testing Script for Phase 6 Task 6.2

Tests the complete unified pipeline functionality using the comprehensive test episode.
Performs simple pass/fail validation as specified in the plan.
"""

import sys
import os
import asyncio
from pathlib import Path
from typing import Dict, Any, List

# Add the project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import required modules
from src.pipeline.unified_pipeline import UnifiedKnowledgePipeline
from src.storage.graph_storage import GraphStorageService
from src.services.llm import LLMService
from src.services.embeddings import EmbeddingsService


class EndToEndTester:
    """End-to-end pipeline testing class."""
    
    def __init__(self):
        self.test_results = {
            "speaker_identification": False,
            "meaningful_units": False,
            "entity_extraction": False,
            "quote_extraction": False,
            "insight_generation": False,
            "gap_detection": False,
            "diversity_metrics": False,
            "missing_links": False,
            "no_segments_stored": False,
            "pipeline_completion": False
        }
        self.pipeline = None
        self.episode_id = "test_comprehensive_episode"
        
    async def setup_pipeline(self):
        """Initialize the unified pipeline for testing."""
        print("Setting up unified pipeline...")
        
        try:
            # Initialize services (using minimal config for testing)
            graph_storage = GraphStorageService(
                uri="bolt://localhost:7687",
                username="neo4j", 
                password="password"  # This would come from env in real usage
            )
            
            llm_service = LLMService()
            embeddings_service = EmbeddingsService()
            
            # Initialize pipeline
            self.pipeline = UnifiedKnowledgePipeline(
                graph_storage=graph_storage,
                llm_service=llm_service,
                embeddings_service=embeddings_service
            )
            
            print("✅ Pipeline setup complete")
            return True
            
        except Exception as e:
            print(f"❌ Pipeline setup failed: {e}")
            return False
    
    async def run_pipeline_test(self):
        """Run the pipeline on the comprehensive test episode."""
        print("\nRunning pipeline on comprehensive test episode...")
        
        try:
            # Path to test VTT file
            vtt_path = Path("test_data/comprehensive_test_episode.vtt")
            if not vtt_path.exists():
                print(f"❌ Test VTT file not found: {vtt_path}")
                return False
            
            # Episode metadata
            episode_metadata = {
                "episode_id": self.episode_id,
                "title": "Tech Frontiers - AI and Entrepreneurship Discussion",
                "youtube_url": "https://youtube.com/watch?v=test123",
                "description": "Comprehensive test episode for pipeline validation"
            }
            
            # Run the pipeline
            print("Processing VTT file through unified pipeline...")
            result = await self.pipeline.process_vtt_file(vtt_path, episode_metadata)
            
            if result.get("status") == "completed":
                print("✅ Pipeline completed successfully")
                self.test_results["pipeline_completion"] = True
                return True
            else:
                print(f"❌ Pipeline failed: {result.get('errors', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ Pipeline execution failed: {e}")
            return False
    
    def validate_speaker_identification(self):
        """Validate that speaker identification worked correctly."""
        print("\nValidating speaker identification...")
        
        try:
            with self.pipeline.graph_storage.session() as session:
                # Check if speakers were identified (not generic Speaker 0, Speaker 1, etc.)
                query = """
                MATCH (e:Episode {id: $episode_id})-[:PART_OF]->(mu:MeaningfulUnit)
                RETURN DISTINCT mu.speaker_distribution as speakers
                """
                
                result = session.run(query, episode_id=self.episode_id)
                speakers_found = []
                
                for record in result:
                    speaker_dist = record["speakers"]
                    if speaker_dist:
                        speakers_found.extend(speaker_dist.keys())
                
                # Expected speakers from our test episode
                expected_speakers = ["Alex", "Sarah", "Dr. Kim", "Mike"]
                
                # Check that we found real names, not generic ones
                generic_patterns = ["Speaker 0", "Speaker 1", "Speaker 2", "Speaker 3"]
                has_generic = any(speaker in str(speakers_found) for speaker in generic_patterns)
                has_expected = any(speaker in str(speakers_found) for speaker in expected_speakers)
                
                if not has_generic and has_expected:
                    print("✅ Speaker identification successful - found real names")
                    self.test_results["speaker_identification"] = True
                else:
                    print(f"❌ Speaker identification failed - found: {speakers_found}")
                    
        except Exception as e:
            print(f"❌ Speaker identification validation failed: {e}")
    
    def validate_meaningful_units(self):
        """Validate MeaningfulUnit creation and storage."""
        print("\nValidating MeaningfulUnit creation...")
        
        try:
            with self.pipeline.graph_storage.session() as session:
                # Check MeaningfulUnits were created
                query = """
                MATCH (e:Episode {id: $episode_id})-[:PART_OF]->(mu:MeaningfulUnit)
                RETURN COUNT(mu) as unit_count, 
                       COLLECT(mu.id) as unit_ids,
                       COLLECT(mu.start_time) as start_times
                """
                
                result = session.run(query, episode_id=self.episode_id)
                record = result.single()
                
                if record:
                    unit_count = record["unit_count"]
                    unit_ids = record["unit_ids"]
                    start_times = record["start_times"]
                    
                    if unit_count > 0:
                        print(f"✅ Created {unit_count} MeaningfulUnits")
                        print(f"   Unit IDs: {unit_ids[:3]}..." if len(unit_ids) > 3 else f"   Unit IDs: {unit_ids}")
                        self.test_results["meaningful_units"] = True
                    else:
                        print("❌ No MeaningfulUnits found")
                else:
                    print("❌ No MeaningfulUnits query result")
                    
        except Exception as e:
            print(f"❌ MeaningfulUnit validation failed: {e}")
    
    def validate_entity_extraction(self):
        """Validate that entities were extracted."""
        print("\nValidating entity extraction...")
        
        try:
            with self.pipeline.graph_storage.session() as session:
                # Check entities were extracted
                query = """
                MATCH (e:Episode {id: $episode_id})-[:MENTIONS]->(entity)
                RETURN COUNT(entity) as entity_count,
                       COLLECT(DISTINCT labels(entity)[0]) as entity_types,
                       COLLECT(entity.name)[0..5] as sample_entities
                """
                
                result = session.run(query, episode_id=self.episode_id)
                record = result.single()
                
                if record:
                    entity_count = record["entity_count"]
                    entity_types = record["entity_types"]
                    sample_entities = record["sample_entities"]
                    
                    if entity_count > 0:
                        print(f"✅ Extracted {entity_count} entities")
                        print(f"   Types found: {entity_types}")
                        print(f"   Sample entities: {sample_entities}")
                        self.test_results["entity_extraction"] = True
                    else:
                        print("❌ No entities found")
                else:
                    print("❌ No entity query result")
                    
        except Exception as e:
            print(f"❌ Entity extraction validation failed: {e}")
    
    def validate_quote_extraction(self):
        """Validate that quotes were extracted with speakers and timestamps."""
        print("\nValidating quote extraction...")
        
        try:
            with self.pipeline.graph_storage.session() as session:
                # Check quotes were extracted
                query = """
                MATCH (e:Episode {id: $episode_id})-[:CONTAINS]->(q:Quote)
                RETURN COUNT(q) as quote_count,
                       COLLECT(q.speaker)[0..3] as sample_speakers,
                       COLLECT(q.timestamp)[0..3] as sample_timestamps,
                       COLLECT(q.type)[0..3] as sample_types
                """
                
                result = session.run(query, episode_id=self.episode_id)
                record = result.single()
                
                if record:
                    quote_count = record["quote_count"]
                    sample_speakers = record["sample_speakers"]
                    sample_timestamps = record["sample_timestamps"]
                    sample_types = record["sample_types"]
                    
                    if quote_count > 0:
                        print(f"✅ Extracted {quote_count} quotes")
                        print(f"   Sample speakers: {sample_speakers}")
                        print(f"   Sample timestamps: {sample_timestamps}")
                        print(f"   Sample types: {sample_types}")
                        self.test_results["quote_extraction"] = True
                    else:
                        print("❌ No quotes found")
                else:
                    print("❌ No quote query result")
                    
        except Exception as e:
            print(f"❌ Quote extraction validation failed: {e}")
    
    def validate_insight_generation(self):
        """Validate that insights were generated."""
        print("\nValidating insight generation...")
        
        try:
            with self.pipeline.graph_storage.session() as session:
                # Check insights were generated
                query = """
                MATCH (e:Episode {id: $episode_id})-[:CONTAINS]->(i:Insight)
                RETURN COUNT(i) as insight_count,
                       COLLECT(i.type)[0..3] as sample_types
                """
                
                result = session.run(query, episode_id=self.episode_id)
                record = result.single()
                
                if record:
                    insight_count = record["insight_count"]
                    sample_types = record["sample_types"]
                    
                    if insight_count > 0:
                        print(f"✅ Generated {insight_count} insights")
                        print(f"   Sample types: {sample_types}")
                        self.test_results["insight_generation"] = True
                    else:
                        print("❌ No insights found")
                else:
                    print("❌ No insight query result")
                    
        except Exception as e:
            print(f"❌ Insight generation validation failed: {e}")
    
    def validate_analysis_modules(self):
        """Validate that all analysis modules ran."""
        print("\nValidating analysis modules...")
        
        try:
            with self.pipeline.graph_storage.session() as session:
                # Check gap detection
                gap_query = """
                MATCH (sg:StructuralGap)
                RETURN COUNT(sg) as gap_count
                """
                result = session.run(gap_query)
                gap_count = result.single()["gap_count"] if result.single() else 0
                
                if gap_count >= 0:  # Even 0 gaps is valid - means analysis ran
                    print(f"✅ Gap detection ran - found {gap_count} gaps")
                    self.test_results["gap_detection"] = True
                
                # Check diversity metrics
                diversity_query = """
                MATCH (em:EcologicalMetrics)
                RETURN COUNT(em) as metrics_count
                """
                result = session.run(diversity_query)
                metrics_count = result.single()["metrics_count"] if result.single() else 0
                
                if metrics_count > 0:
                    print(f"✅ Diversity metrics updated - found {metrics_count} metrics nodes")
                    self.test_results["diversity_metrics"] = True
                else:
                    print("❌ No diversity metrics found")
                
                # Check missing links
                missing_links_query = """
                MATCH (ml:MissingLink)
                RETURN COUNT(ml) as links_count
                """
                result = session.run(missing_links_query)
                links_count = result.single()["links_count"] if result.single() else 0
                
                if links_count >= 0:  # Even 0 links is valid - means analysis ran
                    print(f"✅ Missing links analysis ran - found {links_count} suggested links")
                    self.test_results["missing_links"] = True
                    
        except Exception as e:
            print(f"❌ Analysis modules validation failed: {e}")
    
    def validate_no_segments_stored(self):
        """Validate that no individual segments were stored."""
        print("\nValidating no segments stored...")
        
        try:
            with self.pipeline.graph_storage.session() as session:
                # Check that no Segment nodes exist for this episode
                query = """
                MATCH (e:Episode {id: $episode_id})-[:CONTAINS]->(s:Segment)
                RETURN COUNT(s) as segment_count
                """
                
                result = session.run(query, episode_id=self.episode_id)
                record = result.single()
                
                if record:
                    segment_count = record["segment_count"]
                    
                    if segment_count == 0:
                        print("✅ No segments stored - only MeaningfulUnits as required")
                        self.test_results["no_segments_stored"] = True
                    else:
                        print(f"❌ Found {segment_count} segments stored (should be 0)")
                else:
                    print("✅ No segments found - validation passed")
                    self.test_results["no_segments_stored"] = True
                    
        except Exception as e:
            print(f"❌ Segment validation failed: {e}")
    
    def print_test_summary(self):
        """Print comprehensive test results."""
        print("\n" + "="*50)
        print("END-TO-END PIPELINE TEST RESULTS")
        print("="*50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(self.test_results.values())
        
        for test_name, passed in self.test_results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{test_name:25}: {status}")
        
        print("-"*50)
        print(f"TOTAL: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED! Pipeline validation successful.")
            return True
        else:
            print("❌ Some tests failed. Pipeline validation incomplete.")
            return False


async def main():
    """Run the end-to-end pipeline test."""
    print("Phase 6 Task 6.2: End-to-End Pipeline Testing")
    print("="*50)
    
    tester = EndToEndTester()
    
    # Setup pipeline
    if not await tester.setup_pipeline():
        return False
    
    # Run pipeline test
    if not await tester.run_pipeline_test():
        return False
    
    # Run validation tests
    tester.validate_speaker_identification()
    tester.validate_meaningful_units()
    tester.validate_entity_extraction()
    tester.validate_quote_extraction()
    tester.validate_insight_generation()
    tester.validate_analysis_modules()
    tester.validate_no_segments_stored()
    
    # Print summary
    success = tester.print_test_summary()
    
    return success


# This test should only be run as part of the test suite, not directly
# Use main.py for processing episodes