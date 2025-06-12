#!/usr/bin/env python3
"""Check if all dependencies for schemaless mode are available."""

import sys
import importlib
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_neo4j_graphrag():
    """Check if neo4j-graphrag is installed with correct version."""
    try:
        import neo4j_graphrag
        version = getattr(neo4j_graphrag, '__version__', 'unknown')
        print(f"✓ neo4j-graphrag is installed (version: {version})")
        
        # Check minimum version
        if version != 'unknown':
            try:
                major, minor = map(int, version.split('.')[:2])
                if major == 0 and minor < 6:
                    print(f"⚠️  Warning: neo4j-graphrag version {version} is older than recommended 0.6.0")
                    return False
            except:
                pass
        return True
    except ImportError as e:
        print(f"✗ neo4j-graphrag is not installed")
        print(f"  Error: {e}")
        print(f"  Install with: pip install neo4j-graphrag>=0.6.0")
        return False


def check_simple_kg_pipeline():
    """Check if SimpleKGPipeline can be imported."""
    try:
        from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
        print("✓ SimpleKGPipeline can be imported")
        return True
    except ImportError as e:
        print("✗ SimpleKGPipeline cannot be imported")
        print(f"  Error: {e}")
        return False


def check_adapters():
    """Check if adapters can be instantiated."""
    errors = []
    
    # Check LLM adapter
    try:
        from src.providers.llm.gemini_adapter import GeminiGraphRAGAdapter
        print("✓ GeminiGraphRAGAdapter can be imported")
    except ImportError as e:
        errors.append(f"GeminiGraphRAGAdapter: {e}")
    
    # Check embedding adapter
    try:
        from src.providers.embeddings.sentence_transformer_adapter import SentenceTransformerGraphRAGAdapter
        print("✓ SentenceTransformerGraphRAGAdapter can be imported")
    except ImportError as e:
        errors.append(f"SentenceTransformerGraphRAGAdapter: {e}")
    
    if errors:
        print("\n✗ Adapter import errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    return True


def check_components():
    """Check if all schemaless components can be imported."""
    components = [
        ("TextPreprocessor", "src.processing.preprocessor"),
        ("EntityResolver", "src.processing.entity_resolution"),
        ("SchemalessMetadataEnricher", "src.providers.graph.metadata_enricher"),
        ("KnowledgeExtractor", "src.processing.extraction"),
        ("SchemalessNeo4jProvider", "src.providers.graph.schemaless_neo4j"),
    ]
    
    all_good = True
    for class_name, module_path in components:
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            print(f"✓ {class_name} can be imported from {module_path}")
        except Exception as e:
            print(f"✗ {class_name} import failed: {e}")
            all_good = False
    
    return all_good


def check_provider_factory():
    """Check if provider factory knows about schemaless provider."""
    try:
        from src.factories.provider_factory import ProviderFactory
        
        # Check if schemaless is in registry
        graph_providers = ProviderFactory._default_providers.get('graph', {})
        if 'schemaless' in graph_providers:
            print("✓ Provider factory knows about schemaless provider")
            return True
        else:
            print("✗ Provider factory missing schemaless provider")
            print(f"  Available graph providers: {list(graph_providers.keys())}")
            return False
    except Exception as e:
        print(f"✗ Cannot check provider factory: {e}")
        return False


def check_config_integration():
    """Check if config has schemaless settings."""
    try:
        from src.core.config import PipelineConfig
        from dataclasses import fields
        
        config_fields = {f.name for f in fields(PipelineConfig)}
        required_fields = {
            'use_schemaless_extraction',
            'schemaless_confidence_threshold',
            'entity_resolution_threshold',
            'max_properties_per_node',
            'relationship_normalization'
        }
        
        missing = required_fields - config_fields
        if missing:
            print(f"✗ Config missing fields: {missing}")
            return False
        else:
            print("✓ Config has all schemaless settings")
            return True
    except Exception as e:
        print(f"✗ Cannot check config: {e}")
        return False


def main():
    """Run all dependency checks."""
    print("Checking Schemaless Mode Dependencies\n")
    print("=" * 50)
    
    checks = [
        ("neo4j-graphrag package", check_neo4j_graphrag),
        ("SimpleKGPipeline import", check_simple_kg_pipeline),
        ("Adapter imports", check_adapters),
        ("Component imports", check_components),
        ("Provider factory", check_provider_factory),
        ("Config integration", check_config_integration),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n{name}:")
        print("-" * 30)
        results.append(check_func())
    
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✓ All checks passed ({passed}/{total})")
        print("\nSchemaless mode dependencies are ready!")
        return 0
    else:
        print(f"⚠️  Some checks failed ({passed}/{total} passed)")
        print("\nPlease fix the issues above before using schemaless mode.")
        return 1


if __name__ == "__main__":
    sys.exit(main())