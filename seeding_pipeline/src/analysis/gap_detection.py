"""Structural gap detection for knowledge discovery.

This module identifies gaps between topic clusters in the knowledge graph,
helping to find unexplored connections and knowledge silos.
"""

import logging
from typing import List, Set, Dict, Tuple, Optional, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


def identify_topic_clusters(session) -> List[Set[str]]:
    """Identify topic clusters based on co-occurrence patterns.
    
    Topics that frequently appear together in episodes form clusters.
    
    Args:
        session: Neo4j session
        
    Returns:
        List of topic clusters, where each cluster is a set of topic names
    """
    # Query to find topic co-occurrences
    query = """
    MATCH (e:Episode)-[:HAS_TOPIC]->(t1:Topic)
    MATCH (e)-[:HAS_TOPIC]->(t2:Topic)
    WHERE t1.name < t2.name
    WITH t1.name as topic1, t2.name as topic2, COUNT(DISTINCT e) as cooccurrence_count
    WHERE cooccurrence_count > 1
    RETURN topic1, topic2, cooccurrence_count
    ORDER BY cooccurrence_count DESC
    """
    
    try:
        result = session.run(query)
        
        # Build co-occurrence graph
        cooccurrences = defaultdict(dict)
        all_topics = set()
        
        for record in result:
            topic1 = record["topic1"]
            topic2 = record["topic2"]
            count = record["cooccurrence_count"]
            
            cooccurrences[topic1][topic2] = count
            cooccurrences[topic2][topic1] = count
            all_topics.add(topic1)
            all_topics.add(topic2)
        
        # Get total episode counts for each topic
        topic_counts = {}
        count_query = """
        MATCH (e:Episode)-[:HAS_TOPIC]->(t:Topic)
        WHERE t.name IN $topics
        WITH t.name as topic, COUNT(DISTINCT e) as episode_count
        RETURN topic, episode_count
        """
        
        if all_topics:
            count_result = session.run(count_query, topics=list(all_topics))
            for record in count_result:
                topic_counts[record["topic"]] = record["episode_count"]
        
        # Identify clusters using simple threshold (>30% co-occurrence rate)
        clusters = []
        processed_topics = set()
        
        for topic in all_topics:
            if topic in processed_topics:
                continue
                
            cluster = {topic}
            topic_episode_count = topic_counts.get(topic, 1)
            
            # Find topics that co-occur frequently with this topic
            for other_topic, cooccurrence_count in cooccurrences.get(topic, {}).items():
                if other_topic in processed_topics:
                    continue
                    
                other_topic_count = topic_counts.get(other_topic, 1)
                min_count = min(topic_episode_count, other_topic_count)
                
                # If topics appear together in >30% of their episodes
                if cooccurrence_count / min_count > 0.3:
                    cluster.add(other_topic)
            
            # Only create cluster if it has multiple topics
            if len(cluster) > 1:
                clusters.append(cluster)
                processed_topics.update(cluster)
        
        # Add single-topic clusters for isolated topics
        for topic in all_topics:
            if topic not in processed_topics:
                clusters.append({topic})
        
        logger.info(f"Identified {len(clusters)} topic clusters")
        return clusters
        
    except Exception as e:
        logger.error(f"Error identifying topic clusters: {e}")
        return []


