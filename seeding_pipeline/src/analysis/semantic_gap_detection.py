"""Semantic gap detection for knowledge discovery using cluster embeddings.

This module identifies semantic gaps between clusters in the knowledge graph
by analyzing the distance between cluster centroids. It helps find unexplored
connections and potential bridges between semantically distinct topics.
"""

import logging
import numpy as np
from typing import List, Set, Dict, Tuple, Optional, Any
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors.
    
    Args:
        vec1: First embedding vector
        vec2: Second embedding vector
        
    Returns:
        Cosine similarity score between 0 and 1
    """
    if len(vec1) == 0 or len(vec2) == 0:
        return 0.0
    
    # Ensure numpy arrays
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    
    # Calculate cosine similarity
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    similarity = dot_product / (norm1 * norm2)
    
    # Ensure result is between 0 and 1
    return max(0.0, min(1.0, (similarity + 1) / 2))


def get_all_clusters(session) -> Dict[str, Dict[str, Any]]:
    """Fetch all clusters with their centroids from Neo4j.
    
    Args:
        session: Neo4j session
        
    Returns:
        Dictionary mapping cluster IDs to cluster data including centroids
    """
    query = """
    MATCH (c:Cluster)
    WHERE c.status = 'active' AND c.centroid IS NOT NULL
    RETURN c.id as cluster_id,
           c.label as label,
           c.member_count as member_count,
           c.centroid as centroid,
           c.created_timestamp as created_timestamp
    """
    
    clusters = {}
    try:
        result = session.run(query)
        
        for record in result:
            cluster_id = record["cluster_id"]
            clusters[cluster_id] = {
                "id": cluster_id,
                "label": record["label"],
                "member_count": record["member_count"],
                "centroid": np.array(record["centroid"]),
                "created_timestamp": record["created_timestamp"]
            }
        
        logger.info(f"Fetched {len(clusters)} clusters with centroids")
        
    except Exception as e:
        logger.error(f"Error fetching clusters: {e}")
    
    return clusters


def calculate_cluster_distances(clusters: Dict[str, Dict[str, Any]]) -> Dict[Tuple[str, str], float]:
    """Calculate pairwise distances between all clusters.
    
    Args:
        clusters: Dictionary of cluster data with centroids
        
    Returns:
        Dictionary mapping cluster ID pairs to their distance (1 - similarity)
    """
    distances = {}
    cluster_ids = list(clusters.keys())
    
    for i in range(len(cluster_ids)):
        for j in range(i + 1, len(cluster_ids)):
            id1, id2 = cluster_ids[i], cluster_ids[j]
            
            # Calculate cosine similarity
            similarity = cosine_similarity(
                clusters[id1]["centroid"],
                clusters[id2]["centroid"]
            )
            
            # Convert to distance (0 = identical, 1 = completely different)
            distance = 1.0 - similarity
            
            # Store with sorted IDs for consistency
            key = tuple(sorted([id1, id2]))
            distances[key] = distance
    
    logger.info(f"Calculated {len(distances)} pairwise cluster distances")
    return distances


def identify_semantic_gaps(
    distances: Dict[Tuple[str, str], float],
    clusters: Dict[str, Dict[str, Any]],
    gap_threshold_min: float = 0.3,
    gap_threshold_max: float = 0.7
) -> List[Dict[str, Any]]:
    """Identify cluster pairs that represent semantic gaps.
    
    Gaps are cluster pairs with moderate distance - not too similar (would be
    redundant) and not too different (would be unrelated).
    
    Args:
        distances: Pairwise cluster distances
        clusters: Cluster data
        gap_threshold_min: Minimum distance to be considered a gap
        gap_threshold_max: Maximum distance to be considered a gap
        
    Returns:
        List of gap candidates with scores
    """
    gaps = []
    
    for (id1, id2), distance in distances.items():
        # Check if distance is in the gap range
        if gap_threshold_min <= distance <= gap_threshold_max:
            # Calculate gap score (higher score for distances closer to middle of range)
            gap_center = (gap_threshold_min + gap_threshold_max) / 2
            gap_score = 1.0 - abs(distance - gap_center) / (gap_threshold_max - gap_threshold_min)
            
            gaps.append({
                "cluster1_id": id1,
                "cluster2_id": id2,
                "cluster1_label": clusters[id1]["label"],
                "cluster2_label": clusters[id2]["label"],
                "distance": distance,
                "similarity": 1.0 - distance,
                "gap_score": gap_score,
                "combined_member_count": clusters[id1]["member_count"] + clusters[id2]["member_count"]
            })
    
    # Sort by gap score (best gaps first)
    gaps.sort(key=lambda x: x["gap_score"], reverse=True)
    
    logger.info(f"Identified {len(gaps)} semantic gaps")
    return gaps


def find_bridge_units(
    cluster1_id: str,
    cluster2_id: str,
    session,
    max_bridges: int = 10
) -> List[Dict[str, Any]]:
    """Find meaningful units that could bridge two clusters.
    
    Bridge units are those that have semantic similarity to both clusters
    but aren't strongly assigned to either.
    
    Args:
        cluster1_id: First cluster ID
        cluster2_id: Second cluster ID
        session: Neo4j session
        max_bridges: Maximum number of bridge units to return
        
    Returns:
        List of potential bridge units with their relevance scores
    """
    # Query to find units that have some connection to both clusters' topics
    query = """
    // Get centroids for both clusters
    MATCH (c1:Cluster {id: $cluster1_id})
    MATCH (c2:Cluster {id: $cluster2_id})
    
    // Find units in cluster 1
    MATCH (m1:MeaningfulUnit)-[:IN_CLUSTER]->(c1)
    WITH c1, c2, COLLECT(m1) as cluster1_units
    
    // Find units in cluster 2
    MATCH (m2:MeaningfulUnit)-[:IN_CLUSTER]->(c2)
    WITH c1, c2, cluster1_units, COLLECT(m2) as cluster2_units
    
    // Find units that share entities with both clusters
    MATCH (e:Entity)-[:EXTRACTED_FROM]->(m1:MeaningfulUnit)
    WHERE m1 IN cluster1_units
    WITH c1, c2, cluster1_units, cluster2_units, COLLECT(DISTINCT e) as cluster1_entities
    
    MATCH (e:Entity)-[:EXTRACTED_FROM]->(m2:MeaningfulUnit)
    WHERE m2 IN cluster2_units
    WITH c1, c2, cluster1_units, cluster2_units, cluster1_entities, COLLECT(DISTINCT e) as cluster2_entities
    
    // Find shared entities
    WITH c1, c2, 
         [e IN cluster1_entities WHERE e IN cluster2_entities] as shared_entities,
         cluster1_entities,
         cluster2_entities
    
    // Find units that mention shared entities but aren't in either cluster
    UNWIND shared_entities as bridge_entity
    MATCH (bridge_entity)-[:EXTRACTED_FROM]->(bridge_unit:MeaningfulUnit)
    WHERE NOT (bridge_unit)-[:IN_CLUSTER]->(c1)
      AND NOT (bridge_unit)-[:IN_CLUSTER]->(c2)
    
    RETURN DISTINCT bridge_unit.id as unit_id,
           bridge_unit.summary as summary,
           bridge_entity.name as entity_name,
           bridge_entity.type as entity_type,
           SIZE(shared_entities) as shared_entity_count
    ORDER BY shared_entity_count DESC
    LIMIT $max_bridges
    """
    
    bridges = []
    
    try:
        result = session.run(query, {
            "cluster1_id": cluster1_id,
            "cluster2_id": cluster2_id,
            "max_bridges": max_bridges
        })
        
        for record in result:
            bridges.append({
                "unit_id": record["unit_id"],
                "summary": record["summary"],
                "bridge_entity": record["entity_name"],
                "entity_type": record["entity_type"],
                "relevance_score": record["shared_entity_count"]
            })
        
        logger.debug(f"Found {len(bridges)} bridge units between {cluster1_id} and {cluster2_id}")
        
    except Exception as e:
        logger.error(f"Error finding bridge units: {e}")
    
    return bridges


def create_semantic_gap_relationships(
    gaps: List[Dict[str, Any]],
    session,
    min_gap_score: float = 0.5
) -> int:
    """Create SEMANTIC_GAP relationships in Neo4j.
    
    Args:
        gaps: List of identified gaps
        session: Neo4j session
        min_gap_score: Minimum gap score to create relationship
        
    Returns:
        Number of relationships created
    """
    relationships_created = 0
    
    # Delete existing semantic gap relationships
    delete_query = """
    MATCH ()-[r:SEMANTIC_GAP]->()
    DELETE r
    """
    
    try:
        session.run(delete_query)
        logger.info("Deleted existing SEMANTIC_GAP relationships")
    except Exception as e:
        logger.error(f"Error deleting existing gaps: {e}")
    
    # Create new relationships for significant gaps
    create_query = """
    MATCH (c1:Cluster {id: $cluster1_id})
    MATCH (c2:Cluster {id: $cluster2_id})
    CREATE (c1)-[r:SEMANTIC_GAP {
        distance: $distance,
        similarity: $similarity,
        gap_score: $gap_score,
        created_at: datetime(),
        potential_bridges: $bridges
    }]->(c2)
    RETURN r
    """
    
    for gap in gaps:
        if gap["gap_score"] >= min_gap_score:
            try:
                # Find bridge concepts for this gap
                bridges = find_bridge_units(
                    gap["cluster1_id"],
                    gap["cluster2_id"],
                    session,
                    max_bridges=5
                )
                
                # Extract bridge summaries
                bridge_summaries = [b["summary"][:100] for b in bridges]
                
                result = session.run(create_query, {
                    "cluster1_id": gap["cluster1_id"],
                    "cluster2_id": gap["cluster2_id"],
                    "distance": gap["distance"],
                    "similarity": gap["similarity"],
                    "gap_score": gap["gap_score"],
                    "bridges": bridge_summaries
                })
                
                if result.single():
                    relationships_created += 1
                    
            except Exception as e:
                logger.error(f"Error creating gap relationship: {e}")
    
    logger.info(f"Created {relationships_created} SEMANTIC_GAP relationships")
    return relationships_created


def detect_semantic_gaps(session, affected_cluster_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Main function to detect semantic gaps between clusters.
    
    Args:
        session: Neo4j session
        affected_cluster_ids: Optional list of cluster IDs to focus on
        
    Returns:
        Dictionary with gap detection results
    """
    results = {
        "clusters_analyzed": 0,
        "gaps_detected": 0,
        "relationships_created": 0,
        "top_gaps": [],
        "errors": []
    }
    
    try:
        # Fetch all clusters with centroids
        all_clusters = get_all_clusters(session)
        results["clusters_analyzed"] = len(all_clusters)
        
        if len(all_clusters) < 2:
            logger.info("Not enough clusters to detect gaps")
            return results
        
        # Calculate pairwise distances
        if affected_cluster_ids:
            # Only calculate distances involving affected clusters
            clusters_to_analyze = {
                cid: data for cid, data in all_clusters.items()
                if cid in affected_cluster_ids or len(affected_cluster_ids) == 0
            }
        else:
            clusters_to_analyze = all_clusters
        
        distances = calculate_cluster_distances(clusters_to_analyze)
        
        # Identify semantic gaps
        gaps = identify_semantic_gaps(distances, clusters_to_analyze)
        results["gaps_detected"] = len(gaps)
        
        # Store top gaps for reporting
        results["top_gaps"] = [
            {
                "cluster1": gap["cluster1_label"],
                "cluster2": gap["cluster2_label"],
                "gap_score": round(gap["gap_score"], 3),
                "similarity": round(gap["similarity"], 3)
            }
            for gap in gaps[:5]  # Top 5 gaps
        ]
        
        # Create relationships in Neo4j
        relationships_created = create_semantic_gap_relationships(gaps, session)
        results["relationships_created"] = relationships_created
        
        logger.info(f"Semantic gap detection complete: {results['gaps_detected']} gaps found")
        
    except Exception as e:
        logger.error(f"Error in semantic gap detection: {e}")
        results["errors"].append(str(e))
    
    return results


def run_semantic_gap_detection(episode_id: str, session) -> Dict[str, Any]:
    """Run semantic gap detection for a newly added episode.
    
    Args:
        episode_id: ID of the newly added episode
        session: Neo4j session
        
    Returns:
        Gap detection results
    """
    # Get clusters affected by the new episode
    query = """
    MATCH (e:Episode {id: $episode_id})-[:CONTAINS]->(m:MeaningfulUnit)-[:IN_CLUSTER]->(c:Cluster)
    RETURN COLLECT(DISTINCT c.id) as affected_clusters
    """
    
    try:
        result = session.run(query, episode_id=episode_id)
        record = result.single()
        
        if record and record["affected_clusters"]:
            affected_clusters = record["affected_clusters"]
            logger.info(f"Episode {episode_id} affects {len(affected_clusters)} clusters")
            return detect_semantic_gaps(session, affected_clusters)
        else:
            logger.warning(f"No clusters affected by episode {episode_id}")
            return {"error": "No clusters affected"}
            
    except Exception as e:
        logger.error(f"Error running semantic gap detection for episode {episode_id}: {e}")
        return {"error": str(e)}