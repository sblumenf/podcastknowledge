#!/usr/bin/env python3
"""Test script for SimplifiedUnifiedPipeline."""

import os
import tempfile
from pathlib import Path

# Create a sample VTT file for testing
SAMPLE_VTT = """WEBVTT

00:00:00.000 --> 00:00:05.000
<v Host>Welcome to our podcast about artificial intelligence.

00:00:05.000 --> 00:00:12.000
<v Host>Today we're discussing the latest developments in large language models.

00:00:12.000 --> 00:00:18.000
<v Guest>Thanks for having me. I'm excited to talk about GPT-4 and Claude.

00:00:18.000 --> 00:00:25.000
<v Guest>These models represent a significant leap in natural language understanding.

00:00:25.000 --> 00:00:32.000
<v Host>Let's start with the improvements in reasoning capabilities.

00:00:32.000 --> 00:00:40.000
<v Guest>Both models show enhanced ability to handle complex multi-step problems.

00:00:40.000 --> 00:00:48.000
<v Host>What about the implications for software development?

00:00:48.000 --> 00:00:56.000
<v Guest>Code generation has become remarkably sophisticated, with better context understanding.

00:00:56.000 --> 00:01:05.000
<v Host>Are there any concerns about reliability and hallucinations?

00:01:05.000 --> 00:01:15.000
<v Guest>Yes, hallucinations remain a challenge, but there's been progress in reducing them.
"""


def test_unified_pipeline():
    """Test the SimplifiedUnifiedPipeline with sample data."""
    print("=== Testing SimplifiedUnifiedPipeline ===\n")
    
    # Create temporary VTT file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.vtt', delete=False) as f:
        f.write(SAMPLE_VTT)
        vtt_path = f.name
    
    try:
        # Import required modules
        from src.pipeline.simplified_unified_pipeline import SimplifiedUnifiedPipeline
        from src.storage.graph_storage import GraphStorageService
        from src.services.llm import LLMService
        from src.core.models import Episode, Podcast
        from src.extraction.extraction import ExtractionConfig
        
        print("1. Initializing components...")
        
        # Initialize Neo4j storage (mock for testing)
        print("   - Initializing mock Neo4j storage")
        graph_storage = MockGraphStorage()
        
        # Initialize LLM service (mock for testing)
        print("   - Initializing mock LLM service")
        llm_service = MockLLMService()
        
        # Create extraction config
        extraction_config = ExtractionConfig(
            extract_quotes=True,
            entity_confidence_threshold=0.6,
            quote_importance_threshold=0.7
        )
        
        # Initialize pipeline
        print("   - Initializing SimplifiedUnifiedPipeline")
        pipeline = SimplifiedUnifiedPipeline(
            graph_storage=graph_storage,
            llm_service=llm_service,
            extraction_config=extraction_config
        )
        
        print("\n2. Creating test episode and podcast...")
        
        # Create test podcast and episode
        podcast = Podcast(
            id="podcast_test_001",
            name="AI Discussions",
            description="A podcast about artificial intelligence",
            rss_url="https://example.com/rss"
        )
        
        episode = Episode(
            id="episode_test_001",
            title="LLMs and the Future",
            description="Discussion about large language models",
            published_date="2024-01-15",
            youtube_url="https://youtube.com/watch?v=test123"
        )
        
        print("\n3. Processing episode through pipeline...")
        
        # Process the episode
        results = pipeline.process_episode(
            vtt_file_path=vtt_path,
            episode=episode,
            podcast=podcast
        )
        
        print("\n4. Processing Results:")
        print(f"   - Status: {results.get('status')}")
        print(f"   - Segments parsed: {results.get('segments_parsed')}")
        print(f"   - MeaningfulUnits created: {results.get('meaningful_units_created')}")
        print(f"   - Entities extracted: {results.get('entities_extracted')}")
        print(f"   - Insights extracted: {results.get('insights_extracted')}")
        print(f"   - Quotes extracted: {results.get('quotes_extracted')}")
        print(f"   - Relationships created: {results.get('relationships_created')}")
        print(f"   - Processing time: {results.get('processing_time', 0):.2f}s")
        
        if results.get('status') == 'success':
            print("\n✅ Pipeline test PASSED")
        else:
            print(f"\n❌ Pipeline test FAILED: {results.get('error')}")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up temp file
        if os.path.exists(vtt_path):
            os.unlink(vtt_path)


