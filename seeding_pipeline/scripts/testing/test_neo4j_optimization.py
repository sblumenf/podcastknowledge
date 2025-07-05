#!/usr/bin/env python3
"""Test script for Neo4j query optimization."""

import sys
import time
import random
from pathlib import Path
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig

def generate_test_data(num_podcasts: int = 5, episodes_per_podcast: int = 10, 
                      entities_per_episode: int = 20) -> tuple:
    """Generate test data for benchmarking."""
    podcasts = []
    episodes = []
    entities = []
    relationships = []
    
    # Generate podcasts
    for i in range(num_podcasts):
        podcast = {
            'id': f'podcast_{i}',
            'title': f'Test Podcast {i}',
            'description': f'Description for podcast {i}'
        }
        podcasts.append(podcast)
        
        # Generate episodes for each podcast
        for j in range(episodes_per_podcast):
            episode = {
                'id': f'episode_{i}_{j}',
                'title': f'Episode {j} of Podcast {i}',
                'description': f'Episode description {j}',
                'published_date': '2024-01-01',
                'podcast_id': podcast['id']
            }
            episodes.append(episode)
            
            # Generate entities for each episode
            for k in range(entities_per_episode):
                entity = {
                    'id': f'entity_{i}_{j}_{k}',
                    'name': f'Entity {k}',
                    'type': random.choice(['PERSON', 'ORGANIZATION', 'TOPIC', 'LOCATION'])
                }
                entities.append(entity)
                
                # Create relationship
                relationships.append({
                    'source_id': entity['id'],
                    'target_id': episode['id'],
                    'rel_type': 'MENTIONED_IN',
                    'properties': {'confidence': random.random()}
                })
    
    return podcasts, episodes, entities, relationships

def benchmark_individual_operations(storage: GraphStorageService, 
                                  entities: List[Dict[str, Any]],
                                  relationships: List[Dict[str, Any]]) -> dict:
    """Benchmark individual node/relationship creation."""
    print("\n" + "="*50)
    print("INDIVIDUAL OPERATIONS")
    print("="*50)
    
    # Create nodes individually
    start_time = time.time()
    for entity in entities[:100]:  # Limit to 100 for demo
        storage.create_node('Entity', entity)
    node_time = time.time() - start_time
    
    # Create relationships individually
    start_time = time.time()
    created = 0
    for rel in relationships[:50]:  # Limit to 50 for demo
        try:
            storage.create_relationship(
                rel['source_id'],
                rel['target_id'],
                rel['rel_type'],
                rel.get('properties')
            )
            created += 1
        except:
            pass  # Skip if nodes don't exist
    rel_time = time.time() - start_time
    
    print(f"Created 100 nodes individually in: {node_time:.2f}s")
    print(f"Created {created} relationships individually in: {rel_time:.2f}s")
    
    return {
        'method': 'individual',
        'node_time': node_time,
        'rel_time': rel_time,
        'total_time': node_time + rel_time
    }

def benchmark_bulk_operations(storage: GraphStorageService,
                            entities: List[Dict[str, Any]],
                            relationships: List[Dict[str, Any]]) -> dict:
    """Benchmark bulk node/relationship creation."""
    print("\n" + "="*50)
    print("BULK OPERATIONS (UNWIND)")
    print("="*50)
    
    # Create nodes in bulk
    start_time = time.time()
    storage.create_nodes_bulk('Entity', entities[:100])
    node_time = time.time() - start_time
    
    # Create relationships in bulk
    start_time = time.time()
    created = storage.create_relationships_bulk(relationships[:50])
    rel_time = time.time() - start_time
    
    print(f"Created 100 nodes in bulk in: {node_time:.2f}s")
    print(f"Created {created} relationships in bulk in: {rel_time:.2f}s")
    
    return {
        'method': 'bulk',
        'node_time': node_time,
        'rel_time': rel_time,
        'total_time': node_time + rel_time
    }

