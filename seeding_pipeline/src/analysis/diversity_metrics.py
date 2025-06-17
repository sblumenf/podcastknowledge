"""Ecological thinking metrics for knowledge diversity.

This module tracks and measures the diversity and balance of knowledge
in the graph, helping to identify over-explored and under-explored areas.
"""

import logging
import math
from typing import List, Dict, Optional, Any
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)


def update_diversity_metrics(episode_topics: List[str], session) -> Dict[str, Any]:
    """Update diversity metrics based on new episode topics.
    
    Updates the global EcologicalMetrics node with:
    - Topic distribution counts
    - Diversity score (Shannon entropy)
    - Balance score (based on standard deviation)
    - Trend information
    
    Args:
        episode_topics: List of topic names from new episode
        session: Neo4j session
        
    Returns:
        Dictionary with updated metrics
    """
    results = {
        "diversity_score": 0.0,
        "balance_score": 0.0,
        "total_topics": 0,
        "topic_distribution": {},
        "trend": "stable",
        "errors": []
    }
    
    try:
        # Get or create EcologicalMetrics node
        metrics_node = get_or_create_metrics_node(session)
        
        # Get current topic distribution
        current_distribution = metrics_node.get("topic_distribution", {})
        
        # Update distribution with new topics
        for topic in episode_topics:
            current_distribution[topic] = current_distribution.get(topic, 0) + 1
        
        # Calculate total topic occurrences
        total_occurrences = sum(current_distribution.values())
        
        if total_occurrences > 0:
            # Calculate diversity score (Shannon entropy)
            diversity_score = calculate_shannon_entropy(
                list(current_distribution.values()),
                total_occurrences
            )
            
            # Calculate balance score
            balance_score = calculate_balance_score(
                list(current_distribution.values())
            )
            
            # Detect trend by comparing to previous score
            previous_diversity = metrics_node.get("diversity_score", diversity_score)
            trend = detect_diversity_trend(diversity_score, previous_diversity)
            
            # Update metrics node
            update_query = """
            MATCH (m:EcologicalMetrics)
            SET m.topic_distribution = $distribution,
                m.diversity_score = $diversity,
                m.balance_score = $balance,
                m.total_topics = $total_topics,
                m.total_occurrences = $total_occurrences,
                m.previous_diversity = m.diversity_score,
                m.trend = $trend,
                m.last_updated = datetime()
            
            // Store historical data WITHOUT auto-deletion
            // Historical data is valuable for long-term trend analysis
            WITH m
            CREATE (h:MetricsHistory {
                timestamp: datetime(),
                diversity_score: $diversity,
                balance_score: $balance,
                total_topics: $total_topics
            })
            CREATE (m)-[:HAS_HISTORY]->(h)
            
            RETURN m
            """
            
            result = session.run(
                update_query,
                distribution=current_distribution,
                diversity=diversity_score,
                balance=balance_score,
                total_topics=len(current_distribution),
                total_occurrences=total_occurrences,
                trend=trend
            )
            
            if result.single():
                results.update({
                    "diversity_score": diversity_score,
                    "balance_score": balance_score,
                    "total_topics": len(current_distribution),
                    "topic_distribution": dict(sorted(
                        current_distribution.items(),
                        key=lambda x: x[1],
                        reverse=True
                    )[:10]),  # Top 10 topics
                    "trend": trend
                })
                
                logger.info(f"Updated diversity metrics: score={diversity_score:.3f}, trend={trend}")
        
    except Exception as e:
        logger.error(f"Error updating diversity metrics: {e}")
        results["errors"].append(str(e))
    
    return results


def get_or_create_metrics_node(session) -> Dict[str, Any]:
    """Get existing EcologicalMetrics node or create if doesn't exist.
    
    Args:
        session: Neo4j session
        
    Returns:
        Dictionary with current metrics data
    """
    query = """
    MERGE (m:EcologicalMetrics {id: 'global'})
    ON CREATE SET 
        m.created = datetime(),
        m.topic_distribution = {},
        m.diversity_score = 0.0,
        m.balance_score = 0.0,
        m.total_topics = 0,
        m.total_occurrences = 0
    RETURN m
    """
    
    try:
        result = session.run(query)
        record = result.single()
        
        if record:
            node = record["m"]
            return {
                "topic_distribution": node.get("topic_distribution", {}),
                "diversity_score": node.get("diversity_score", 0.0),
                "balance_score": node.get("balance_score", 0.0),
                "total_topics": node.get("total_topics", 0),
                "total_occurrences": node.get("total_occurrences", 0)
            }
    except Exception as e:
        logger.error(f"Error getting metrics node: {e}")
    
    return {
        "topic_distribution": {},
        "diversity_score": 0.0,
        "balance_score": 0.0,
        "total_topics": 0,
        "total_occurrences": 0
    }


