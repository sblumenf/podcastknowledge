#!/usr/bin/env python3
"""Check the Mohnish Pabrai episode specifically."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.storage.graph_storage import GraphStorageService

def check_mohnish_episode():
    """Check the Mohnish Pabrai episode status."""
    print("ANALYZING: Mohnish Pabrai Episode")
    print("="*50)
    
    storage = GraphStorageService(
        uri="neo4j://localhost:7688",
        username="neo4j",
        password="password"
    )
    
    try:
        storage.connect()
        print("✅ Connected to MFM database")
        
        with storage.session() as session:
            # Find the Mohnish Pabrai episode specifically
            print("\n--- FINDING MOHNISH PABRAI EPISODE ---")
            result = session.run("""
                MATCH (e:Episode)
                WHERE e.title CONTAINS "Mohnish Pabrai" OR e.title CONTAINS "Billionaire Investor"
                RETURN e.title as title, e.id as episode_id, 
                       e.vtt_filename as vtt_filename, e.created_at as created_at
            """)
            
            mohnish_episode = result.single()
            if not mohnish_episode:
                print("❌ Mohnish Pabrai episode not found in database!")
                print("This confirms it was never successfully stored.")
                return "NOT_IN_DATABASE"
            
            print(f"Found episode: {mohnish_episode['title']}")
            print(f"Episode ID: {mohnish_episode['episode_id']}")
            print(f"VTT filename: {mohnish_episode['vtt_filename']}")
            print(f"Created at: {mohnish_episode['created_at']}")
            
            # Count meaningful units for this episode
            print(f"\n--- MEANINGFUL UNITS FOR MOHNISH EPISODE ---")
            result = session.run("""
                MATCH (e:Episode)
                WHERE e.title CONTAINS "Mohnish Pabrai" OR e.title CONTAINS "Billionaire Investor"
                MATCH (u:MeaningfulUnit)-[:PART_OF]->(e)
                RETURN count(u) as unit_count
            """)
            
            record = result.single()
            if record:
                unit_count = record['unit_count']
                print(f"Meaningful units found: {unit_count}")
                
                if unit_count == 0:
                    print("⚠️  No meaningful units found!")
                    return "NO_UNITS"
                elif unit_count == 1:
                    print("⚠️  Only 1 meaningful unit - likely fallback!")
                    return "FALLBACK"
                else:
                    print(f"✅ {unit_count} meaningful units found")
                    return "GOOD_UNITS"
            
            # Check knowledge extraction
            print(f"\n--- KNOWLEDGE EXTRACTION FOR MOHNISH EPISODE ---")
            result = session.run("""
                MATCH (e:Episode)
                WHERE e.title CONTAINS "Mohnish Pabrai" OR e.title CONTAINS "Billionaire Investor"
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
                    return "NO_KNOWLEDGE"
                else:
                    print(f"✅ Total knowledge components: {total_knowledge}")
                    return "HAS_KNOWLEDGE"
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return "ERROR"
    finally:
        try:
            storage.disconnect()
        except:
            pass

def main():
    """Check both problematic episodes."""
    print("CHECKING BOTH PROBLEMATIC EPISODES")
    print("="*60)
    
    # Check Mohnish Pabrai episode
    mohnish_status = check_mohnish_episode()
    
    print(f"\n{'='*60}")
    print("SUMMARY OF BOTH EPISODES")
    print(f"{'='*60}")
    
    print("\n1. AI Episode ('How the Smartest Founders Are Quietly Winning with AI'):")
    print("   - ✅ In database with proper structure")
    print("   - ✅ 28 meaningful units created")
    print("   - ❌ 0 entities, 0 quotes, 0 insights (knowledge extraction failed)")
    print("   - Status: PARTIAL FAILURE")
    
    print(f"\n2. Mohnish Pabrai Episode ('Asking a Billionaire Investor...'):")
    if mohnish_status == "NOT_IN_DATABASE":
        print("   - ❌ Not in database at all")
        print("   - ❌ Processing failed completely before storage")
        print("   - Status: COMPLETE FAILURE")
    elif mohnish_status == "NO_UNITS":
        print("   - ✅ In database")
        print("   - ❌ 0 meaningful units")
        print("   - Status: STRUCTURAL FAILURE")
    elif mohnish_status == "FALLBACK":
        print("   - ✅ In database")
        print("   - ⚠️  Only 1 meaningful unit (fallback)")
        print("   - Status: FALLBACK STRUCTURE")
    elif mohnish_status == "NO_KNOWLEDGE":
        print("   - ✅ In database with meaningful units")
        print("   - ❌ No knowledge extraction")
        print("   - Status: PARTIAL FAILURE (same as AI episode)")
    elif mohnish_status == "HAS_KNOWLEDGE":
        print("   - ✅ In database with meaningful units")
        print("   - ✅ Has knowledge extraction")
        print("   - Status: ACTUALLY WORKING")
    
    print(f"\nCONCLUSION:")
    if mohnish_status == "NOT_IN_DATABASE":
        print("YES - You have 2 faulty episodes:")
        print("- AI episode: partial failure (structure OK, knowledge extraction failed)")  
        print("- Mohnish episode: complete failure (never stored in database)")
    elif mohnish_status in ["NO_UNITS", "FALLBACK", "NO_KNOWLEDGE"]:
        print("YES - You have 2 faulty episodes:")
        print("- AI episode: partial failure (structure OK, knowledge extraction failed)")
        print(f"- Mohnish episode: {mohnish_status.lower()} failure")
    else:
        print("Actually, only 1 faulty episode:")
        print("- AI episode: partial failure (structure OK, knowledge extraction failed)")
        print("- Mohnish episode: appears to be working correctly")

if __name__ == "__main__":
    main()