def benchmark_queries(storage: GraphStorageService) -> dict:
    """Benchmark query performance with and without caching."""
    print("\n" + "="*50)
    print("QUERY PERFORMANCE")
    print("="*50)
    
    # Complex query to test
    cypher = """
    MATCH (e:Entity)-[:MENTIONED_IN]->(ep:Episode)
    WHERE e.type = $entity_type
    RETURN e.name, count(ep) as episode_count
    ORDER BY episode_count DESC
    LIMIT 10
    """
    params = {'entity_type': 'PERSON'}
    
    # Without cache
    times_no_cache = []
    for i in range(5):
        start_time = time.time()
        results = storage.query(cypher, params, use_cache=False)
        elapsed = time.time() - start_time
        times_no_cache.append(elapsed)
        print(f"Query {i+1} without cache: {elapsed*1000:.1f}ms")
    
    print()
    
    # With cache
    times_with_cache = []
    for i in range(5):
        start_time = time.time()
        results = storage.query(cypher, params, use_cache=True)
        elapsed = time.time() - start_time
        times_with_cache.append(elapsed)
        print(f"Query {i+1} with cache: {elapsed*1000:.1f}ms")
    
    avg_no_cache = sum(times_no_cache) / len(times_no_cache)
    avg_with_cache = sum(times_with_cache) / len(times_with_cache)
    
    print(f"\nAverage query time without cache: {avg_no_cache*1000:.1f}ms")
    print(f"Average query time with cache: {avg_with_cache*1000:.1f}ms")
    print(f"Cache speedup: {avg_no_cache/avg_with_cache:.1f}x")
    
    return {
        'avg_no_cache_ms': avg_no_cache * 1000,
        'avg_with_cache_ms': avg_with_cache * 1000,
        'speedup': avg_no_cache / avg_with_cache if avg_with_cache > 0 else 0
    }

def main():
    """Run Neo4j optimization benchmarks."""
    print("Neo4j Query Optimization Test")
    print("=============================")
    
    # Load configuration
    config = PipelineConfig()
    
    # Initialize storage
    storage = GraphStorageService(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password
    )
    
    try:
        # Connect and setup schema
        print("\nConnecting to Neo4j...")
        storage.connect()
        storage.setup_schema()
        
        # Generate test data
        print("\nGenerating test data...")
        podcasts, episodes, entities, relationships = generate_test_data()
        print(f"  Podcasts: {len(podcasts)}")
        print(f"  Episodes: {len(episodes)}")
        print(f"  Entities: {len(entities)}")
        print(f"  Relationships: {len(relationships)}")
        
        # Clear existing data
        print("\nClearing existing test data...")
        with storage.session() as session:
            session.run("MATCH (n:Entity) DETACH DELETE n")
        
        # Run benchmarks
        results = []
        
        # Individual operations
        individual_result = benchmark_individual_operations(storage, entities, relationships)
        results.append(individual_result)
        
        # Clear for fair comparison
        with storage.session() as session:
            session.run("MATCH (n:Entity) DETACH DELETE n")
        
        # Bulk operations
        bulk_result = benchmark_bulk_operations(storage, entities, relationships)
        results.append(bulk_result)
        
        # Query benchmarks
        query_result = benchmark_queries(storage)
        
        # Display summary
        print("\n" + "="*70)
        print("BENCHMARK SUMMARY")
        print("="*70)
        print(f"{'Operation':<20} {'Time (s)':<15} {'Speedup':<10}")
        print("-"*70)
        
        individual_time = results[0]['total_time']
        for result in results:
            speedup = individual_time / result['total_time'] if result['total_time'] > 0 else 0
            print(f"{result['method']:<20} {result['total_time']:<15.2f} {speedup:.1f}x")
        
        print(f"\nQuery performance:")
        print(f"  Without cache: {query_result['avg_no_cache_ms']:.1f}ms")
        print(f"  With cache: {query_result['avg_with_cache_ms']:.1f}ms")
        print(f"  Cache speedup: {query_result['speedup']:.1f}x")
        
        # Validation
        print(f"\nValidation: <100ms average query time ", end="")
        if query_result['avg_with_cache_ms'] < 100:
            print("✓")
        else:
            print("✗")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if storage._driver:
            storage._driver.close()
        print("\nClosed Neo4j connection")

if __name__ == "__main__":
    main()