def calculate_shannon_entropy(frequencies: List[int], total: int) -> float:
    """Calculate Shannon entropy as diversity measure.
    
    Higher entropy indicates more diverse distribution.
    
    Args:
        frequencies: List of occurrence counts
        total: Total number of occurrences
        
    Returns:
        Shannon entropy value
    """
    if not frequencies or total == 0:
        return 0.0
    
    entropy = 0.0
    for freq in frequencies:
        if freq > 0:
            probability = freq / total
            entropy -= probability * math.log2(probability)
    
    # Normalize to 0-1 range based on maximum possible entropy
    max_entropy = math.log2(len(frequencies)) if len(frequencies) > 1 else 1
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
    
    return min(1.0, max(0.0, normalized_entropy))


def calculate_balance_score(frequencies: List[int]) -> float:
    """Calculate balance score based on distribution uniformity.
    
    Higher score indicates more balanced distribution.
    
    Args:
        frequencies: List of occurrence counts
        
    Returns:
        Balance score between 0 and 1
    """
    if not frequencies or len(frequencies) < 2:
        return 1.0
    
    # Calculate mean
    mean = sum(frequencies) / len(frequencies)
    
    # Calculate standard deviation
    variance = sum((x - mean) ** 2 for x in frequencies) / len(frequencies)
    std_dev = math.sqrt(variance)
    
    # Calculate coefficient of variation
    cv = std_dev / mean if mean > 0 else 0
    
    # Convert to 0-1 score (lower CV = higher balance)
    # Using exponential decay for smooth transition
    balance_score = math.exp(-cv)
    
    return min(1.0, max(0.0, balance_score))


def detect_diversity_trend(current: float, previous: float) -> str:
    """Detect trend in diversity score.
    
    Args:
        current: Current diversity score
        previous: Previous diversity score
        
    Returns:
        Trend indicator: "increasing", "decreasing", or "stable"
    """
    threshold = 0.05  # 5% change threshold
    
    if current > previous * (1 + threshold):
        return "increasing"
    elif current < previous * (1 - threshold):
        return "decreasing"
    else:
        return "stable"


def get_diversity_insights(session) -> Dict[str, Any]:
    """Get detailed diversity insights and recommendations.
    
    Args:
        session: Neo4j session
        
    Returns:
        Dictionary with insights and recommendations
    """
    insights = {
        "current_state": {},
        "under_explored_topics": [],
        "over_explored_topics": [],
        "recommendations": [],
        "historical_trend": []
    }
    
    try:
        # Get current metrics
        metrics_query = """
        MATCH (m:EcologicalMetrics {id: 'global'})
        RETURN m
        """
        
        result = session.run(metrics_query)
        record = result.single()
        
        if not record:
            insights["recommendations"].append("No diversity metrics found. Process more episodes to build metrics.")
            return insights
        
        metrics = record["m"]
        diversity_score = metrics.get("diversity_score", 0)
        balance_score = metrics.get("balance_score", 0)
        topic_dist = metrics.get("topic_distribution", {})
        
        insights["current_state"] = {
            "diversity_score": diversity_score,
            "balance_score": balance_score,
            "total_topics": metrics.get("total_topics", 0),
            "trend": metrics.get("trend", "unknown")
        }
        
        # Identify under and over-explored topics
        if topic_dist:
            sorted_topics = sorted(topic_dist.items(), key=lambda x: x[1])
            total_occurrences = sum(topic_dist.values())
            mean_occurrences = total_occurrences / len(topic_dist)
            
            # Under-explored (< 50% of mean)
            insights["under_explored_topics"] = [
                {"topic": topic, "count": count}
                for topic, count in sorted_topics[:5]
                if count < mean_occurrences * 0.5
            ]
            
            # Over-explored (> 200% of mean)
            insights["over_explored_topics"] = [
                {"topic": topic, "count": count}
                for topic, count in sorted_topics[-5:]
                if count > mean_occurrences * 2
            ]
        
        # Generate recommendations
        if diversity_score < 0.5:
            insights["recommendations"].append(
                "Low diversity detected. Consider exploring new topics to broaden content."
            )
        elif diversity_score > 0.8:
            insights["recommendations"].append(
                "High diversity achieved. Consider deepening existing topics for expertise."
            )
        
        if balance_score < 0.5:
            insights["recommendations"].append(
                "Imbalanced topic distribution. Focus on under-explored topics."
            )
        
        if insights["under_explored_topics"]:
            topics = [t["topic"] for t in insights["under_explored_topics"][:3]]
            insights["recommendations"].append(
                f"Under-explored topics needing attention: {', '.join(topics)}"
            )
        
        # Get historical trend
        history_query = """
        MATCH (m:EcologicalMetrics {id: 'global'})-[:HAS_HISTORY]->(h:MetricsHistory)
        RETURN h.timestamp as timestamp, 
               h.diversity_score as diversity,
               h.balance_score as balance
        ORDER BY h.timestamp DESC
        LIMIT 10
        """
        
        history_result = session.run(history_query)
        insights["historical_trend"] = [
            {
                "timestamp": record["timestamp"].isoformat() if hasattr(record["timestamp"], 'isoformat') else str(record["timestamp"]),
                "diversity": record["diversity"],
                "balance": record["balance"]
            }
            for record in history_result
        ]
        
    except Exception as e:
        logger.error(f"Error getting diversity insights: {e}")
        insights["recommendations"].append(f"Error analyzing diversity: {str(e)}")
    
    return insights


