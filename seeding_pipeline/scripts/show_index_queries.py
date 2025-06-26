#!/usr/bin/env python3
"""
Show the Cypher queries needed to recreate all indexes and constraints.

This script outputs the exact Cypher queries you can run manually in Neo4j Browser
or cypher-shell to recreate the schema.

Usage:
    python scripts/show_index_queries.py
"""

import click


def get_constraint_queries():
    """Return list of constraint creation queries."""
    return [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Podcast) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Episode) REQUIRE e.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (m:MeaningfulUnit) REQUIRE m.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (en:Entity) REQUIRE en.id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE"
    ]


def get_index_queries():
    """Return list of index creation queries."""
    return [
        "CREATE INDEX IF NOT EXISTS FOR (p:Podcast) ON (p.title)",
        "CREATE INDEX IF NOT EXISTS FOR (e:Episode) ON (e.title)",
        "CREATE INDEX IF NOT EXISTS FOR (e:Episode) ON (e.published_date)",
        "CREATE INDEX IF NOT EXISTS FOR (e:Episode) ON (e.youtube_url)",
        "CREATE INDEX IF NOT EXISTS FOR (m:MeaningfulUnit) ON (m.start_time)",
        "CREATE INDEX IF NOT EXISTS FOR (m:MeaningfulUnit) ON (m.primary_speaker)",
        "CREATE INDEX IF NOT EXISTS FOR (en:Entity) ON (en.name)",
        "CREATE INDEX IF NOT EXISTS FOR (en:Entity) ON (en.type)",
        "CREATE INDEX IF NOT EXISTS FOR ()-[r:MENTIONED_IN]-() ON (r.confidence)",
        "CREATE VECTOR INDEX meaningfulUnitEmbeddings IF NOT EXISTS FOR (m:MeaningfulUnit) ON m.embedding OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}"
    ]


@click.command()
@click.option('--format', type=click.Choice(['plain', 'cypher-shell', 'browser']), default='plain',
              help='Output format: plain (default), cypher-shell (with semicolons), or browser (with comments)')
def main(format):
    """Show Cypher queries to recreate Neo4j indexes and constraints."""
    
    print("\n" + "="*80)
    print("NEO4J INDEX CREATION QUERIES")
    print("="*80 + "\n")
    
    constraints = get_constraint_queries()
    indexes = get_index_queries()
    
    if format == 'browser':
        print("// Copy and paste these queries into Neo4j Browser")
        print("// Run them one at a time or all together\n")
    
    print("-- CONSTRAINTS (for uniqueness) --")
    if format == 'browser':
        print("// These ensure unique IDs for each node type\n")
    
    for query in constraints:
        if format == 'cypher-shell':
            print(f"{query};")
        else:
            print(query)
    
    print("\n-- INDEXES (for performance) --")
    if format == 'browser':
        print("// These speed up common queries and lookups\n")
    
    for i, query in enumerate(indexes):
        if "VECTOR INDEX" in query and format == 'browser':
            print("// Vector index for semantic similarity search (requires Neo4j 5.11+)")
            print("// This enables finding similar content based on embeddings")
        
        if format == 'cypher-shell':
            print(f"{query};")
        else:
            print(query)
    
    if format == 'plain':
        print("\n-- NOTES --")
        print("- Run these queries in Neo4j Browser or cypher-shell")
        print("- The 'IF NOT EXISTS' clause makes them safe to run multiple times")
        print("- Vector index requires Neo4j 5.11 or later")
        print("- Constraints automatically create indexes for the constrained properties")
    elif format == 'cypher-shell':
        print("\n// To run in cypher-shell:")
        print("// cat <this_output> | cypher-shell -u <username> -p <password>")
    elif format == 'browser':
        print("\n// All queries use 'IF NOT EXISTS' so they're safe to run multiple times")
        print("// The vector index will be skipped if your Neo4j version < 5.11")


if __name__ == "__main__":
    main()