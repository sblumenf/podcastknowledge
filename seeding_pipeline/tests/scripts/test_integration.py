#!/usr/bin/env python3
"""Quick integration test to verify all components work together."""

from pathlib import Path
import sys
# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

def test_imports():
    """Test that all components can be imported."""
    print("Testing imports...")
    
    errors = []
    
    # Test each import individually to find the specific issue
    # Phase 1 - POC removed during cleanup
    
    try:
        from src.providers.llm.gemini_adapter import GeminiGraphRAGAdapter, create_gemini_adapter
        print("✓ GeminiGraphRAGAdapter")
    except ImportError as e:
        print(f"✗ GeminiGraphRAGAdapter: {e}")
        errors.append(e)
    
    try:
        from src.providers.embeddings.sentence_transformer_adapter import (
            SentenceTransformerGraphRAGAdapter, create_sentence_transformer_adapter
        )
        print("✓ SentenceTransformerGraphRAGAdapter")
    except ImportError as e:
        print(f"✗ SentenceTransformerGraphRAGAdapter: {e}")
        errors.append(e)
    
    # Phase 2
    try:
        from src.utils.component_tracker import ComponentTracker, track_component_impact
        print("✓ ComponentTracker")
    except ImportError as e:
        print(f"✗ ComponentTracker: {e}")
        errors.append(e)
    
    try:
        from src.extraction.preprocessor import TextPreprocessor
        print("✓ TextPreprocessor (consolidated)")
    except ImportError as e:
        print(f"✗ TextPreprocessor: {e}")
        errors.append(e)
    
    try:
        from src.extraction.entity_resolution import EntityResolver
        print("✓ EntityResolver (consolidated)")
    except ImportError as e:
        print(f"✗ EntityResolver: {e}")
        errors.append(e)
    
    try:
        from src.providers.graph.metadata_enricher import SchemalessMetadataEnricher
        print("✓ SchemalessMetadataEnricher")
    except ImportError as e:
        print(f"✗ SchemalessMetadataEnricher: {e}")
        errors.append(e)
    
    try:
        from src.extraction.extraction import KnowledgeExtractor
        print("✓ KnowledgeExtractor (consolidated)")
    except ImportError as e:
        print(f"✗ KnowledgeExtractor: {e}")
        errors.append(e)
    
    # Phase 3 - Graph providers available
    
    # Phase 4
    try:
        from src.migration.query_translator import QueryTranslator
        print("✓ QueryTranslator")
    except ImportError as e:
        print(f"✗ QueryTranslator: {e}")
        errors.append(e)
    
    try:
        from src.migration.result_standardizer import ResultStandardizer
        print("✓ ResultStandardizer")
    except ImportError as e:
        print(f"✗ ResultStandardizer: {e}")
        errors.append(e)
    
    try:
        from src.providers.graph.compatible_neo4j import CompatibleNeo4jProvider
        print("✓ CompatibleNeo4jProvider")
    except ImportError as e:
        print(f"✗ CompatibleNeo4jProvider: {e}")
        errors.append(e)
    
    if errors:
        print(f"\n❌ {len(errors)} import(s) failed")
        return False
    else:
        print("\n✅ All imports successful!")
        return True

def test_basic_instantiation():
    """Test basic instantiation of key components."""
    print("\nTesting component instantiation...")
    
    try:
        from src.extraction.preprocessor import TextPreprocessor
        preprocessor = TextPreprocessor()
        print("✓ TextPreprocessor instantiated")
        
        from src.extraction.entity_resolution import EntityResolver
        resolver = EntityResolver()
        print("✓ EntityResolver instantiated")
        
        from src.providers.graph.metadata_enricher import SchemalessMetadataEnricher
        enricher = SchemalessMetadataEnricher()
        print("✓ SchemalessMetadataEnricher instantiated")
        
        from src.extraction.extraction import KnowledgeExtractor
        extractor = KnowledgeExtractor(None, None)  # Mock services
        print("✓ KnowledgeExtractor instantiated")
        
        from src.migration.query_translator import QueryTranslator
        translator = QueryTranslator()
        print("✓ QueryTranslator instantiated")
        
        from src.migration.result_standardizer import ResultStandardizer
        standardizer = ResultStandardizer()
        print("✓ ResultStandardizer instantiated")
        
        print("\n✅ All components instantiated successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Instantiation failed: {e}")
        return False

def main():
    """Run integration tests."""
    print("=== Phase 1-4 Integration Test ===\n")
    
    # Test imports
    if not test_imports():
        print("\nFix import issues before proceeding to Phase 5")
        return 1
    
    # Test instantiation
    if not test_basic_instantiation():
        print("\nFix instantiation issues before proceeding to Phase 5")
        return 1
    
    print("\n✅ All integration tests passed!")
    print("The code is ready to proceed to Phase 5 (Testing Infrastructure)")
    return 0

if __name__ == '__main__':
    sys.exit(main())