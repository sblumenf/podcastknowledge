#!/usr/bin/env python3
"""
Analyze Neo4j node types for a specific podcast database.

This script provides comprehensive analysis of all node types in a podcast's Neo4j database,
including property analysis, relationship mapping, and categorical value extraction.
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Tuple, Any

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from neo4j import GraphDatabase
import yaml


def load_podcast_config(podcast_name: str) -> Dict[str, Any]:
    """Load configuration for a specific podcast."""
    config_path = os.path.join(project_root, 'config', 'podcasts.yaml')
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Find the podcast configuration
    for podcast in config.get('podcasts', []):
        if podcast['name'].lower() == podcast_name.lower() or podcast['id'].lower() == podcast_name.lower():
            return podcast
    
    raise ValueError(f"Podcast '{podcast_name}' not found in configuration. Available podcasts: " + 
                    ", ".join([p['name'] for p in config.get('podcasts', [])]))


def get_all_node_labels(driver, database: str) -> List[str]:
    """Get all node labels in the database."""
    with driver.session(database=database) as session:
        result = session.run("CALL db.labels()")
        return [record["label"] for record in result]


def get_node_count(driver, database: str, label: str) -> int:
    """Get count of nodes for a specific label."""
    with driver.session(database=database) as session:
        query = f"MATCH (n:{label}) RETURN count(n) as count"
        result = session.run(query)
        return result.single()["count"]


def get_sample_nodes(driver, database: str, label: str, limit: int = 5) -> List[Dict]:
    """Get sample nodes for a specific label."""
    with driver.session(database=database) as session:
        query = f"MATCH (n:{label}) RETURN n LIMIT {limit}"
        result = session.run(query)
        return [dict(record["n"]) for record in result]


def get_all_properties_for_label(driver, database: str, label: str) -> List[str]:
    """Get all unique properties for nodes with a specific label."""
    with driver.session(database=database) as session:
        query = f"MATCH (n:{label}) RETURN keys(n) as properties LIMIT 100"
        result = session.run(query)
        all_props = set()
        for record in result:
            all_props.update(record["properties"])
        return list(all_props)


def get_categorical_values(driver, database: str, label: str, property_name: str, max_distinct: int = 50) -> Tuple[List[Tuple], int]:
    """Get distinct values for a property if it appears to be categorical."""
    with driver.session(database=database) as session:
        query = f"""
        MATCH (n:{label})
        WHERE n.{property_name} IS NOT NULL
        RETURN DISTINCT n.{property_name} as value, count(*) as count
        ORDER BY count DESC
        LIMIT {max_distinct}
        """
        result = session.run(query)
        values = [(record["value"], record["count"]) for record in result]
        
        # Check if we likely have all distinct values
        total_query = f"""
        MATCH (n:{label})
        WHERE n.{property_name} IS NOT NULL
        RETURN count(DISTINCT n.{property_name}) as distinct_count
        """
        distinct_result = session.run(total_query)
        distinct_count = distinct_result.single()["distinct_count"]
        
        return values, distinct_count


def get_relationships_for_label(driver, database: str, label: str) -> Dict[str, List]:
    """Get all relationship types connected to nodes with a specific label."""
    with driver.session(database=database) as session:
        # Outgoing relationships
        out_query = f"""
        MATCH (n:{label})-[r]->()
        RETURN DISTINCT type(r) as rel_type, labels(endNode(r)) as target_labels
        """
        out_result = session.run(out_query)
        outgoing = [(record["rel_type"], record["target_labels"]) for record in out_result]
        
        # Incoming relationships
        in_query = f"""
        MATCH ()-[r]->(n:{label})
        RETURN DISTINCT type(r) as rel_type, labels(startNode(r)) as source_labels
        """
        in_result = session.run(in_query)
        incoming = [(record["rel_type"], record["source_labels"]) for record in in_result]
        
        return {"outgoing": outgoing, "incoming": incoming}


def analyze_node_type(driver, database: str, label: str, verbose: bool = False) -> Dict[str, Any]:
    """Comprehensive analysis of a node type."""
    if verbose:
        print(f"\n=== Analyzing {label} nodes ===")
    
    analysis = {
        "label": label,
        "count": get_node_count(driver, database, label),
        "properties": get_all_properties_for_label(driver, database, label),
        "samples": get_sample_nodes(driver, database, label),
        "relationships": get_relationships_for_label(driver, database, label),
        "categorical_properties": {}
    }
    
    # Analyze properties that might be categorical
    for prop in analysis["properties"]:
        # Skip properties that are likely not categorical
        if any(skip in prop.lower() for skip in ["id", "timestamp", "embedding", "text", "content", "description", "summary", "url"]):
            continue
            
        values, distinct_count = get_categorical_values(driver, database, label, prop)
        if distinct_count <= 20:  # Likely categorical if <= 20 distinct values
            analysis["categorical_properties"][prop] = {
                "values": values,
                "distinct_count": distinct_count
            }
    
    return analysis


def main():
    """Main analysis function."""
    parser = argparse.ArgumentParser(description="Analyze Neo4j node types for a podcast database")
    parser.add_argument("--podcast", "-p", required=True, help="Podcast name or ID")
    parser.add_argument("--output", "-o", help="Output file path (default: neo4j_node_analysis_<podcast>.json)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--format", choices=["json", "summary"], default="json", 
                       help="Output format (default: json)")
    
    args = parser.parse_args()
    
    try:
        # Load podcast configuration
        if args.verbose:
            print(f"Loading configuration for podcast: {args.podcast}")
        
        podcast_config = load_podcast_config(args.podcast)
        podcast_id = podcast_config['id']
        podcast_name = podcast_config['name']
        
        # Get database connection details
        db_config = podcast_config.get('database', {})
        uri = db_config.get('uri', 'neo4j://localhost:7687')
        password = db_config.get('neo4j_password', 'password')
        database_name = db_config.get('database_name', 'neo4j')
        
        if args.verbose:
            print(f"\nConnecting to {podcast_name} database")
            print(f"URI: {uri}")
            print(f"Database: {database_name}")
        
        # Create driver
        driver = GraphDatabase.driver(uri, auth=("neo4j", password))
        
        try:
            # Verify connection
            driver.verify_connectivity()
            print(f"Successfully connected to {podcast_name} Neo4j database")
            
            # Get all node labels
            labels = get_all_node_labels(driver, database_name)
            print(f"\nFound {len(labels)} node types: {labels}")
            
            # Analyze each node type
            analyses = {}
            for label in labels:
                analyses[label] = analyze_node_type(driver, database_name, label, args.verbose)
            
            # Determine output file
            if args.output:
                output_file = args.output
            else:
                output_file = f"neo4j_node_analysis_{podcast_id}.json"
            
            # Save results
            if args.format == "json":
                with open(output_file, "w") as f:
                    json.dump(analyses, f, indent=2, default=str)
                print(f"\n\nAnalysis complete! Results saved to {output_file}")
            
            # Print summary
            print(f"\n=== SUMMARY for {podcast_name} ===")
            for label, analysis in analyses.items():
                print(f"\n{label}:")
                print(f"  - Count: {analysis['count']}")
                print(f"  - Properties: {len(analysis['properties'])}")
                print(f"  - Categorical properties: {list(analysis['categorical_properties'].keys())}")
                if analysis['relationships']['outgoing']:
                    print(f"  - Outgoing relationships: {[r[0] for r in analysis['relationships']['outgoing']]}")
                if analysis['relationships']['incoming']:
                    print(f"  - Incoming relationships: {[r[0] for r in analysis['relationships']['incoming']]}")
            
            # If summary format requested, don't save JSON
            if args.format == "summary":
                print("\n(Summary format selected - no JSON file created)")
            
        finally:
            driver.close()
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()