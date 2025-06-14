#!/usr/bin/env python3
"""Test script to verify entity extraction is working after fixes."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.pipeline.enhanced_knowledge_pipeline import EnhancedKnowledgePipeline
from neo4j import GraphDatabase


async def test_entity_extraction():
    """Test that entities are actually being extracted."""
    
    print("=" * 60)
    print("Testing Entity Extraction Fix")
    print("=" * 60)
    
    # Initialize pipeline
    print("\n1. Initializing pipeline...")
    pipeline = EnhancedKnowledgePipeline(
        enable_all_features=True,
        neo4j_config={
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password",
            "database": "neo4j"
        }
    )
    print("✅ Pipeline initialized")
    
    # Test with a sample VTT file
    test_vtt = Path("test_data/hour_podcast_test.vtt")
    if not test_vtt.exists():
        print(f"❌ Test file not found: {test_vtt}")
        print("Creating a simple test VTT file...")
        
        # Create test directory and file
        test_vtt.parent.mkdir(exist_ok=True)
        test_vtt.write_text("""WEBVTT

00:00:00.000 --> 00:00:10.000
<v Speaker1>Today we're discussing artificial intelligence with Dr. Sarah Johnson from Stanford University.

00:00:10.000 --> 00:00:20.000
<v Dr. Johnson>Thank you for having me. AI and machine learning are transforming healthcare diagnostics.

00:00:20.000 --> 00:00:30.000
<v Speaker1>Can you tell us about the recent breakthroughs in cancer detection using neural networks?

00:00:30.000 --> 00:00:40.000
<v Dr. Johnson>Absolutely. We've developed systems that can analyze medical imaging with unprecedented accuracy.
""")
        print("✅ Created test VTT file")
    
    # Process the file
    print(f"\n2. Processing VTT file: {test_vtt}")
    result = await pipeline.process_vtt_file(test_vtt)
    
    print(f"\n3. Results:")
    print(f"   Entities created: {result.entities_created}")
    print(f"   Relationships created: {result.relationships_created}")
    print(f"   Processing time: {result.processing_time:.2f}s")
    
    # Query Neo4j to verify entities
    print("\n4. Verifying entities in Neo4j...")
    try:
        driver = GraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "password")
        )
        
        with driver.session(database="neo4j") as session:
            # Count entities by type
            query = """
            MATCH (n)
            WHERE n:Person OR n:Organization OR n:Topic OR n:Concept OR n:Event OR n:Product
            RETURN labels(n)[0] as EntityType, count(n) as Count
            ORDER BY Count DESC
            """
            
            result_neo4j = session.run(query)
            
            print("\n   Entity counts by type:")
            total = 0
            for record in result_neo4j:
                print(f"   - {record['EntityType']}: {record['Count']}")
                total += record['Count']
            
            print(f"\n   Total entities in Neo4j: {total}")
            
            # Show some example entities
            query_examples = """
            MATCH (n)
            WHERE n:Person OR n:Organization OR n:Topic OR n:Concept OR n:Event OR n:Product
            RETURN labels(n)[0] as Type, n.name as Name
            LIMIT 10
            """
            
            examples = session.run(query_examples)
            print("\n   Example entities:")
            for record in examples:
                print(f"   - {record['Type']}: {record['Name']}")
        
        driver.close()
        
    except Exception as e:
        print(f"❌ Neo4j query failed: {e}")
        print("   Make sure Neo4j is running at bolt://localhost:7687")
    
    # Cleanup
    pipeline.close()
    
    # Success check
    if result.entities_created > 0:
        print(f"\n✅ SUCCESS: Entity extraction is working! Created {result.entities_created} entities.")
        return True
    else:
        print(f"\n❌ FAILED: No entities created. Entity extraction is still broken.")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_entity_extraction())
    sys.exit(0 if success else 1)