"""Script to check if embeddings exist in the Neo4j databases."""

from neo4j import GraphDatabase
import yaml
from pathlib import Path

def check_embeddings(uri, database, auth):
    """Check if embeddings exist in a specific database."""
    driver = GraphDatabase.driver(uri, auth=auth)
    
    try:
        with driver.session(database=database) as session:
            # Count total MeaningfulUnit nodes
            total_result = session.run(
                "MATCH (m:MeaningfulUnit) RETURN count(m) as total"
            )
            total_count = total_result.single()["total"]
            
            # Count nodes with embeddings
            embedding_result = session.run(
                "MATCH (m:MeaningfulUnit) WHERE m.embedding IS NOT NULL RETURN count(m) as with_embeddings"
            )
            embedding_count = embedding_result.single()["with_embeddings"]
            
            # Check vector index
            index_result = session.run(
                "SHOW INDEXES WHERE name = 'meaningfulUnitEmbeddings'"
            )
            has_index = len(list(index_result)) > 0
            
            # Get sample embedding dimensions
            sample_result = session.run(
                "MATCH (m:MeaningfulUnit) WHERE m.embedding IS NOT NULL "
                "RETURN size(m.embedding) as dimensions LIMIT 1"
            )
            sample = sample_result.single()
            dimensions = sample["dimensions"] if sample else 0
            
            return {
                "total_nodes": total_count,
                "nodes_with_embeddings": embedding_count,
                "has_vector_index": has_index,
                "embedding_dimensions": dimensions,
                "percentage": (embedding_count / total_count * 100) if total_count > 0 else 0
            }
    finally:
        driver.close()

def main():
    # Read podcast configuration
    config_path = Path(__file__).parent.parent.parent.parent / "seeding_pipeline" / "config" / "podcasts.yaml"
    
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
    
    print("Checking embeddings in Neo4j databases...\n")
    
    for podcast in config.get('podcasts', []):
        if not podcast.get('enabled', False):
            continue
            
        name = podcast.get('name', 'Unknown')
        uri = podcast.get('database', {}).get('uri', 'bolt://localhost:7687')
        database_name = podcast.get('database', {}).get('database_name', 'neo4j')
        
        print(f"Podcast: {name}")
        print(f"Database: {database_name} at {uri}")
        
        try:
            # Try the configured database name first, then fall back to default
            try:
                results = check_embeddings(uri, database_name, ("neo4j", "password"))
            except Exception as e:
                if "DatabaseNotFound" in str(e) and database_name != "neo4j":
                    print(f"  Database '{database_name}' not found, trying default 'neo4j' database...")
                    results = check_embeddings(uri, "neo4j", ("neo4j", "password"))
                else:
                    raise
            
            print(f"  Total MeaningfulUnit nodes: {results['total_nodes']}")
            print(f"  Nodes with embeddings: {results['nodes_with_embeddings']} ({results['percentage']:.1f}%)")
            print(f"  Vector index exists: {results['has_vector_index']}")
            print(f"  Embedding dimensions: {results['embedding_dimensions']}")
            
        except Exception as e:
            print(f"  Error: {str(e)}")
        
        print()

if __name__ == "__main__":
    main()