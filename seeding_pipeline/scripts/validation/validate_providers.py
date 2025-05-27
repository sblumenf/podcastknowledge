#!/usr/bin/env python3
"""Validate all providers with test data."""

import os
import sys
import json
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.factories.provider_factory import ProviderFactory, ProviderManager
from src.providers.health import ProviderHealthMonitor


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_audio_provider(provider_name: str = 'mock') -> bool:
    """Validate audio provider functionality."""
    logger.info(f"Validating audio provider: {provider_name}")
    
    try:
        # Create provider
        config = {
            'provider': provider_name,
            'model_size': 'base',
            'device': 'cpu'
        }
        
        if provider_name == 'mock':
            config['mock_response'] = {
                'transcription': "This is a test transcription.",
                'segments': [
                    {"text": "This is a test.", "start": 0.0, "end": 2.0},
                    {"text": "transcription.", "start": 2.0, "end": 3.0}
                ]
            }
            
        provider = ProviderFactory.create_audio_provider(provider_name, config)
        
        # Test health check
        health = provider.health_check()
        logger.info(f"Health check: {health}")
        
        if not health.get('healthy'):
            logger.error(f"Provider unhealthy: {health}")
            return False
            
        # Test transcription (for mock provider)
        if provider_name == 'mock':
            result = provider.transcribe("dummy_path.wav")
            logger.info(f"Transcription result: {len(result)} segments")
            
        logger.info(f"✓ Audio provider '{provider_name}' validated successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Audio provider validation failed: {e}")
        return False


def validate_llm_provider(provider_name: str = 'mock') -> bool:
    """Validate LLM provider functionality."""
    logger.info(f"Validating LLM provider: {provider_name}")
    
    try:
        # Create provider
        config = {
            'provider': provider_name,
            'model_name': 'test-model',
            'temperature': 0.7
        }
        
        if provider_name == 'gemini':
            # Need API key for real provider
            api_key = os.environ.get('GEMINI_API_KEY')
            if not api_key:
                logger.warning("GEMINI_API_KEY not set, skipping Gemini validation")
                return True
            config['api_key'] = api_key
            config['model_name'] = 'gemini-2.0-flash'
        elif provider_name == 'mock':
            config['response_mode'] = 'fixed'
            config['default_response'] = 'Test response from LLM'
            
        provider = ProviderFactory.create_llm_provider(provider_name, config)
        
        # Test health check
        health = provider.health_check()
        logger.info(f"Health check: {health}")
        
        if not health.get('healthy'):
            logger.error(f"Provider unhealthy: {health}")
            return False
            
        # Test completion
        response = provider.complete("Hello, please respond with 'OK'")
        logger.info(f"Completion response: {response[:50]}...")
        
        # Test rate limits
        rate_limits = provider.get_rate_limits()
        logger.info(f"Rate limits: {rate_limits}")
        
        logger.info(f"✓ LLM provider '{provider_name}' validated successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ LLM provider validation failed: {e}")
        return False


def validate_graph_provider(provider_name: str = 'memory') -> bool:
    """Validate graph database provider functionality."""
    logger.info(f"Validating graph provider: {provider_name}")
    
    try:
        # Create provider
        config = {
            'provider': provider_name,
            'database': 'test'
        }
        
        if provider_name == 'neo4j':
            # Need connection details for real provider
            uri = os.environ.get('NEO4J_URI')
            if not uri:
                logger.warning("NEO4J_URI not set, skipping Neo4j validation")
                return True
                
            config.update({
                'uri': uri,
                'username': os.environ.get('NEO4J_USERNAME', 'neo4j'),
                'password': os.environ.get('NEO4J_PASSWORD')
            })
            
        provider = ProviderFactory.create_graph_provider(provider_name, config)
        
        # Test connection
        provider.connect()
        
        # Test health check
        health = provider.health_check()
        logger.info(f"Health check: {health}")
        
        if not health.get('healthy'):
            logger.error(f"Provider unhealthy: {health}")
            return False
            
        # Test basic operations
        # Create a test node
        node_id = provider.create_node('TestNode', {
            'id': 'test1',
            'name': 'Test Node',
            'value': 42
        })
        logger.info(f"Created node: {node_id}")
        
        # Get the node
        node = provider.get_node(node_id)
        logger.info(f"Retrieved node: {node}")
        
        # Update the node
        provider.update_node(node_id, {'value': 100})
        
        # Delete the node
        provider.delete_node(node_id)
        
        # Disconnect
        provider.disconnect()
        
        logger.info(f"✓ Graph provider '{provider_name}' validated successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Graph provider validation failed: {e}")
        return False


