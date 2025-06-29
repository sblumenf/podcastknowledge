#!/usr/bin/env python3
"""Analyze the specific AI episode from MFM to understand any issues."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.storage.graph_storage import GraphStorageService

def analyze_ai_episode():
    """Analyze the AI episode specifically."""
    print("ANALYZING: How the Smartest Founders Are Quietly Winning with AI")
    print("="*60)
    
    storage = GraphStorageService(
        uri="neo4j://localhost:7688",
        username="neo4j",
        password="password"
    )
    
    try:
        storage.connect()
        print("✅ Connected to MFM database")
        
        with storage.session() as session:
            # Find the AI episode specifically
            print("\n--- FINDING AI EPISODE ---")
            result = session.run("""
                MATCH (e:Episode)
                WHERE e.title CONTAINS "AI" AND e.title CONTAINS "Smartest Founders"
                RETURN e.title as title, e.id as episode_id, 
                       e.vtt_filename as vtt_filename, e.created_at as created_at
            """)
            
            ai_episode = result.single()
            if not ai_episode:
                print("❌ AI episode not found in database!")
                return
            
            print(f"Found episode: {ai_episode['title']}")
            print(f"Episode ID: {ai_episode['episode_id']}")
            print(f"VTT filename: {ai_episode['vtt_filename']}")
            print(f"Created at: {ai_episode['created_at']}")
            
            # Count meaningful units for this episode
            print(f"\n--- MEANINGFUL UNITS FOR AI EPISODE ---")
            result = session.run("""
                MATCH (e:Episode)
                WHERE e.title CONTAINS "AI" AND e.title CONTAINS "Smartest Founders"
                MATCH (u:MeaningfulUnit)-[:PART_OF]->(e)
                RETURN count(u) as unit_count,
                       collect(u.id)[0..5] as sample_unit_ids
            """)
            
            record = result.single()
            if record:
                unit_count = record['unit_count']
                sample_ids = record['sample_unit_ids']
                
                print(f"Meaningful units found: {unit_count}")
                print(f"Sample unit IDs:")
                for i, unit_id in enumerate(sample_ids, 1):
                    print(f"  {i}. {unit_id}")
                
                if unit_count == 0:
                    print("⚠️  No meaningful units found for this episode!")
                elif unit_count == 1:
                    print("⚠️  Only 1 meaningful unit - likely a fallback structure!")
                else:
                    print(f"✅ Episode appears to have {unit_count} meaningful units")
            
            # Check for knowledge extraction results
            print(f"\n--- KNOWLEDGE EXTRACTION FOR AI EPISODE ---")
            result = session.run("""
                MATCH (e:Episode)
                WHERE e.title CONTAINS "AI" AND e.title CONTAINS "Smartest Founders"
                MATCH (u:MeaningfulUnit)-[:PART_OF]->(e)
                OPTIONAL MATCH (ent:Entity)-[:MENTIONED_IN]->(u)
                OPTIONAL MATCH (q:Quote)-[:EXTRACTED_FROM]->(u)
                OPTIONAL MATCH (i:Insight)-[:EXTRACTED_FROM]->(u)
                RETURN count(DISTINCT ent) as entities,
                       count(DISTINCT q) as quotes,
                       count(DISTINCT i) as insights
            """)
            
            record = result.single()
            if record:
                print(f"Entities: {record['entities']}")
                print(f"Quotes: {record['quotes']}")
                print(f"Insights: {record['insights']}")
                
                total_knowledge = record['entities'] + record['quotes'] + record['insights']
                if total_knowledge == 0:
                    print("⚠️  No knowledge components found!")
                else:
                    print(f"✅ Total knowledge components: {total_knowledge}")
            
            # Look for any specific error patterns in unit descriptions
            print(f"\n--- CHECKING FOR ERROR PATTERNS ---")
            result = session.run("""
                MATCH (e:Episode)
                WHERE e.title CONTAINS "AI" AND e.title CONTAINS "Smartest Founders"
                MATCH (u:MeaningfulUnit)-[:PART_OF]->(e)
                RETURN u.description as description, u.unit_type as unit_type,
                       u.completeness as completeness
                LIMIT 3
            """)
            
            units = list(result)
            if units:
                print("Sample meaningful unit details:")
                for i, unit in enumerate(units, 1):
                    desc = unit['description'] or 'No description'
                    unit_type = unit['unit_type'] or 'No type'
                    completeness = unit['completeness'] or 'No completeness'
                    
                    print(f"  Unit {i}:")
                    print(f"    Type: {unit_type}")
                    print(f"    Completeness: {completeness}")
                    print(f"    Description: {desc[:100]}...")
                    
                    # Check for fallback indicators
                    if 'fallback' in desc.lower():
                        print("    ⚠️  FALLBACK DETECTED!")
            
    except Exception as e:
        print(f"❌ Error analyzing AI episode: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            storage.disconnect()
        except:
            pass

def check_error_logs():
    """Check for error logs related to the AI episode."""
    print(f"\n{'='*60}")
    print("CHECKING ERROR LOGS FOR AI EPISODE")
    print(f"{'='*60}")
    
    # Look for checkpoint files
    checkpoint_files = list(Path("/home/sergeblumenfeld/podcastknowledge/seeding_pipeline/checkpoints").glob("*AI*"))
    if checkpoint_files:
        print(f"Found {len(checkpoint_files)} checkpoint files:")
        for f in checkpoint_files:
            print(f"  {f.name}")
    else:
        print("No checkpoint files found for AI episode")
    
    # Look for performance reports
    perf_files = list(Path("/home/sergeblumenfeld/podcastknowledge/seeding_pipeline/performance_reports").glob("*AI*"))
    if perf_files:
        print(f"\nFound {len(perf_files)} performance report files:")
        for f in perf_files:
            print(f"  {f.name}")
            # Try to read the file briefly
            try:
                with open(f, 'r') as file:
                    content = file.read(1000)  # First 1000 chars
                    if 'error' in content.lower() or 'fail' in content.lower():
                        print(f"    ⚠️  May contain error information")
            except:
                pass
    else:
        print("No performance report files found for AI episode")
    
    # Look for embedding failure logs
    embedding_failures = list(Path("/home/sergeblumenfeld/podcastknowledge/seeding_pipeline/logs/embedding_failures").glob("*AI*"))
    if embedding_failures:
        print(f"\n⚠️  Found {len(embedding_failures)} embedding failure logs:")
        for f in embedding_failures:
            print(f"  {f.name}")
    else:
        print("\nNo embedding failure logs found for AI episode")

def main():
    """Main analysis function."""
    analyze_ai_episode()
    check_error_logs()

if __name__ == "__main__":
    main()