def calculate_gap_score(cluster1: Set[str], cluster2: Set[str], session) -> float:
    """Calculate gap score between two topic clusters.
    
    Gap score = 1 - (episodes with both clusters / min episodes of either cluster)
    Higher score means larger gap (less connection).
    
    Args:
        cluster1: First topic cluster
        cluster2: Second topic cluster
        session: Neo4j session
        
    Returns:
        Gap score between 0 and 1
    """
    if not cluster1 or not cluster2:
        return 0.0
    
    # Query to count episodes for each cluster and their overlap
    query = """
    // Count episodes with cluster1 topics
    MATCH (e1:Episode)-[:HAS_TOPIC]->(t1:Topic)
    WHERE t1.name IN $cluster1_topics
    WITH COLLECT(DISTINCT e1) as cluster1_episodes
    
    // Count episodes with cluster2 topics
    MATCH (e2:Episode)-[:HAS_TOPIC]->(t2:Topic)
    WHERE t2.name IN $cluster2_topics
    WITH cluster1_episodes, COLLECT(DISTINCT e2) as cluster2_episodes
    
    // Calculate intersection
    WITH cluster1_episodes, cluster2_episodes,
         [e IN cluster1_episodes WHERE e IN cluster2_episodes] as both_episodes
    
    RETURN SIZE(cluster1_episodes) as cluster1_count,
           SIZE(cluster2_episodes) as cluster2_count,
           SIZE(both_episodes) as both_count
    """
    
    try:
        result = session.run(
            query,
            cluster1_topics=list(cluster1),
            cluster2_topics=list(cluster2)
        )
        
        record = result.single()
        if not record:
            return 1.0
        
        cluster1_count = record["cluster1_count"]
        cluster2_count = record["cluster2_count"]
        both_count = record["both_count"]
        
        # Avoid division by zero
        min_count = min(cluster1_count, cluster2_count)
        if min_count == 0:
            return 1.0
        
        # Calculate gap score
        gap_score = 1.0 - (both_count / min_count)
        
        return max(0.0, min(1.0, gap_score))  # Ensure score is between 0 and 1
        
    except Exception as e:
        logger.error(f"Error calculating gap score: {e}")
        return 0.0


def find_bridge_concepts(cluster1: Set[str], cluster2: Set[str], session) -> List[str]:
    """Find entities that could bridge two clusters.
    
    Bridge concepts are entities that appear with topics from both clusters
    but not necessarily in the same episodes.
    
    Args:
        cluster1: First topic cluster
        cluster2: Second topic cluster
        session: Neo4j session
        
    Returns:
        List of potential bridge entity names
    """
    query = """
    // Find entities connected to cluster1 topics
    MATCH (e1:Episode)-[:HAS_TOPIC]->(t1:Topic)
    WHERE t1.name IN $cluster1_topics
    MATCH (e1)-[:MENTIONS]->(entity1)
    WITH COLLECT(DISTINCT entity1.name) as cluster1_entities
    
    // Find entities connected to cluster2 topics
    MATCH (e2:Episode)-[:HAS_TOPIC]->(t2:Topic)
    WHERE t2.name IN $cluster2_topics
    MATCH (e2)-[:MENTIONS]->(entity2)
    WITH cluster1_entities, COLLECT(DISTINCT entity2.name) as cluster2_entities
    
    // Find common entities (potential bridges)
    WITH [e IN cluster1_entities WHERE e IN cluster2_entities] as bridge_entities
    UNWIND bridge_entities as bridge
    
    // Count occurrences with each cluster
    MATCH (ep1:Episode)-[:HAS_TOPIC]->(t1:Topic)
    WHERE t1.name IN $cluster1_topics
    MATCH (ep1)-[:MENTIONS]->(ent1)
    WHERE ent1.name = bridge
    WITH bridge, COUNT(DISTINCT ep1) as cluster1_mentions
    
    MATCH (ep2:Episode)-[:HAS_TOPIC]->(t2:Topic)
    WHERE t2.name IN $cluster2_topics
    MATCH (ep2)-[:MENTIONS]->(ent2)
    WHERE ent2.name = bridge
    WITH bridge, cluster1_mentions, COUNT(DISTINCT ep2) as cluster2_mentions
    
    // Return bridges that appear with both clusters reasonably often
    WHERE cluster1_mentions >= 2 AND cluster2_mentions >= 2
    RETURN bridge
    ORDER BY cluster1_mentions + cluster2_mentions DESC
    LIMIT 10
    """
    
    try:
        result = session.run(
            query,
            cluster1_topics=list(cluster1),
            cluster2_topics=list(cluster2)
        )
        
        bridges = [record["bridge"] for record in result]
        return bridges
        
    except Exception as e:
        logger.error(f"Error finding bridge concepts: {e}")
        return []


