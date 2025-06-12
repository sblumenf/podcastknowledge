"""Missing link analysis for knowledge discovery.

This module identifies entities that should potentially be connected
but currently have no direct relationship in the knowledge graph.
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


def find_missing_links(new_entities: List[str], session) -> List[Dict[str, Any]]:
    """Find potentially valuable connections for new entities.
    
    Identifies existing entities that:
    1. Have high individual frequency
    2. Are of the same type as new entities
    3. Never co-occur with the new entities
    
    Args:
        new_entities: List of newly added entity names
        session: Neo4j session
        
    Returns:
        List of missing link suggestions with scores
    """
    if not new_entities:
        return []
    
    missing_links = []
    
    for new_entity in new_entities:
        # Get type and frequency of new entity
        entity_info_query = """
        MATCH (e)-[:MENTIONS]->(entity)
        WHERE entity.name = $entity_name
        WITH entity, labels(entity) as entity_labels, COUNT(DISTINCT e) as frequency
        RETURN entity_labels, frequency
        """
        
        try:
            result = session.run(entity_info_query, entity_name=new_entity)
            record = result.single()
            
            if not record:
                continue
            
            entity_labels = record["entity_labels"]
            new_entity_frequency = record["frequency"]
            
            # Skip if entity is too rare
            if new_entity_frequency < 2:
                continue
            
            # Find high-frequency entities of same type that never co-occur
            find_unconnected_query = """
            // Find entities of same type with high frequency
            MATCH (e:Episode)-[:MENTIONS]->(other)
            WHERE $label IN labels(other)
            AND other.name <> $entity_name
            WITH other.name as other_name, COUNT(DISTINCT e) as other_frequency
            WHERE other_frequency >= $min_frequency
            
            // Check if they ever co-occur
            OPTIONAL MATCH (cooccur:Episode)-[:MENTIONS]->(entity1),
                          (cooccur)-[:MENTIONS]->(entity2)
            WHERE entity1.name = $entity_name
            AND entity2.name = other_name
            WITH other_name, other_frequency, COUNT(cooccur) as cooccurrence_count
            WHERE cooccurrence_count = 0
            
            RETURN other_name, other_frequency
            ORDER BY other_frequency DESC
            LIMIT 10
            """
            
            # Use first label (primary type) for matching
            primary_label = entity_labels[0] if entity_labels else "Entity"
            
            result = session.run(
                find_unconnected_query,
                entity_name=new_entity,
                label=primary_label,
                min_frequency=max(2, new_entity_frequency // 2)
            )
            
            for record in result:
                other_entity = record["other_name"]
                other_frequency = record["other_frequency"]
                
                # Calculate connection potential score
                score = calculate_connection_potential(
                    new_entity, new_entity_frequency,
                    other_entity, other_frequency,
                    session
                )
                
                if score > 0.3:  # Threshold for meaningful connections
                    # Generate connection suggestion
                    suggestion = generate_connection_topic(
                        new_entity, other_entity, primary_label
                    )
                    
                    missing_links.append({
                        "entity1": new_entity,
                        "entity2": other_entity,
                        "entity_type": primary_label,
                        "connection_score": score,
                        "entity1_frequency": new_entity_frequency,
                        "entity2_frequency": other_frequency,
                        "suggested_topic": suggestion
                    })
            
        except Exception as e:
            logger.error(f"Error finding missing links for {new_entity}: {e}")
    
    # Sort by connection score
    missing_links.sort(key=lambda x: x["connection_score"], reverse=True)
    
    return missing_links


def calculate_connection_potential(
    entity1: str, freq1: int,
    entity2: str, freq2: int,
    session
) -> float:
    """Calculate the potential value of connecting two entities.
    
    Score based on:
    - Entity frequencies (higher is better)
    - Shared context (topics, other entities)
    - Semantic similarity (if embeddings available)
    
    Args:
        entity1: First entity name
        freq1: Frequency of first entity
        entity2: Second entity name
        freq2: Frequency of second entity
        session: Neo4j session
        
    Returns:
        Connection potential score between 0 and 1
    """
    # Base score from frequencies
    freq_score = min(freq1, freq2) / max(freq1, freq2)
    
    # Check for shared context
    shared_context_query = """
    // Find shared topics
    MATCH (e1:Episode)-[:MENTIONS]->(entity1)
    WHERE entity1.name = $entity1
    MATCH (e1)-[:HAS_TOPIC]->(t1:Topic)
    WITH COLLECT(DISTINCT t1.name) as topics1
    
    MATCH (e2:Episode)-[:MENTIONS]->(entity2)
    WHERE entity2.name = $entity2
    MATCH (e2)-[:HAS_TOPIC]->(t2:Topic)
    WITH topics1, COLLECT(DISTINCT t2.name) as topics2
    
    // Calculate overlap
    WITH topics1, topics2,
         [t IN topics1 WHERE t IN topics2] as shared_topics
    
    // Find shared entities (excluding the two we're checking)
    MATCH (e3:Episode)-[:MENTIONS]->(entity1)
    WHERE entity1.name = $entity1
    MATCH (e3)-[:MENTIONS]->(other1)
    WHERE other1.name NOT IN [$entity1, $entity2]
    WITH shared_topics, COLLECT(DISTINCT other1.name) as entities1
    
    MATCH (e4:Episode)-[:MENTIONS]->(entity2)
    WHERE entity2.name = $entity2
    MATCH (e4)-[:MENTIONS]->(other2)
    WHERE other2.name NOT IN [$entity1, $entity2]
    WITH shared_topics, entities1, COLLECT(DISTINCT other2.name) as entities2
    
    WITH shared_topics,
         [e IN entities1 WHERE e IN entities2] as shared_entities
    
    RETURN SIZE(shared_topics) as shared_topic_count,
           SIZE(shared_entities) as shared_entity_count
    """
    
    try:
        result = session.run(
            shared_context_query,
            entity1=entity1,
            entity2=entity2
        )
        
        record = result.single()
        if record:
            shared_topics = record["shared_topic_count"]
            shared_entities = record["shared_entity_count"]
            
            # Context score (normalized)
            context_score = min(1.0, (shared_topics + shared_entities) / 10)
        else:
            context_score = 0.0
            
    except Exception as e:
        logger.error(f"Error calculating shared context: {e}")
        context_score = 0.0
    
    # Check for semantic similarity if embeddings exist
    similarity_score = get_semantic_similarity(entity1, entity2, session)
    
    # Combine scores with weights
    final_score = (
        0.3 * freq_score +
        0.4 * context_score +
        0.3 * similarity_score
    )
    
    return min(1.0, max(0.0, final_score))


def get_semantic_similarity(entity1: str, entity2: str, session) -> float:
    """Get semantic similarity between entities using embeddings if available.
    
    Args:
        entity1: First entity name
        entity2: Second entity name
        session: Neo4j session
        
    Returns:
        Similarity score between 0 and 1, or 0.5 if embeddings not available
    """
    # Check if entities have embeddings
    query = """
    MATCH (e1) WHERE e1.name = $entity1
    MATCH (e2) WHERE e2.name = $entity2
    WHERE e1.embedding IS NOT NULL AND e2.embedding IS NOT NULL
    RETURN gds.similarity.cosine(e1.embedding, e2.embedding) as similarity
    """
    
    try:
        result = session.run(query, entity1=entity1, entity2=entity2)
        record = result.single()
        
        if record and record["similarity"] is not None:
            # Convert cosine similarity to 0-1 range
            return (record["similarity"] + 1) / 2
        else:
            # No embeddings available, return neutral score
            return 0.5
            
    except Exception as e:
        # GDS might not be installed or embeddings not available
        logger.debug(f"Could not calculate semantic similarity: {e}")
        return 0.5


def generate_connection_topic(entity1: str, entity2: str, entity_type: str) -> str:
    """Generate a suggested topic that could connect two entities.
    
    Args:
        entity1: First entity name
        entity2: Second entity name
        entity_type: Type of entities (Person, Concept, etc.)
        
    Returns:
        Suggested connection topic
    """
    # Simple heuristic-based suggestions
    if entity_type == "Person":
        suggestions = [
            f"Collaboration between {entity1} and {entity2}",
            f"Comparing approaches of {entity1} and {entity2}",
            f"Interview with both {entity1} and {entity2}",
            f"How {entity1} influenced {entity2}'s work"
        ]
    elif entity_type == "Concept":
        suggestions = [
            f"Relationship between {entity1} and {entity2}",
            f"How {entity1} affects {entity2}",
            f"Integrating {entity1} with {entity2}",
            f"From {entity1} to {entity2}: A deep dive"
        ]
    elif entity_type == "Technology":
        suggestions = [
            f"Using {entity1} with {entity2}",
            f"Migrating from {entity1} to {entity2}",
            f"Comparing {entity1} and {entity2}",
            f"Best practices for {entity1} and {entity2}"
        ]
    else:
        suggestions = [
            f"Exploring {entity1} and {entity2} together",
            f"The connection between {entity1} and {entity2}",
            f"Understanding {entity1} through {entity2}",
            f"Why {entity1} matters for {entity2}"
        ]
    
    # Return first suggestion (could be randomized)
    return suggestions[0]


def create_missing_link_node(link_data: Dict[str, Any], session) -> bool:
    """Create or update a MissingLink node in Neo4j.
    
    Args:
        link_data: Dictionary with link information
        session: Neo4j session
        
    Returns:
        True if successful, False otherwise
    """
    # Create unique identifier
    link_id = f"{link_data['entity1']}||{link_data['entity2']}"
    
    query = """
    MERGE (link:MissingLink {id: $link_id})
    SET link.entity1 = $entity1,
        link.entity2 = $entity2,
        link.entity_type = $entity_type,
        link.connection_score = $score,
        link.suggested_topic = $topic,
        link.entity1_frequency = $freq1,
        link.entity2_frequency = $freq2,
        link.last_updated = datetime()
    RETURN link
    """
    
    try:
        result = session.run(
            query,
            link_id=link_id,
            entity1=link_data["entity1"],
            entity2=link_data["entity2"],
            entity_type=link_data["entity_type"],
            score=link_data["connection_score"],
            topic=link_data["suggested_topic"],
            freq1=link_data["entity1_frequency"],
            freq2=link_data["entity2_frequency"]
        )
        
        if result.single():
            logger.debug(f"Created/updated missing link: {link_data['entity1']} <-> {link_data['entity2']}")
            return True
        return False
        
    except Exception as e:
        logger.error(f"Error creating missing link node: {e}")
        return False


def update_existing_links(session) -> int:
    """Update or remove MissingLink nodes if entities are now connected.
    
    Returns:
        Number of links updated/removed
    """
    query = """
    MATCH (link:MissingLink)
    // Check if entities now co-occur
    OPTIONAL MATCH (e:Episode)-[:MENTIONS]->(entity1),
                  (e)-[:MENTIONS]->(entity2)
    WHERE entity1.name = link.entity1
    AND entity2.name = link.entity2
    WITH link, COUNT(e) as cooccurrence_count
    WHERE cooccurrence_count > 0
    DELETE link
    RETURN COUNT(link) as deleted_count
    """
    
    try:
        result = session.run(query)
        record = result.single()
        deleted = record["deleted_count"] if record else 0
        
        if deleted > 0:
            logger.info(f"Removed {deleted} missing links that are now connected")
        
        return deleted
        
    except Exception as e:
        logger.error(f"Error updating existing links: {e}")
        return 0


def run_missing_link_analysis(episode_id: str, session) -> Dict[str, Any]:
    """Run missing link analysis for a newly added episode.
    
    Args:
        episode_id: ID of the newly added episode
        session: Neo4j session
        
    Returns:
        Missing link analysis results
    """
    results = {
        "new_entities_checked": 0,
        "missing_links_found": 0,
        "high_score_links": [],
        "links_removed": 0,
        "errors": []
    }
    
    # Get entities from the new episode
    query = """
    MATCH (e:Episode {id: $episode_id})-[:MENTIONS]->(entity)
    RETURN COLLECT(DISTINCT entity.name) as entities
    """
    
    try:
        result = session.run(query, episode_id=episode_id)
        record = result.single()
        
        if not record or not record["entities"]:
            logger.warning(f"No entities found for episode {episode_id}")
            return results
        
        new_entities = record["entities"]
        results["new_entities_checked"] = len(new_entities)
        
        # Find missing links for new entities
        missing_links = find_missing_links(new_entities, session)
        
        # Create nodes for significant missing links
        for link in missing_links:
            if create_missing_link_node(link, session):
                results["missing_links_found"] += 1
                
                # Track high-score links
                if link["connection_score"] > 0.7:
                    results["high_score_links"].append({
                        "entities": f"{link['entity1']} <-> {link['entity2']}",
                        "type": link["entity_type"],
                        "score": link["connection_score"],
                        "suggestion": link["suggested_topic"]
                    })
        
        # Update existing links
        results["links_removed"] = update_existing_links(session)
        
        logger.info(f"Missing link analysis complete: {results['missing_links_found']} new links found")
        
    except Exception as e:
        logger.error(f"Error in missing link analysis: {e}")
        results["errors"].append(str(e))
    
    return results