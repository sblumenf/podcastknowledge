#!/usr/bin/env python3
"""Check MeaningfulUnits in Neo4j database."""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Neo4j connection settings
uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
username = os.getenv("NEO4J_USERNAME", "neo4j")
password = os.getenv("NEO4J_PASSWORD")
database = os.getenv("NEO4J_DATABASE", "neo4j")

if not password:
    print("Error: NEO4J_PASSWORD not set in environment")
    exit(1)

# Create driver
driver = GraphDatabase.driver(uri, auth=(username, password))

def run_query(query, parameters=None):
    """Run a query and return results."""
    with driver.session(database=database) as session:
        result = session.run(query, parameters or {})
        return list(result)

def check_meaningful_units():
    """Check MeaningfulUnits in the database."""
    
    print("Checking MeaningfulUnits in Neo4j database...")
    print(f"URI: {uri}")
    print(f"Database: {database}")
    print("-" * 80)
    
    # Query 1: Count total MeaningfulUnits
    query1 = "MATCH (m:MeaningfulUnit) RETURN count(m) as total"
    result1 = run_query(query1)
    total_units = result1[0]['total'] if result1 else 0
    print(f"1. Total MeaningfulUnits: {total_units}")
    
    # Query 2: Count MeaningfulUnits with embeddings
    query2 = """
    MATCH (m:MeaningfulUnit) 
    WHERE m.embedding IS NOT NULL 
    RETURN count(m) as with_embeddings
    """
    result2 = run_query(query2)
    units_with_embeddings = result2[0]['with_embeddings'] if result2 else 0
    print(f"2. MeaningfulUnits with embeddings: {units_with_embeddings}")
    
    # Query 3: Count MeaningfulUnits without embeddings
    query3 = """
    MATCH (m:MeaningfulUnit) 
    WHERE m.embedding IS NULL 
    RETURN count(m) as without_embeddings
    """
    result3 = run_query(query3)
    units_without_embeddings = result3[0]['without_embeddings'] if result3 else 0
    print(f"3. MeaningfulUnits without embeddings: {units_without_embeddings}")
    
    # Query 4: Sample a MeaningfulUnit to see its properties
    query4 = """
    MATCH (m:MeaningfulUnit)
    RETURN m
    LIMIT 1
    """
    result4 = run_query(query4)
    
    if result4:
        sample_unit = result4[0]['m']
        print("\n4. Sample MeaningfulUnit properties:")
        properties = dict(sample_unit)
        
        # Show all properties except embedding (which is large)
        for key, value in properties.items():
            if key == 'embedding':
                if value is not None:
                    print(f"   - {key}: [PRESENT - {len(value)} dimensions]")
                else:
                    print(f"   - {key}: NULL")
            else:
                if isinstance(value, str) and len(value) > 100:
                    print(f"   - {key}: {value[:100]}...")
                else:
                    print(f"   - {key}: {value}")
    else:
        print("\n4. No MeaningfulUnits found in database")
    
    # Query 5: Check if there are any MeaningfulUnits with partial embeddings
    query5 = """
    MATCH (m:MeaningfulUnit)
    WHERE m.embedding IS NOT NULL
    RETURN m.id, size(m.embedding) as embedding_size
    LIMIT 5
    """
    result5 = run_query(query5)
    
    if result5:
        print("\n5. Sample of MeaningfulUnits with embeddings:")
        for record in result5:
            print(f"   - Unit ID: {record['m.id']}, Embedding size: {record['embedding_size']}")
    
    # Query 6: Check for any error properties that might indicate embedding failures
    query6 = """
    MATCH (m:MeaningfulUnit)
    WHERE m.embedding_error IS NOT NULL OR m.error IS NOT NULL
    RETURN m.id, m.embedding_error, m.error
    LIMIT 5
    """
    result6 = run_query(query6)
    
    if result6:
        print("\n6. MeaningfulUnits with error properties:")
        for record in result6:
            print(f"   - Unit ID: {record['m.id']}")
            if record.get('m.embedding_error'):
                print(f"     Embedding error: {record['m.embedding_error']}")
            if record.get('m.error'):
                print(f"     Error: {record['m.error']}")
    else:
        print("\n6. No MeaningfulUnits with error properties found")
    
    # Query 7: Check Episodes to see if embedding generation was supposed to run
    query7 = """
    MATCH (e:Episode)
    RETURN e.title, e.podcast, e.process_status, e.embedding_status
    LIMIT 5
    """
    result7 = run_query(query7)
    
    if result7:
        print("\n7. Sample Episodes and their status:")
        for record in result7:
            print(f"   - Title: {record['e.title']}")
            print(f"     Podcast: {record['e.podcast']}")
            print(f"     Process status: {record.get('e.process_status', 'N/A')}")
            print(f"     Embedding status: {record.get('e.embedding_status', 'N/A')}")
            print()
    
    # Summary
    print("-" * 80)
    print("SUMMARY:")
    print(f"Total MeaningfulUnits: {total_units}")
    print(f"With embeddings: {units_with_embeddings} ({units_with_embeddings/total_units*100:.1f}% if total_units > 0 else 0)")
    print(f"Without embeddings: {units_without_embeddings} ({units_without_embeddings/total_units*100:.1f}% if total_units > 0 else 0)")
    
    if units_without_embeddings > 0:
        print("\n⚠️  WARNING: There are MeaningfulUnits without embeddings!")
        print("This suggests the embedding generation step may not have completed successfully.")

if __name__ == "__main__":
    try:
        check_meaningful_units()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.close()