def validate_embedding_provider(provider_name: str = 'mock') -> bool:
    """Validate embedding provider functionality."""
    logger.info(f"Validating embedding provider: {provider_name}")
    
    try:
        # Create provider
        config = {
            'provider': provider_name,
            'dimension': 384
        }
        
        if provider_name == 'sentence_transformer':
            config['model_name'] = 'all-MiniLM-L6-v2'
            config['device'] = 'cpu'
        elif provider_name == 'openai':
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                logger.warning("OPENAI_API_KEY not set, skipping OpenAI validation")
                return True
            config['api_key'] = api_key
            config['model_name'] = 'text-embedding-3-small'
            config['dimension'] = 1536
        elif provider_name == 'mock':
            config['mode'] = 'hash'
            
        provider = ProviderFactory.create_embedding_provider(provider_name, config)
        
        # Test health check
        health = provider.health_check()
        logger.info(f"Health check: {health}")
        
        if not health.get('healthy'):
            logger.error(f"Provider unhealthy: {health}")
            return False
            
        # Test single embedding
        text = "This is a test sentence for embedding."
        embedding = provider.generate_embedding(text)
        logger.info(f"Single embedding dimension: {len(embedding)}")
        
        # Test batch embeddings
        texts = [
            "First test sentence.",
            "Second test sentence.",
            "Third test sentence."
        ]
        embeddings = provider.generate_embeddings(texts)
        logger.info(f"Batch embeddings: {len(embeddings)} embeddings generated")
        
        # Test similarity
        sim = provider.similarity(embeddings[0], embeddings[1])
        logger.info(f"Similarity between first two: {sim:.3f}")
        
        # Get model info
        info = provider.get_model_info()
        logger.info(f"Model info: {info}")
        
        logger.info(f"✓ Embedding provider '{provider_name}' validated successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Embedding provider validation failed: {e}")
        return False


def validate_provider_factory():
    """Validate provider factory functionality."""
    logger.info("Validating provider factory...")
    
    try:
        # Test available providers
        available = ProviderFactory.get_available_providers()
        logger.info(f"Available providers: {json.dumps(available, indent=2)}")
        
        # Test creating from config
        config = {
            'audio': {'provider': 'mock'},
            'llm': {'provider': 'mock', 'response_mode': 'fixed'},
            'graph': {'provider': 'memory'},
            'embedding': {'provider': 'mock', 'dimension': 128}
        }
        
        providers = ProviderFactory.create_from_config(config)
        logger.info(f"Created {len(providers)} providers from config")
        
        # Test health check all
        health_results = ProviderFactory.health_check_all(providers)
        
        all_healthy = all(
            result.get('healthy', False) 
            for result in health_results.values()
        )
        
        if all_healthy:
            logger.info("✓ All providers healthy")
        else:
            logger.error("✗ Some providers unhealthy")
            for name, result in health_results.items():
                if not result.get('healthy'):
                    logger.error(f"  - {name}: {result}")
                    
        return all_healthy
        
    except Exception as e:
        logger.error(f"✗ Provider factory validation failed: {e}")
        return False


def validate_health_monitoring():
    """Validate health monitoring system."""
    logger.info("Validating health monitoring...")
    
    try:
        # Create monitor
        monitor = ProviderHealthMonitor(check_interval=5.0)
        
        # Create test providers
        config = {'dimension': 128}
        embedding_provider = ProviderFactory.create_embedding_provider('mock', config)
        
        # Register provider
        monitor.register_provider(
            'test_embedding',
            embedding_provider,
            fallback_providers=['backup_embedding']
        )
        
        # Check provider health
        health = monitor.check_provider_health('test_embedding')
        logger.info(f"Provider health: {health}")
        
        # Get provider status
        status = monitor.get_provider_status('test_embedding')
        logger.info(f"Provider status: {json.dumps(status, indent=2)}")
        
        # Test aggregated health
        aggregate = monitor.aggregate_health()
        logger.info(f"Aggregate health: {json.dumps(aggregate, indent=2)}")
        
        logger.info("✓ Health monitoring validated successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Health monitoring validation failed: {e}")
        return False


def main():
    """Main validation script."""
    logger.info("=" * 60)
    logger.info("Provider Validation Script")
    logger.info("=" * 60)
    
    results = {
        'audio': False,
        'llm': False,
        'graph': False,
        'embedding': False,
        'factory': False,
        'health': False
    }
    
    # Validate each provider type
    logger.info("\n1. Validating Audio Providers")
    results['audio'] = validate_audio_provider('mock')
    
    logger.info("\n2. Validating LLM Providers")
    results['llm'] = validate_llm_provider('mock')
    
    logger.info("\n3. Validating Graph Providers")
    results['graph'] = validate_graph_provider('memory')
    
    logger.info("\n4. Validating Embedding Providers")
    results['embedding'] = validate_embedding_provider('mock')
    
    logger.info("\n5. Validating Provider Factory")
    results['factory'] = validate_provider_factory()
    
    logger.info("\n6. Validating Health Monitoring")
    results['health'] = validate_health_monitoring()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("VALIDATION SUMMARY")
    logger.info("=" * 60)
    
    passed = 0
    failed = 0
    
    for component, result in results.items():
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{component.capitalize():20} {status}")
        if result:
            passed += 1
        else:
            failed += 1
            
    logger.info("-" * 60)
    logger.info(f"Total: {passed} passed, {failed} failed")
    
    # Exit code
    if failed > 0:
        logger.error("\n⚠️  Some validations failed!")
        sys.exit(1)
    else:
        logger.info("\n✅ All validations passed!")
        sys.exit(0)


if __name__ == '__main__':
    main()