class MockGraphStorage:
    """Mock graph storage for testing."""
    
    def __init__(self):
        self.stored_items = {
            'podcasts': [],
            'episodes': [],
            'meaningful_units': [],
            'entities': [],
            'relationships': []
        }
    
    def session(self):
        """Mock session context manager."""
        return MockSession()
    
    def create_meaningful_unit(self, unit_data, episode_id):
        """Mock creating a meaningful unit."""
        self.stored_items['meaningful_units'].append({
            'data': unit_data,
            'episode_id': episode_id
        })
        print(f"     - Stored MeaningfulUnit: {unit_data['id']}")
        return unit_data['id']
    
    def create_meaningful_unit_relationship(self, source_id, unit_id, rel_type, properties=None):
        """Mock creating a relationship to meaningful unit."""
        self.stored_items['relationships'].append({
            'source': source_id,
            'target': unit_id,
            'type': rel_type,
            'properties': properties
        })


class MockSession:
    """Mock Neo4j session."""
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def run(self, query, **params):
        """Mock running a Cypher query."""
        # Just log what would be stored
        if 'MERGE' in query:
            node_type = query.split('(')[1].split(':')[1].split(' ')[0]
            node_id = params.get('id', 'unknown')
            print(f"     - Stored {node_type}: {node_id}")
        elif 'CREATE' in query:
            if 'Entity' in query:
                print(f"     - Stored Entity: {params.get('id')}")
            elif 'Insight' in query:
                print(f"     - Stored Insight: {params.get('id')}")
            elif 'Quote' in query:
                print(f"     - Stored Quote: {params.get('id')}")


class MockLLMService:
    """Mock LLM service for testing."""
    
    def generate_completion(self, prompt, system_prompt=None, response_format=None, temperature=0.7):
        """Mock LLM response for conversation analysis."""
        # Return a mock conversation structure as a dict
        # This avoids the model mismatch issues
        return {
            'units': [
                {
                    'start_index': 0,
                    'end_index': 4,
                    'unit_type': 'introduction',
                    'description': 'Introduction and discussion of LLMs',
                    'completeness': 'complete',
                    'key_entities': ['GPT-4', 'Claude'],
                    'confidence': 0.9,
                    'summary': 'Introduction to AI and LLMs discussion',
                    'is_complete': True,
                    'completeness_note': 'Full introduction captured'
                },
                {
                    'start_index': 5,
                    'end_index': 9,
                    'unit_type': 'topic_discussion',
                    'description': 'Technical details and implications of LLMs',
                    'completeness': 'complete',
                    'key_entities': ['software development', 'hallucinations'],
                    'confidence': 0.8,
                    'summary': 'Technical discussion about LLM capabilities and limitations',
                    'is_complete': True,
                    'completeness_note': 'Complete discussion captured'
                }
            ],
            'themes': [
                {
                    'theme': 'AI and LLMs',
                    'description': 'Discussion of artificial intelligence and large language models',
                    'evolution': 'Starts with introduction, moves to technical capabilities and limitations',
                    'related_units': [0, 1]
                }
            ],
            'flow': {
                'opening': 'Welcome and introduction',
                'development': 'From introduction to technical details',
                'conclusion': 'Discussion of challenges'
            },
            'insights': {
                'fragmentation_issues': [],
                'missing_context': [],
                'natural_boundaries': [4, 9],
                'overall_coherence': 0.9
            },
            'boundaries': [],
            'total_segments': 10
        }


if __name__ == "__main__":
    test_unified_pipeline()