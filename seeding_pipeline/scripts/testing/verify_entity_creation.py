#!/usr/bin/env python3
"""Quick script to verify entities exist in Neo4j."""

from neo4j import GraphDatabase

# Connect to Neo4j
driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "password")
)

with driver.session(database="neo4j") as session:
    # Count all entities
    query = """
    MATCH (n)
    WHERE n:Person OR n:Organization OR n:Topic OR n:Concept OR n:Event OR n:Product
    RETURN labels(n)[0] as EntityType, count(n) as Count
    ORDER BY Count DESC
    """
    
    result = session.run(query)
    
    print("Entity counts by type:")
    total = 0
    for record in result:
        print(f"  {record['EntityType']}: {record['Count']}")
        total += record['Count']
    
    print(f"\nTotal entities: {total}")
    
    # Show some examples
    if total > 0:
        print("\nExample entities:")
        query_examples = """
        MATCH (n)
        WHERE n:Person OR n:Organization OR n:Topic OR n:Concept OR n:Event OR n:Product
        RETURN labels(n)[0] as Type, n.name as Name
        LIMIT 10
        """
        
        examples = session.run(query_examples)
        for record in examples:
            print(f"  {record['Type']}: {record['Name']}")
        
        print(f"\n✅ SUCCESS: Found {total} entities!")
    else:
        print("\n❌ No entities found")

driver.close()