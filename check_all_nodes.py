#!/usr/bin/env python3
"""Check all nodes in the database."""

import os
from neo4j import GraphDatabase

def check_all_nodes():
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    username = os.getenv('NEO4J_USERNAME', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'password')
    
    driver = GraphDatabase.driver(uri, auth=(username, password))
    
    try:
        with driver.session() as session:
            # Count all nodes by label
            result = session.run("""
                MATCH (n)
                RETURN labels(n) as labels, COUNT(n) as count
                ORDER BY count DESC
            """)
            
            print("=== ALL NODES IN DATABASE ===")
            total = 0
            for record in result:
                labels_str = ', '.join(record['labels']) if record['labels'] else 'No label'
                count = record['count']
                total += count
                print(f"{labels_str}: {count}")
            
            print(f"\nTotal nodes: {total}")
            
            # Show MeaningfulUnit nodes if they exist
            result = session.run("""
                MATCH (u:MeaningfulUnit)
                RETURN u.id, u.unit_type, u.summary
                LIMIT 5
            """)
            
            units = list(result)
            if units:
                print("\n=== SAMPLE MEANINGFUL UNITS ===")
                for record in units:
                    print(f"\nID: {record['u.id']}")
                    print(f"Type: {record['u.unit_type']}")
                    print(f"Summary: {record['u.summary'][:100]}..." if record['u.summary'] else "No summary")
                    
    finally:
        driver.close()

if __name__ == "__main__":
    check_all_nodes()