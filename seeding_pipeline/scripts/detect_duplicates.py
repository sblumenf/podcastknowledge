#!/usr/bin/env python3
"""Detect and analyze duplicates in the Neo4j database."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.storage.graph_storage import GraphStorageService
from src.core.config import PipelineConfig

def detect_duplicates():
    """Detect various types of duplicates in the database."""
    config = PipelineConfig()
    storage = GraphStorageService(
        uri=config.neo4j_uri,
        username=config.neo4j_username,
        password=config.neo4j_password,
        database=config.neo4j_database
    )
    
    try:
        print("=== Duplicate Detection Report ===\n")
        
        # 1. Episode duplicates by title
        print("1. Episodes with duplicate titles:")
        query = """
        MATCH (e:Episode)
        WITH e.title as title, collect(e) as episodes
        WHERE size(episodes) > 1
        RETURN title, size(episodes) as count, [ep in episodes | ep.id] as episode_ids
        ORDER BY count DESC
        """
        results = storage.query(query)
        if results:
            for r in results:
                print(f"  '{r['title']}': {r['count']} episodes")
                for ep_id in r['episode_ids']:
                    print(f"    - {ep_id}")
        else:
            print("  No duplicate episode titles found.")
        
        print()
        
        # 2. Duplicate speaker patterns in same episode
        print("2. Episodes with potential duplicate speakers:")
        query = """
        MATCH (e:Episode)
        OPTIONAL MATCH (mu:MeaningfulUnit)-[:PART_OF]->(e)
        WHERE mu.speaker_distribution IS NOT NULL
        WITH e, collect(DISTINCT mu.speaker_distribution) as patterns
        WHERE size(patterns) > 1
        RETURN e.title as title, size(patterns) as pattern_count, patterns
        ORDER BY pattern_count DESC
        LIMIT 5
        """
        results = storage.query(query)
        if results:
            import json
            for r in results:
                print(f"  '{r['title']}': {r['pattern_count']} different speaker patterns")
                
                # Analyze speakers in each pattern
                all_speakers = set()
                for pattern in r['patterns']:
                    try:
                        if isinstance(pattern, str) and pattern.startswith('{'):
                            speaker_dict = json.loads(pattern.replace("'", '"'))
                            all_speakers.update(speaker_dict.keys())
                    except:
                        pass
                
                print(f"    All speakers found: {sorted(list(all_speakers))}")
        else:
            print("  No episodes with multiple speaker patterns found.")
        
        print()
        
        # 3. Duplicate meaningful units
        print("3. Duplicate meaningful units (same text content):")
        query = """
        MATCH (mu:MeaningfulUnit)
        WITH mu.text as text, collect(mu) as units
        WHERE size(units) > 1 AND text IS NOT NULL
        RETURN text[0..100] + "..." as sample_text, size(units) as count
        ORDER BY count DESC
        LIMIT 5
        """
        results = storage.query(query)
        if results:
            for r in results:
                print(f"  {r['count']} units with text: '{r['sample_text']}'")
        else:
            print("  No duplicate meaningful units found.")
        
        print()
        
        # 4. Check episode processing status
        print("4. Episode processing status:")
        query = """
        MATCH (e:Episode)
        RETURN e.processing_status as status, count(*) as count
        """
        results = storage.query(query)
        if results:
            for r in results:
                status = r['status'] or 'NULL'
                print(f"  {status}: {r['count']} episodes")
        
        print()
        
        # 5. Check for constraint violations (shouldn't exist if constraints work)
        print("5. Checking for constraint violations:")
        
        # Episode ID duplicates
        query = """
        MATCH (e:Episode)
        WITH e.id as episode_id, collect(e) as episodes
        WHERE size(episodes) > 1
        RETURN episode_id, size(episodes) as count
        """
        results = storage.query(query)
        if results:
            print("  ❌ Episode ID duplicates found:")
            for r in results:
                print(f"    Episode ID '{r['episode_id']}': {r['count']} instances")
        else:
            print("  ✅ No Episode ID duplicates (constraints working)")
        
        # MeaningfulUnit ID duplicates  
        query = """
        MATCH (mu:MeaningfulUnit)
        WITH mu.id as unit_id, collect(mu) as units
        WHERE size(units) > 1
        RETURN unit_id, size(units) as count
        LIMIT 5
        """
        results = storage.query(query)
        if results:
            print("  ❌ MeaningfulUnit ID duplicates found:")
            for r in results:
                print(f"    Unit ID '{r['unit_id']}': {r['count']} instances")
        else:
            print("  ✅ No MeaningfulUnit ID duplicates (constraints working)")
        
        print()
        
        # 6. Summary statistics
        print("6. Database summary:")
        queries = {
            "Episodes": "MATCH (e:Episode) RETURN count(*) as count",
            "MeaningfulUnits": "MATCH (mu:MeaningfulUnit) RETURN count(*) as count", 
            "Entities": "MATCH (en:Entity) RETURN count(*) as count",
            "Topics": "MATCH (t:Topic) RETURN count(*) as count"
        }
        
        for label, query in queries.items():
            result = storage.query(query)
            count = result[0]['count'] if result else 0
            print(f"  {label}: {count}")
        
    except Exception as e:
        print(f"Error detecting duplicates: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        storage.close()

if __name__ == "__main__":
    detect_duplicates()