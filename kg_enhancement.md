# Knowledge Graph Enhancement Plan for Podcast Knowledge System

## Overview
This plan builds on the existing `podcast_knowledge_system_complete.py` script to create a more powerful knowledge graph that preserves the schema-free nature of podcast content while adding advanced relationship types, knowledge expansion, and semantic clustering capabilities.

## Table of Contents
1. [Enhance Semantic Relationship Types](#1-enhance-semantic-relationship-types)
2. [Knowledge Expansion and Entity Resolution](#2-knowledge-expansion-and-entity-resolution)
3. [Cross-Episode Relationship Building](#3-cross-episode-relationship-building)
4. [Graph Algorithms for Pattern Discovery](#4-graph-algorithms-for-pattern-discovery)
5. [Semantic Clustering with Vector Embeddings](#5-semantic-clustering-with-vector-embeddings)
6. [Integration with Existing System](#6-integration-with-existing-system)

## 1. Enhance Semantic Relationship Types

```python
def enhance_knowledge_relationships(neo4j_driver, llm_client):
    with neo4j_driver.session() as session:
        # Create semantic relationships between insights
        session.run("""
        MATCH (i1:Insight), (i2:Insight)
        WHERE i1.id <> i2.id AND i1.category = i2.category
        WITH i1, i2, apoc.text.similarity(i1.title, i2.title) AS similarity
        WHERE similarity > 0.5
        MERGE (i1)-[:SIMILAR_CONCEPT {strength: similarity}]->(i2)
        """)
        
        # Add temporal relationships between episodes in a series
        session.run("""
        MATCH (e1:Episode), (e2:Episode)
        WHERE e1.podcast_id = e2.podcast_id 
          AND datetime(e1.published_date) < datetime(e2.published_date)
        WITH e1, e2, duration.between(datetime(e1.published_date), datetime(e2.published_date)) as time_between
        WHERE time_between.days < 90  // Within 3 months
        MERGE (e1)-[:PRECEDED_BY {days_apart: time_between.days}]->(e2)
        """)
        
        # Connect entities mentioned together in segments (co-occurrence)
        session.run("""
        MATCH (s:Segment)<-[:HAS_SEGMENT]-(e:Episode)
        MATCH (ent1:Entity)-[:MENTIONED_IN]->(e)
        MATCH (ent2:Entity)-[:MENTIONED_IN]->(e)
        WHERE ent1.id <> ent2.id AND toLower(s.text) CONTAINS toLower(ent1.name) 
          AND toLower(s.text) CONTAINS toLower(ent2.name)
        MERGE (ent1)-[r:MENTIONED_WITH]->(ent2)
        ON CREATE SET r.count = 1
        ON MATCH SET r.count = r.count + 1
        """)
        
        # Create LLM-inferred CONTRADICTS/SUPPORTS/EXPANDS_ON relationships (sample 100 pairs)
        result = session.run("""
        MATCH (i1:Insight), (i2:Insight)
        WHERE i1.id <> i2.id AND i1.category = i2.category
          AND NOT (i1)-[:CONTRADICTS|SUPPORTS|EXPANDS_ON]-(i2)
        RETURN i1.id as id1, i1.title as title1, i1.description as desc1,
               i2.id as id2, i2.title as title2, i2.description as desc2
        LIMIT 100
        """)
        
        for record in result:
            prompt = f"""
            Analyze these two insights and determine their relationship:
            
            Insight 1: {record['title1']} - {record['desc1']}
            Insight 2: {record['title2']} - {record['desc2']}
            
            What is the relationship between these insights? Choose exactly one:
            - SUPPORTS (insight 2 provides evidence for or enhances insight 1)
            - CONTRADICTS (insight 2 opposes or challenges insight 1)
            - EXPANDS_ON (insight 2 adds more detail or context to insight 1)
            - UNRELATED (no significant relationship)
            
            Return only one word: SUPPORTS, CONTRADICTS, EXPANDS_ON, or UNRELATED
            """
            
            response = llm_client.invoke(prompt)
            relationship = response.content.strip().upper()
            
            if relationship in ["SUPPORTS", "CONTRADICTS", "EXPANDS_ON"]:
                session.run(f"""
                MATCH (i1:Insight {{id: $id1}}), (i2:Insight {{id: $id2}})
                MERGE (i1)-[:{relationship}]->(i2)
                """, {"id1": record["id1"], "id2": record["id2"]})
```

## 2. Knowledge Expansion and Entity Resolution

```python
def expand_knowledge_graph(neo4j_driver, llm_client, embedding_client):
    # Entity resolution - merge duplicate entities across episodes
    with neo4j_driver.session() as session:
        # Find potential duplicate entities with similar names
        result = session.run("""
        MATCH (e1:Entity), (e2:Entity)
        WHERE e1.id <> e2.id AND e1.type = e2.type
          AND apoc.text.fuzzyMatch(e1.name, e2.name) > 0.8
        RETURN e1.id as id1, e1.name as name1, e2.id as id2, e2.name as name2
        """)
        
        for record in result:
            # Use LLM to confirm if entities are indeed the same
            prompt = f"""
            Are these two entities the same? 
            Entity 1: {record['name1']} ({record['id1']})
            Entity 2: {record['name2']} ({record['id2']})
            
            Answer with YES or NO only.
            """
            
            response = llm_client.invoke(prompt)
            if "YES" in response.content.upper():
                # Merge the entities
                session.run("""
                MATCH (e1:Entity {id: $id1}), (e2:Entity {id: $id2})
                CALL apoc.refactor.mergeNodes([e1, e2], {
                    properties: {
                        name: 'combine',
                        description: 'combine',
                        frequency: 'sum',
                        importance: 'max'
                    },
                    mergeRels: true
                })
                YIELD node
                RETURN node
                """, {"id1": record["id1"], "id2": record["id2"]})
        
        # Add external knowledge enrichment for key entities (top 20 by importance)
        top_entities = session.run("""
        MATCH (e:Entity)
        RETURN e.id as id, e.name as name, e.type as type
        ORDER BY e.importance DESC
        LIMIT 20
        """)
        
        for entity in top_entities:
            # Fetch external knowledge about entity
            prompt = f"""
            Give me a comprehensive but concise description of {entity['name']} ({entity['type']}).
            Include key facts, significance, and relationships to other concepts.
            Keep it under 250 words and focus on objective information.
            """
            
            enrichment = llm_client.invoke(prompt)
            
            # Update entity with enriched knowledge
            session.run("""
            MATCH (e:Entity {id: $id})
            SET e.enriched_description = $description,
                e.knowledge_enriched = true
            """, {"id": entity["id"], "description": enrichment.content})
            
            # Generate embedding for the enriched description
            if embedding_client:
                enriched_embedding = generate_embeddings(enrichment.content, embedding_client)
                if enriched_embedding:
                    session.run("""
                    MATCH (e:Entity {id: $id})
                    SET e.enriched_embedding = $embedding
                    """, {"id": entity["id"], "embedding": enriched_embedding})
```

## 3. Cross-Episode Relationship Building

```python
def build_cross_episode_relationships(neo4j_driver, llm_client):
    with neo4j_driver.session() as session:
        # Track topic evolution across episodes
        result = session.run("""
        MATCH (e:Entity)-[:MENTIONED_IN]->(ep:Episode)
        WITH e.name as entity_name, e.type as entity_type, 
             collect(distinct {
                 id: ep.id,
                 title: ep.title, 
                 date: ep.published_date
             }) ORDER BY ep.published_date as appearances
        WHERE size(appearances) > 1
        RETURN entity_name, entity_type, appearances
        ORDER BY size(appearances) DESC
        LIMIT 10
        """)
        
        for record in result:
            entity_name = record["entity_name"]
            appearances = record["appearances"]
            
            # For consecutive episode pairs, analyze how the entity's context evolved
            for i in range(len(appearances)-1):
                ep1 = appearances[i]
                ep2 = appearances[i+1]
                
                # Get contexts from both episodes
                contexts_result = session.run("""
                MATCH (ep1:Episode {id: $ep1_id})-[:HAS_SEGMENT]->(s1:Segment)
                WHERE toLower(s1.text) CONTAINS toLower($entity_name)
                WITH collect(s1.text) as context1
                
                MATCH (ep2:Episode {id: $ep2_id})-[:HAS_SEGMENT]->(s2:Segment)
                WHERE toLower(s2.text) CONTAINS toLower($entity_name)
                
                RETURN context1, collect(s2.text) as context2
                """, {"entity_name": entity_name, "ep1_id": ep1["id"], "ep2_id": ep2["id"]})
                
                if not contexts_result.peek():
                    continue
                    
                contexts = contexts_result.single()
                
                # Use LLM to detect conceptual shift or evolution
                prompt = f"""
                Analyze how the discussion of '{entity_name}' evolved between these episodes:
                
                Episode 1 '{ep1["title"]}' contexts:
                {contexts['context1']}
                
                Episode 2 '{ep2["title"]}' contexts:
                {contexts['context2']}
                
                Did the understanding or discussion of this entity:
                1. EVOLVE - understanding developed or expanded
                2. SHIFT - conceptual direction changed
                3. CONTRADICT - later episode contradicted earlier episode
                4. CONSISTENT - no significant change in understanding
                
                Return only one word: EVOLVE, SHIFT, CONTRADICT, or CONSISTENT
                """
                
                response = llm_client.invoke(prompt)
                evolution_type = response.content.strip().upper()
                
                # Create appropriate relationship between episodes
                if evolution_type in ["EVOLVE", "SHIFT", "CONTRADICT"]:
                    session.run(f"""
                    MATCH (ep1:Episode {{id: $ep1_id}}), (ep2:Episode {{id: $ep2_id}})
                    MERGE (ep1)-[r:TOPIC_EVOLUTION {{
                        entity: $entity_name,
                        relation_type: $evolution_type
                    }}]->(ep2)
                    """, {
                        "ep1_id": ep1["id"], 
                        "ep2_id": ep2["id"],
                        "entity_name": entity_name,
                        "evolution_type": evolution_type
                    })
        
        # Connect insights across episodes by similarity
        session.run("""
        MATCH (i1:Insight)-[:FROM_EPISODE]->(ep1:Episode)
        MATCH (i2:Insight)-[:FROM_EPISODE]->(ep2:Episode)
        WHERE ep1.id <> ep2.id AND i1.category = i2.category
        WITH i1, i2, ep1, ep2,
             apoc.text.similarity(i1.title, i2.title) +
             apoc.text.similarity(i1.description, i2.description) as similarity
        WHERE similarity > 1.5
        MERGE (i1)-[:SIMILAR_INSIGHT {score: similarity}]->(i2)
        """)
```

## 4. Graph Algorithms for Pattern Discovery

```python
def apply_graph_algorithms(neo4j_driver):
    with neo4j_driver.session() as session:
        # Set up graph projections for algorithms
        session.run("""
        CALL gds.graph.project(
          'complete_knowledge_graph',
          ['Entity', 'Insight', 'Episode', 'Segment'],
          {
            MENTIONED_IN: {orientation: 'UNDIRECTED'},
            MENTIONED_WITH: {orientation: 'UNDIRECTED'},
            SIMILAR_CONCEPT: {orientation: 'UNDIRECTED'},
            CONTRADICTS: {orientation: 'UNDIRECTED'},
            SUPPORTS: {orientation: 'UNDIRECTED'},
            EXPANDS_ON: {orientation: 'UNDIRECTED'},
            HAS_INSIGHT: {orientation: 'UNDIRECTED'},
            HAS_SEGMENT: {orientation: 'UNDIRECTED'},
            SIMILAR_INSIGHT: {orientation: 'UNDIRECTED'},
            TOPIC_EVOLUTION: {orientation: 'NATURAL'}
          }
        )
        """)
        
        # Run PageRank to find key concepts (most influential nodes)
        session.run("""
        CALL gds.pageRank.write(
          'complete_knowledge_graph',
          {
            writeProperty: 'pagerank',
            maxIterations: 20,
            dampingFactor: 0.85
          }
        )
        """)
        
        # Run community detection to find topic clusters
        session.run("""
        CALL gds.louvain.write(
          'complete_knowledge_graph',
          {
            writeProperty: 'community',
            includeIntermediateCommunities: true
          }
        )
        """)
        
        # Find shortest paths between important concepts
        important_entities = session.run("""
        MATCH (e:Entity)
        WHERE e.pagerank > 0.01
        RETURN e.id as id, e.name as name
        ORDER BY e.pagerank DESC
        LIMIT 10
        """)
        
        entities = list(important_entities)
        
        # Find paths between top entities
        for i in range(len(entities)):
            for j in range(i+1, len(entities)):
                source = entities[i]
                target = entities[j]
                
                paths = session.run("""
                MATCH path = shortestPath((e1:Entity {id: $source_id})-[*..5]-(e2:Entity {id: $target_id}))
                RETURN [node IN nodes(path) | node.name] as node_names,
                       [rel IN relationships(path) | type(rel)] as rel_types
                """, {"source_id": source["id"], "target_id": target["id"]})
                
                if paths.peek():
                    path_data = paths.single()
                    # Create explicit CONNECTION relationships between key concepts
                    session.run("""
                    MATCH (e1:Entity {id: $source_id}), (e2:Entity {id: $target_id})
                    MERGE (e1)-[:KEY_CONNECTION {
                        path_length: size($path_nodes) - 2,
                        path_details: $path_nodes
                    }]->(e2)
                    """, {
                        "source_id": source["id"],
                        "target_id": target["id"],
                        "path_nodes": path_data["node_names"]
                    })
```

## 5. Semantic Clustering with Vector Embeddings

```python
def implement_semantic_clustering(neo4j_driver):
    with neo4j_driver.session() as session:
        # Create vector indexes if they don't exist
        session.run("""
        CREATE VECTOR INDEX insight_vector IF NOT EXISTS
        FOR (i:Insight) ON (i.embedding)
        OPTIONS {
          indexConfig: {
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine'
          }
        }
        """)
        
        session.run("""
        CREATE VECTOR INDEX entity_vector IF NOT EXISTS
        FOR (e:Entity) ON (e.embedding)
        OPTIONS {
          indexConfig: {
            `vector.dimensions`: 1536,
            `vector.similarity_function`: 'cosine'
          }
        }
        """)
        
        # Create semantic similarity connections between insights
        session.run("""
        MATCH (i1:Insight)
        WHERE i1.embedding IS NOT NULL
        CALL db.index.vector.queryNodes('insight_vector', 5, i1.embedding) 
        YIELD node as i2, score
        WHERE i1.id <> i2.id AND score > 0.8
        MERGE (i1)-[:SEMANTIC_SIMILARITY {score: score}]->(i2)
        """)
        
        # Create semantic similarity connections between entities
        session.run("""
        MATCH (e1:Entity)
        WHERE e1.embedding IS NOT NULL
        CALL db.index.vector.queryNodes('entity_vector', 5, e1.embedding) 
        YIELD node as e2, score
        WHERE e1.id <> e2.id AND score > 0.8
        MERGE (e1)-[:SEMANTIC_SIMILARITY {score: score}]->(e2)
        """)
        
        # Create topic clusters based on semantic similarity
        session.run("""
        CALL gds.graph.project(
          'semantic_graph',
          ['Insight', 'Entity'],
          {
            SEMANTIC_SIMILARITY: {
              orientation: 'UNDIRECTED',
              properties: ['score']
            }
          }
        )
        """)
        
        # Run label propagation to identify semantic clusters
        session.run("""
        CALL gds.labelPropagation.write(
          'semantic_graph',
          {
            writeProperty: 'semantic_cluster',
            relationshipWeightProperty: 'score'
          }
        )
        """)
        
        # Name the clusters based on common concepts
        cluster_results = session.run("""
        MATCH (n)
        WHERE n.semantic_cluster IS NOT NULL
        RETURN DISTINCT n.semantic_cluster as cluster_id, 
               collect(n.name) as member_names,
               collect(labels(n)[0]) as member_types
        """)
        
        for cluster in cluster_results:
            cluster_id = cluster["cluster_id"]
            member_names = cluster["member_names"]
            
            # Generate cluster name with LLM
            prompt = f"""
            Create a short (2-3 word) descriptive name for a topic cluster containing these concepts:
            {', '.join(member_names[:20])}
            
            The name should be concise and capture the common theme.
            Return only the name, nothing else.
            """
            
            cluster_name = llm_client.invoke(prompt).content.strip()
            
            # Store cluster name
            session.run("""
            MATCH (n)
            WHERE n.semantic_cluster = $cluster_id
            SET n.cluster_name = $cluster_name
            """, {"cluster_id": cluster_id, "cluster_name": cluster_name})
```

## 6. Integration with Existing System

```python
def collect_knowledge_graph_stats(neo4j_driver):
    """
    Collect statistics about the enhanced knowledge graph for verification.
    
    Args:
        neo4j_driver: Neo4j driver
        
    Returns:
        Dictionary with knowledge graph statistics
    """
    if not neo4j_driver:
        print("Neo4j driver not available. Cannot collect knowledge graph statistics.")
        return None
    
    stats = {}
    
    # Get database name
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    
    try:
        with neo4j_driver.session(database=database) as session:
            # Get node counts by type
            result = session.run("""
            MATCH (n)
            WITH labels(n)[0] as nodeType, count(n) as count
            RETURN nodeType, count
            ORDER BY count DESC
            """)
            
            node_counts = {record["nodeType"]: record["count"] for record in result}
            stats["node_counts"] = node_counts
            stats["total_nodes"] = sum(node_counts.values())
            
            # Get relationship counts by type
            result = session.run("""
            MATCH ()-[r]->()
            WITH type(r) as relType, count(r) as count
            RETURN relType, count
            ORDER BY count DESC
            """)
            
            rel_counts = {record["relType"]: record["count"] for record in result}
            stats["relationship_counts"] = rel_counts
            stats["total_relationships"] = sum(rel_counts.values())
            
            # Get semantic relationship counts
            semantic_rels = ["SIMILAR_CONCEPT", "CONTRADICTS", "SUPPORTS", "EXPANDS_ON", 
                            "MENTIONED_WITH", "SEMANTIC_SIMILARITY", "TOPIC_EVOLUTION", 
                            "KEY_CONNECTION"]
            
            semantic_rel_count = sum(rel_counts.get(rel, 0) for rel in semantic_rels)
            stats["semantic_relationship_count"] = semantic_rel_count
            
            # Get cluster counts
            result = session.run("""
            MATCH (n)
            WHERE n.semantic_cluster IS NOT NULL
            RETURN count(DISTINCT n.semantic_cluster) as cluster_count
            """)
            
            if result.peek():
                stats["semantic_cluster_count"] = result.single()["cluster_count"]
            else:
                stats["semantic_cluster_count"] = 0
            
            # Get cross-episode connections
            result = session.run("""
            MATCH ()-[r:TOPIC_EVOLUTION]->()
            RETURN count(r) as count
            """)
            
            if result.peek():
                stats["cross_episode_count"] = result.single()["count"]
            else:
                stats["cross_episode_count"] = 0
            
            # Get top entities by PageRank
            result = session.run("""
            MATCH (e:Entity)
            WHERE e.pagerank IS NOT NULL
            RETURN e.name as name, e.type as type, e.pagerank as score
            ORDER BY e.pagerank DESC
            LIMIT 10
            """)
            
            stats["top_entities"] = [{"name": record["name"], 
                                     "type": record["type"], 
                                     "pagerank": record["score"]} 
                                    for record in result]
            
            return stats
            
    except Exception as e:
        print(f"Error collecting knowledge graph statistics: {e}")
        return None

def enhance_knowledge_graph(podcast_info, results, neo4j_driver, llm_client, embedding_client):
    """
    Apply advanced knowledge graph enhancements to the extracted podcast knowledge.
    
    Args:
        podcast_info: Podcast information
        results: Results from processing episodes
        neo4j_driver: Neo4j driver
        llm_client: LLM client
        embedding_client: OpenAI client for embeddings
    """
    # Step 1: Basic knowledge is already in Neo4j from the original pipeline
    
    # Step 2: Enhance with semantic relationships
    print("Enhancing semantic relationships...")
    enhance_knowledge_relationships(neo4j_driver, llm_client)
    
    # Step 3: Expand knowledge and resolve duplicate entities
    print("Expanding knowledge and resolving entities...")
    expand_knowledge_graph(neo4j_driver, llm_client, embedding_client)
    
    # Step 4: Build cross-episode connections
    print("Building cross-episode relationships...")
    build_cross_episode_relationships(neo4j_driver, llm_client)
    
    # Step 5: Apply graph algorithms to discover patterns
    print("Applying graph algorithms for pattern discovery...")
    apply_graph_algorithms(neo4j_driver)
    
    # Step 6: Implement semantic clustering with vector embeddings
    print("Implementing semantic clustering...")
    implement_semantic_clustering(neo4j_driver)
    
    # Collect and display statistics for verification
    print("Collecting knowledge graph statistics...")
    stats = collect_knowledge_graph_stats(neo4j_driver)
    if stats:
        print("\nEnhanced Knowledge Graph Statistics:")
        print(f"Total Nodes: {stats['total_nodes']}")
        print(f"Total Relationships: {stats['total_relationships']}")
        print(f"Semantic Relationships: {stats['semantic_relationship_count']}")
        print(f"Topic Clusters: {stats['semantic_cluster_count']}")
        print(f"Cross-Episode Connections: {stats['cross_episode_count']}")
        
        print("\nTop Entities by Influence:")
        for i, entity in enumerate(stats["top_entities"][:5], 1):
            print(f"{i}. {entity['name']} ({entity['type']}): {entity['pagerank']:.4f}")
    
    return True
```

Then update the `run_knowledge_graph_pipeline` function to call this enhancement step after the initial knowledge graph is built:

```python
def run_knowledge_graph_pipeline(podcast_config, max_episodes=1, segmenter_config=None, use_large_context=True, enhance_graph=True):
    """
    Run the complete knowledge graph pipeline with optional enhancements.
    
    Args:
        podcast_config: Podcast configuration
        max_episodes: Maximum number of episodes to process
        segmenter_config: Configuration for the segmenter
        use_large_context: Whether to use 1M token window optimizations
        enhance_graph: Whether to apply advanced knowledge graph enhancements
        
    Returns:
        Processing results
    """
    # Initialize Neo4j
    neo4j_driver = connect_to_neo4j()
    if neo4j_driver:
        setup_neo4j_schema(neo4j_driver)
    
    # Fetch podcast feed
    podcast_info = fetch_podcast_feed(podcast_config, max_episodes)
    
    # Configure segmenter if needed
    if use_large_context and segmenter_config is None:
        # Create a default configuration optimized for large context models
        segmenter_config = {
            'min_segment_tokens': 150,
            'max_segment_tokens': 800,
            'use_gpu': True,
            'ad_detection_enabled': True,
            'use_semantic_boundaries': True
        }
    
    # Process episodes
    results = []
    for episode in podcast_info["episodes"]:
        result = process_podcast_episode(
            podcast_config, 
            episode, 
            segmenter_config,
            use_large_context=use_large_context
        )
        if result:
            results.append(result)
    
    # Apply knowledge graph enhancements if requested
    if enhance_graph and neo4j_driver and len(results) > 0:
        print("\nApplying knowledge graph enhancements...")
        enhance_knowledge_graph(
            podcast_info, 
            results, 
            neo4j_driver, 
            initialize_gemini_client(enable_large_context=True),
            initialize_embedding_model()
        )
    
    # Collect base statistics
    if neo4j_driver:
        # Use existing visualize_knowledge_graph function for base statistics
        base_stats = visualize_knowledge_graph(neo4j_driver)
        if base_stats:
            print("\nBase Knowledge Graph Statistics:")
            print(f"Total Nodes: {base_stats['stats']['nodeCount']}")
            print(f"Podcasts: {base_stats['stats']['podcastCount']}")
            print(f"Episodes: {base_stats['stats']['episodeCount']}")
            print(f"Segments: {base_stats['stats']['segmentCount']}")
            print(f"Insights: {base_stats['stats']['insightCount']}")
            print(f"Entities: {base_stats['stats']['entityCount']}")
    
    return results
```

## Example Usage

To use the enhanced knowledge graph functionality, modify your script's `main` function:

```python
if __name__ == "__main__":
    import argparse
    
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description="PodcastKnowledge: Enhanced Knowledge Graph System")
    parser.add_argument("--podcast", "-p", type=str, default="my-first-million", 
                        help="Podcast ID to process")
    parser.add_argument("--episodes", "-e", type=int, default=1, 
                        help="Number of episodes to process")
    parser.add_argument("--large-context", "-l", action="store_true", default=True,
                        help="Use 1M token context window optimizations (default: True)")
    parser.add_argument("--disable-large-context", "-d", action="store_true",
                        help="Disable 1M token context window optimizations")
    parser.add_argument("--enhance-graph", "-g", action="store_true", default=True,
                        help="Apply advanced knowledge graph enhancements (default: True)")
    parser.add_argument("--disable-enhancements", "-n", action="store_true",
                        help="Disable advanced knowledge graph enhancements")
    parser.add_argument("--min-tokens", type=int, default=150,
                        help="Minimum tokens per segment")
    parser.add_argument("--max-tokens", type=int, default=800,
                        help="Maximum tokens per segment")
    
    args = parser.parse_args()
    
    # Override large context if explicitly disabled
    if args.disable_large_context:
        args.large_context = False
        
    # Override graph enhancements if explicitly disabled
    if args.disable_enhancements:
        args.enhance_graph = False
    
    # ... rest of the existing main function ...
    
    # Process episodes with optional enhancements
    results = run_knowledge_graph_pipeline(
        podcast_config,
        max_episodes=args.episodes,
        segmenter_config=segmenter_config,
        use_large_context=args.large_context,
        enhance_graph=args.enhance_graph
    )
```

## Benefits of This Approach

1. **Schema-Free Knowledge Extraction**: Maintains the flexibility of the original system while adding powerful semantic structures

2. **Rich Semantic Relationships**: Adds meaningful relationship types that go beyond simple hierarchical connections

3. **Cross-Episode Knowledge Building**: Tracks how topics and concepts evolve across multiple episodes

4. **Entity Resolution and Knowledge Enrichment**: Consolidates duplicate entities and adds external knowledge

5. **Advanced Graph Algorithms**: Identifies key concepts, clusters, and pathways through the knowledge

6. **Semantic Clustering with Vector Embeddings**: Groups semantically similar content regardless of exact wording

This plan preserves the schema-free nature of your podcast knowledge extraction system while adding powerful semantic relationships, cross-episode connections, and graph analytics capabilities. The enhancements are applied after the initial knowledge graph is built, ensuring you maintain all the core functionality of your existing system.