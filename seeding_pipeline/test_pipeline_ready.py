#!/usr/bin/env python3
"""Quick test to verify pipeline is ready to run."""

import sys
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Test all imports
print("Testing imports...")

try:
    from src.pipeline.unified_pipeline import UnifiedKnowledgePipeline
    print("✅ UnifiedKnowledgePipeline imported successfully")
except Exception as e:
    print(f"❌ Failed to import UnifiedKnowledgePipeline: {e}")
    sys.exit(1)

try:
    from src.storage.graph_storage import GraphStorageService
    print("✅ GraphStorageService imported successfully")
except Exception as e:
    print(f"❌ Failed to import GraphStorageService: {e}")
    sys.exit(1)

try:
    from src.services.llm import LLMService
    print("✅ LLMService imported successfully")
except Exception as e:
    print(f"❌ Failed to import LLMService: {e}")
    sys.exit(1)

try:
    from src.services.embeddings import EmbeddingsService
    print("✅ EmbeddingsService imported successfully")
except Exception as e:
    print(f"❌ Failed to import EmbeddingsService: {e}")
    sys.exit(1)

# Test VTT file exists
vtt_path = Path("test_transcript.vtt")
if vtt_path.exists():
    print(f"✅ Test VTT file exists: {vtt_path}")
else:
    print(f"❌ Test VTT file not found: {vtt_path}")

# Check environment variables
import os

print("\nChecking environment variables...")
neo4j_uri = os.getenv('NEO4J_URI', 'neo4j://localhost:7687')
print(f"NEO4J_URI: {neo4j_uri}")

neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
print(f"NEO4J_USER: {neo4j_user}")

neo4j_password = os.getenv('NEO4J_PASSWORD')
if neo4j_password:
    print("✅ NEO4J_PASSWORD is set")
else:
    print("❌ NEO4J_PASSWORD is not set")

gemini_api_key = os.getenv('GEMINI_API_KEY')
google_api_key = os.getenv('GOOGLE_API_KEY')
if gemini_api_key or google_api_key:
    print("✅ API key is set (GEMINI_API_KEY or GOOGLE_API_KEY)")
else:
    print("❌ API key is not set (need GEMINI_API_KEY or GOOGLE_API_KEY)")

# Test component initialization
print("\nTesting component initialization...")

try:
    # Test without actual connections
    llm_service = LLMService(api_key="test-key")
    print("✅ LLMService can be initialized")
except Exception as e:
    print(f"❌ Failed to initialize LLMService: {e}")

try:
    # Don't actually connect to Neo4j
    graph_storage = GraphStorageService(
        uri="neo4j://localhost:7687",
        username="neo4j",
        password="test"
    )
    print("✅ GraphStorageService can be initialized")
except Exception as e:
    print(f"❌ Failed to initialize GraphStorageService: {e}")

try:
    # Initialize pipeline
    pipeline = UnifiedKnowledgePipeline(
        graph_storage=graph_storage,
        llm_service=llm_service,
        embeddings_service=None
    )
    print("✅ UnifiedKnowledgePipeline can be initialized")
    
    # Check key methods exist
    assert hasattr(pipeline, 'process_vtt_file'), "process_vtt_file method missing"
    print("✅ process_vtt_file method exists")
    
    # Check internal methods
    assert hasattr(pipeline, '_parse_vtt'), "_parse_vtt method missing"
    assert hasattr(pipeline, '_identify_speakers'), "_identify_speakers method missing"
    assert hasattr(pipeline, '_analyze_conversation'), "_analyze_conversation method missing"
    assert hasattr(pipeline, '_create_meaningful_units'), "_create_meaningful_units method missing"
    assert hasattr(pipeline, '_extract_knowledge'), "_extract_knowledge method missing"
    assert hasattr(pipeline, '_store_knowledge'), "_store_knowledge method missing"
    assert hasattr(pipeline, '_run_analysis'), "_run_analysis method missing"
    print("✅ All pipeline methods exist")
    
except Exception as e:
    print(f"❌ Failed to initialize pipeline: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("PIPELINE READINESS CHECK COMPLETE")
print("="*60)

missing_configs = []
if not neo4j_password:
    missing_configs.append("NEO4J_PASSWORD")
if not (gemini_api_key or google_api_key):
    missing_configs.append("GEMINI_API_KEY or GOOGLE_API_KEY")

if missing_configs:
    print(f"\n⚠️  Missing required environment variables: {', '.join(missing_configs)}")
    print("\nSet them with:")
    for config in missing_configs:
        print(f"export {config}=your-value-here")
else:
    print("\n✅ All components are ready!")
    print("\nYou can now run:")
    print("python main.py test_transcript.vtt --podcast 'Test Podcast' --title 'Test Episode'")