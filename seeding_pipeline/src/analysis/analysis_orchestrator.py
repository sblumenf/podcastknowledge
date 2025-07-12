"""Analysis orchestrator for knowledge discovery.

This module coordinates all knowledge discovery analyses when new episodes
are added to the knowledge graph.
"""

import logging
import time
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .gap_detection import run_gap_detection
from .semantic_gap_detection import run_semantic_gap_detection
from .missing_links import run_missing_link_analysis
from .diversity_metrics import run_diversity_analysis

logger = logging.getLogger(__name__)


def run_knowledge_discovery(episode_id: str, session) -> Dict[str, Any]:
    """Run all knowledge discovery analyses for a new episode.
    
    Coordinates:
    - Gap detection for affected topic clusters
    - Missing link analysis for new entities
    - Diversity metrics update
    
    Args:
        episode_id: ID of the newly added episode
        session: Neo4j session
        
    Returns:
        Combined results from all analyses
    """
    results = {
        "episode_id": episode_id,
        "analyses_completed": [],
        "analyses_failed": [],
        "total_time": 0.0,
        "gap_detection": {},
        "semantic_gap_detection": {},
        "missing_links": {},
        "diversity_metrics": {},
        "summary": {}
    }
    
    start_time = time.time()
    
    try:
        # First, verify episode exists and has required data
        verification_query = """
        MATCH (e:Episode {id: $episode_id})
        OPTIONAL MATCH (e)-[:CONTAINS]->(m:MeaningfulUnit)-[:IN_CLUSTER]->(c:Cluster)
        OPTIONAL MATCH (entity)-[:MENTIONED_IN]->(e)
        RETURN e.title as title,
               COUNT(DISTINCT c) as cluster_count,
               COUNT(DISTINCT entity) as entity_count
        """
        
        result = session.run(verification_query, episode_id=episode_id)
        record = result.single()
        
        if not record or not record["title"]:
            logger.error(f"Episode {episode_id} not found")
            results["analyses_failed"].append("episode_verification")
            return results
        
        episode_title = record["title"]
        has_clusters = record["cluster_count"] > 0
        has_entities = record["entity_count"] > 0
        
        logger.info(f"Running knowledge discovery for episode: {episode_title}")
        
        # Run analyses based on available data
        analyses_to_run = []
        
        if has_clusters:
            analyses_to_run.append(("gap_detection", run_gap_detection))
            analyses_to_run.append(("semantic_gap_detection", run_semantic_gap_detection))
            analyses_to_run.append(("diversity_metrics", run_diversity_analysis))
        else:
            logger.warning(f"No clusters found for episode {episode_id}, skipping related analyses")
        
        if has_entities:
            analyses_to_run.append(("missing_links", run_missing_link_analysis))
        else:
            logger.warning(f"No entities found for episode {episode_id}, skipping missing link analysis")
        
        # Run analyses (could be parallelized with proper session handling)
        for analysis_name, analysis_func in analyses_to_run:
            try:
                analysis_start = time.time()
                
                # Run the analysis
                analysis_results = analysis_func(episode_id, session)
                
                # Store results
                results[analysis_name] = analysis_results
                
                # Track timing
                analysis_time = time.time() - analysis_start
                logger.info(f"{analysis_name} completed in {analysis_time:.2f}s")
                
                # Check for errors in results
                if "errors" in analysis_results and analysis_results["errors"]:
                    results["analyses_failed"].append(analysis_name)
                else:
                    results["analyses_completed"].append(analysis_name)
                    
            except Exception as e:
                logger.error(f"Error in {analysis_name}: {e}")
                results["analyses_failed"].append(analysis_name)
                results[analysis_name] = {"error": str(e)}
        
        # Generate summary
        results["summary"] = generate_summary(results)
        
    except Exception as e:
        logger.error(f"Error in knowledge discovery orchestration: {e}")
        results["analyses_failed"].append("orchestration")
        results["summary"]["error"] = str(e)
    
    finally:
        results["total_time"] = time.time() - start_time
        logger.info(f"Knowledge discovery completed in {results['total_time']:.2f}s")
    
    return results