def run_diversity_analysis(episode_id: str, session) -> Dict[str, Any]:
    """Run diversity analysis for a newly added episode.
    
    Args:
        episode_id: ID of the newly added episode
        session: Neo4j session
        
    Returns:
        Diversity analysis results
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
            topics = record["topics"]
            
            # Update metrics
            metrics = update_diversity_metrics(topics, session)
            
            # Get insights if diversity is changing significantly
            if metrics.get("trend") in ["increasing", "decreasing"]:
                insights = get_diversity_insights(session)
                metrics["insights"] = insights
            
            return metrics
        else:
            logger.warning(f"No topics found for episode {episode_id}")
            return {"error": "No topics found"}
            
    except Exception as e:
        logger.error(f"Error running diversity analysis for episode {episode_id}: {e}")
        return {"error": str(e)}


def get_historical_metrics(session, days_back: Optional[int] = None, 
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Retrieve historical diversity metrics with optional time filtering.
    
    This function provides controlled access to historical data without 
    auto-deletion. Use this for long-term trend analysis, reporting,
    and strategic planning.
    
    Args:
        session: Neo4j session
        days_back: Number of days of history to retrieve (if specified)
        start_date: Start date for historical range (if specified)
        end_date: End date for historical range (if specified)
        
    Returns:
        List of historical metrics ordered by timestamp
        
    Note:
        Historical data is preserved indefinitely for valuable long-term
        analysis. Use time filters to query specific periods as needed.
    """
    # Build query based on parameters
    base_query = """
    MATCH (m:EcologicalMetrics {id: 'global'})-[:HAS_HISTORY]->(h:MetricsHistory)
    """
    
    where_clauses = []
    params = {}
    
    if days_back is not None:
        where_clauses.append("h.timestamp >= datetime() - duration('P' + $days + 'D')")
        params['days'] = str(days_back)
    
    if start_date is not None:
        where_clauses.append("h.timestamp >= $start_date")
        params['start_date'] = start_date
        
    if end_date is not None:
        where_clauses.append("h.timestamp <= $end_date")
        params['end_date'] = end_date
    
    # Construct full query
    if where_clauses:
        query = base_query + " WHERE " + " AND ".join(where_clauses)
    else:
        query = base_query
        
    query += """
    RETURN h.timestamp as timestamp,
           h.diversity_score as diversity_score,
           h.balance_score as balance_score,
           h.total_topics as total_topics
    ORDER BY h.timestamp DESC
    """
    
    try:
        result = session.run(query, **params)
        return [
            {
                "timestamp": record["timestamp"],
                "diversity_score": record["diversity_score"],
                "balance_score": record["balance_score"],
                "total_topics": record["total_topics"]
            }
            for record in result
        ]
    except Exception as e:
        logger.error(f"Error retrieving historical metrics: {e}")
        return []


def archive_old_metrics(session, years_to_keep: int = 2) -> Dict[str, Any]:
    """Archive historical metrics older than specified years.
    
    This function should be called manually as part of maintenance,
    NOT automatically. It exports old data before removal.
    
    Args:
        session: Neo4j session
        years_to_keep: Number of years of history to keep (default: 2)
        
    Returns:
        Dictionary with archive results and exported data
        
    Note:
        This is a manual maintenance function. Automatic deletion
        has been removed to preserve valuable historical data.
    """
    cutoff_date = datetime.now() - timedelta(days=years_to_keep * 365)
    
    # First, export the old data
    export_query = """
    MATCH (m:EcologicalMetrics {id: 'global'})-[:HAS_HISTORY]->(h:MetricsHistory)
    WHERE h.timestamp < $cutoff_date
    RETURN h.timestamp as timestamp,
           h.diversity_score as diversity_score,
           h.balance_score as balance_score,
           h.total_topics as total_topics
    ORDER BY h.timestamp
    """
    
    try:
        result = session.run(export_query, cutoff_date=cutoff_date)
        archived_data = [dict(record) for record in result]
        
        # Only delete if we have successfully exported the data
        if archived_data:
            # Manual deletion - requires explicit action
            delete_query = """
            MATCH (m:EcologicalMetrics {id: 'global'})-[r:HAS_HISTORY]->(h:MetricsHistory)
            WHERE h.timestamp < $cutoff_date
            DELETE r, h
            RETURN count(h) as deleted_count
            """
            
            delete_result = session.run(delete_query, cutoff_date=cutoff_date)
            deleted = delete_result.single()['deleted_count']
            
            return {
                "success": True,
                "archived_count": len(archived_data),
                "deleted_count": deleted,
                "cutoff_date": cutoff_date.isoformat(),
                "archived_data": archived_data  # Can be saved to file
            }
        else:
            return {
                "success": True,
                "message": "No data to archive",
                "cutoff_date": cutoff_date.isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error archiving historical metrics: {e}")
        return {
            "success": False,
            "error": str(e)
        }