def create_gap_node(
    cluster1: Set[str], 
    cluster2: Set[str], 
    gap_score: float,
    potential_bridges: List[str],
    session
) -> bool:
    """Create or update a StructuralGap node in Neo4j.
    
    Args:
        cluster1: First topic cluster
        cluster2: Second topic cluster
        gap_score: Calculated gap score
        potential_bridges: List of potential bridge concepts
        session: Neo4j session
        
    Returns:
        True if successful, False otherwise
    """
    # Sort clusters to ensure consistent ordering
    cluster1_sorted = sorted(list(cluster1))
    cluster2_sorted = sorted(list(cluster2))
    
    # Create unique identifier for this gap
    gap_id = f"{','.join(cluster1_sorted)}||{','.join(cluster2_sorted)}"
    
    query = """
    MERGE (gap:StructuralGap {id: $gap_id})
    SET gap.cluster1 = $cluster1,
        gap.cluster2 = $cluster2,
        gap.gap_score = $gap_score,
        gap.potential_bridges = $bridges,
        gap.last_updated = datetime()
    RETURN gap
    """
    
    try:
        result = session.run(
            query,
            gap_id=gap_id,
            cluster1=cluster1_sorted,
            cluster2=cluster2_sorted,
            gap_score=gap_score,
            bridges=potential_bridges
        )
        
        if result.single():
            logger.debug(f"Created/updated gap node for clusters: {cluster1_sorted[:2]}... and {cluster2_sorted[:2]}...")
            return True
        return False
        
    except Exception as e:
        logger.error(f"Error creating gap node: {e}")
        return False


def detect_structural_gaps(session, new_topics: Optional[List[str]] = None) -> Dict[str, Any]:
    """Main function to detect structural gaps in the knowledge graph.
    
    Args:
        session: Neo4j session
        new_topics: Optional list of newly added topics for incremental update
        
    Returns:
        Dictionary with gap detection results
    """
    results = {
        "clusters_found": 0,
        "gaps_detected": 0,
        "high_score_gaps": [],
        "errors": []
    }
    
    try:
        # Identify topic clusters
        clusters = identify_topic_clusters(session)
        results["clusters_found"] = len(clusters)
        
        if len(clusters) < 2:
            logger.info("Not enough clusters to detect gaps")
            return results
        
        # If new topics provided, only check gaps involving affected clusters
        if new_topics:
            affected_clusters = [
                cluster for cluster in clusters 
                if any(topic in cluster for topic in new_topics)
            ]
            
            # Check gaps between affected clusters and all others
            cluster_pairs = []
            for affected in affected_clusters:
                for other in clusters:
                    if affected != other:
                        cluster_pairs.append((affected, other))
        else:
            # Full analysis - check all cluster pairs
            cluster_pairs = [
                (clusters[i], clusters[j])
                for i in range(len(clusters))
                for j in range(i + 1, len(clusters))
            ]
        
        # Calculate gap scores and create nodes
        for cluster1, cluster2 in cluster_pairs:
            gap_score = calculate_gap_score(cluster1, cluster2, session)
            
            # Only store significant gaps (score > 0.5)
            if gap_score > 0.5:
                bridges = find_bridge_concepts(cluster1, cluster2, session)
                
                if create_gap_node(cluster1, cluster2, gap_score, bridges, session):
                    results["gaps_detected"] += 1
                    
                    # Track high-score gaps
                    if gap_score > 0.8:
                        results["high_score_gaps"].append({
                            "cluster1": list(cluster1)[:3],  # First 3 topics
                            "cluster2": list(cluster2)[:3],
                            "score": gap_score,
                            "bridges": bridges[:3]  # Top 3 bridges
                        })
        
        logger.info(f"Gap detection complete: {results['gaps_detected']} gaps found")
        
    except Exception as e:
        logger.error(f"Error in gap detection: {e}")
        results["errors"].append(str(e))
    
    return results


# Convenience function for integration
def run_gap_detection(episode_id: str, session) -> Dict[str, Any]:
    """Run gap detection for a newly added episode.
    
    Args:
        episode_id: ID of the newly added episode
        session: Neo4j session
        
    Returns:
        Gap detection results
    """
    # Get topics from the new episode
    query = """
    MATCH (e:Episode {id: $episode_id})-[:HAS_TOPIC]->(t:Topic)
    RETURN COLLECT(t.name) as topics
    """
    
    try:
        result = session.run(query, episode_id=episode_id)
        record = result.single()
        
        if record and record["topics"]:
            new_topics = record["topics"]
            return detect_structural_gaps(session, new_topics)
        else:
            logger.warning(f"No topics found for episode {episode_id}")
            return {"error": "No topics found"}
            
    except Exception as e:
        logger.error(f"Error running gap detection for episode {episode_id}: {e}")
        return {"error": str(e)}