def generate_summary(results: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a summary of knowledge discovery findings.
    
    Args:
        results: Combined results from all analyses
        
    Returns:
        Summary dictionary with key findings
    """
    summary = {
        "key_findings": [],
        "recommendations": [],
        "metrics": {}
    }
    
    # Summarize gap detection
    gap_results = results.get("gap_detection", {})
    if gap_results.get("high_score_gaps"):
        gap_count = len(gap_results["high_score_gaps"])
        summary["key_findings"].append(
            f"Found {gap_count} significant knowledge gaps between topic clusters"
        )
        
        # Add top gap as recommendation
        top_gap = gap_results["high_score_gaps"][0]
        summary["recommendations"].append(
            f"Explore connection between {top_gap['cluster1'][0]} and {top_gap['cluster2'][0]} topics"
        )
    
    # Summarize semantic gap detection
    semantic_gap_results = results.get("semantic_gap_detection", {})
    if semantic_gap_results.get("top_gaps"):
        gap_count = semantic_gap_results.get("gaps_detected", 0)
        summary["key_findings"].append(
            f"Found {gap_count} semantic gaps between knowledge clusters"
        )
        
        # Add top semantic gap as recommendation
        if semantic_gap_results["top_gaps"]:
            top_gap = semantic_gap_results["top_gaps"][0]
            summary["recommendations"].append(
                f"Bridge semantic gap between '{top_gap['cluster1']}' and '{top_gap['cluster2']}' (similarity: {top_gap['similarity']:.2f})"
            )
    
    # Summarize missing links
    link_results = results.get("missing_links", {})
    if link_results.get("high_score_links"):
        link_count = len(link_results["high_score_links"])
        summary["key_findings"].append(
            f"Identified {link_count} high-value missing connections"
        )
        
        # Add top missing link as recommendation
        top_link = link_results["high_score_links"][0]
        summary["recommendations"].append(
            f"Consider: {top_link['suggestion']}"
        )
    
    # Summarize diversity metrics
    diversity_results = results.get("diversity_metrics", {})
    if "diversity_score" in diversity_results:
        diversity_score = diversity_results["diversity_score"]
        trend = diversity_results.get("trend", "stable")
        
        summary["metrics"]["diversity_score"] = diversity_score
        summary["metrics"]["diversity_trend"] = trend
        
        if trend == "decreasing":
            summary["key_findings"].append(
                "Knowledge diversity is decreasing - risk of echo chamber"
            )
            summary["recommendations"].append(
                "Introduce new perspectives and topics to maintain diversity"
            )
        elif diversity_score < 0.3:
            summary["key_findings"].append(
                "Low knowledge diversity detected"
            )
    
    # Add insights if available
    if "insights" in diversity_results:
        insights = diversity_results["insights"]
        if insights.get("under_explored_topics"):
            topics = [t["topic"] for t in insights["under_explored_topics"][:3]]
            summary["recommendations"].append(
                f"Under-explored topics to consider: {', '.join(topics)}"
            )
    
    # Overall health assessment
    analyses_completed = len(results.get("analyses_completed", []))
    analyses_failed = len(results.get("analyses_failed", []))
    
    if analyses_completed > 0 and analyses_failed == 0:
        summary["status"] = "healthy"
    elif analyses_failed > analyses_completed:
        summary["status"] = "degraded"
    else:
        summary["status"] = "partial"
    
    return summary


def run_knowledge_discovery_batch(episode_ids: list, session) -> Dict[str, Any]:
    """Run knowledge discovery for multiple episodes.
    
    Useful for batch processing or catching up on analyses.
    
    Args:
        episode_ids: List of episode IDs to process
        session: Neo4j session
        
    Returns:
        Batch processing results
    """
    batch_results = {
        "episodes_processed": 0,
        "episodes_failed": 0,
        "total_time": 0.0,
        "episode_results": {}
    }
    
    start_time = time.time()
    
    for episode_id in episode_ids:
        try:
            episode_results = run_knowledge_discovery(episode_id, session)
            batch_results["episode_results"][episode_id] = episode_results
            
            if episode_results.get("summary", {}).get("status") == "healthy":
                batch_results["episodes_processed"] += 1
            else:
                batch_results["episodes_failed"] += 1
                
        except Exception as e:
            logger.error(f"Failed to process episode {episode_id}: {e}")
            batch_results["episodes_failed"] += 1
            batch_results["episode_results"][episode_id] = {"error": str(e)}
    
    batch_results["total_time"] = time.time() - start_time
    
    return batch_results


def get_analysis_configuration(session) -> Dict[str, Any]:
    """Get configuration for knowledge discovery analyses.
    
    Args:
        session: Neo4j session
        
    Returns:
        Configuration dictionary
    """
    # This could be extended to read from database or config file
    config = {
        "gap_detection": {
            "enabled": True,
            "min_cluster_size": 2,
            "cooccurrence_threshold": 0.3,
            "min_gap_score": 0.5
        },
        "missing_links": {
            "enabled": True,
            "min_entity_frequency": 2,
            "connection_score_threshold": 0.3,
            "max_suggestions": 10
        },
        "diversity_metrics": {
            "enabled": True,
            "history_retention_days": 30,
            "trend_threshold": 0.05
        }
    }
    
    return config