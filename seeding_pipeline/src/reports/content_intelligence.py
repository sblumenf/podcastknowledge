"""Content intelligence report generation module.

This module generates reports from knowledge discovery analysis results,
providing actionable insights for podcasters.
"""

import json
import csv
import logging
from typing import Dict, Any, List, Optional, TextIO
from datetime import datetime
from pathlib import Path
from io import StringIO

logger = logging.getLogger(__name__)


def generate_gap_report(podcast_name: str, session) -> Dict[str, Any]:
    """Generate gap analysis report for a podcast.
    
    Queries StructuralGap nodes and formats findings with
    topic clusters, gap scores, and bridge suggestions.
    
    Args:
        podcast_name: Name of the podcast to analyze
        session: Neo4j session
        
    Returns:
        Dictionary with gap analysis report data
    """
    report = {
        "podcast_name": podcast_name,
        "report_type": "gap_analysis",
        "generated_at": datetime.now().isoformat(),
        "summary": {},
        "gaps": [],
        "recommendations": []
    }
    
    # Query for gaps related to this podcast
    query = """
    MATCH (p:Podcast {name: $podcast_name})-[:HAS_EPISODE]->(e:Episode)
    MATCH (e)-[:IN_CLUSTER.*Cluster)
    WITH COLLECT(DISTINCT t.name) as podcast_topics
    
    MATCH (gap:StructuralGap)
    WHERE ANY(topic IN gap.cluster1 WHERE topic IN podcast_topics)
       OR ANY(topic IN gap.cluster2 WHERE topic IN podcast_topics)
    RETURN gap
    ORDER BY gap.gap_score DESC
    LIMIT 20
    """
    
    try:
        result = session.run(query, podcast_name=podcast_name)
        
        gaps_found = 0
        high_score_gaps = 0
        total_score = 0.0
        
        for record in result:
            gap = record["gap"]
            gap_data = {
                "cluster1": gap.get("cluster1", [])[:5],  # Top 5 topics
                "cluster2": gap.get("cluster2", [])[:5],
                "gap_score": gap.get("gap_score", 0),
                "potential_bridges": gap.get("potential_bridges", [])[:3],
                "last_updated": gap.get("last_updated", "").split("T")[0] if gap.get("last_updated") else ""
            }
            
            report["gaps"].append(gap_data)
            gaps_found += 1
            total_score += gap_data["gap_score"]
            
            if gap_data["gap_score"] > 0.8:
                high_score_gaps += 1
        
        # Generate summary
        report["summary"] = {
            "total_gaps": gaps_found,
            "high_score_gaps": high_score_gaps,
            "average_gap_score": total_score / gaps_found if gaps_found > 0 else 0
        }
        
        # Generate recommendations
        if high_score_gaps > 0:
            top_gap = report["gaps"][0] if report["gaps"] else None
            if top_gap:
                report["recommendations"].append({
                    "priority": "high",
                    "action": "Bridge knowledge gap",
                    "details": f"Create content connecting {top_gap['cluster1'][0]} with {top_gap['cluster2'][0]}",
                    "bridge_suggestions": top_gap["potential_bridges"]
                })
        
        if gaps_found > 10:
            report["recommendations"].append({
                "priority": "medium",
                "action": "Increase cross-topic integration",
                "details": "Many topic clusters are isolated. Consider episodes that combine multiple themes."
            })
        
        logger.info(f"Generated gap report for {podcast_name}: {gaps_found} gaps found")
        
    except Exception as e:
        logger.error(f"Error generating gap report: {e}")
        report["error"] = str(e)
    
    return report


def generate_missing_links_report(podcast_name: str, session) -> Dict[str, Any]:
    """Generate missing links report for a podcast.
    
    Queries MissingLink nodes and groups findings by entity type
    with connection suggestions.
    
    Args:
        podcast_name: Name of the podcast to analyze
        session: Neo4j session
        
    Returns:
        Dictionary with missing links report data
    """
    report = {
        "podcast_name": podcast_name,
        "report_type": "missing_links",
        "generated_at": datetime.now().isoformat(),
        "summary": {},
        "missing_links": [],
        "by_entity_type": {},
        "recommendations": []
    }
    
    # Query for missing links related to this podcast
    query = """
    MATCH (p:Podcast {name: $podcast_name})-[:HAS_EPISODE]->(e:Episode)
    MATCH (e)-[:MENTIONS]->(entity)
    WITH COLLECT(DISTINCT entity.name) as podcast_entities
    
    MATCH (link:MissingLink)
    WHERE link.entity1 IN podcast_entities OR link.entity2 IN podcast_entities
    RETURN link
    ORDER BY link.connection_score DESC
    LIMIT 30
    """
    
    try:
        result = session.run(query, podcast_name=podcast_name)
        
        links_found = 0
        high_score_links = 0
        entity_types = {}
        
        for record in result:
            link = record["link"]
            link_data = {
                "entity1": link.get("entity1", ""),
                "entity2": link.get("entity2", ""),
                "entity_type": link.get("entity_type", "Unknown"),
                "connection_score": link.get("connection_score", 0),
                "suggested_topic": link.get("suggested_topic", ""),
                "frequency": {
                    "entity1": link.get("entity1_frequency", 0),
                    "entity2": link.get("entity2_frequency", 0)
                }
            }
            
            report["missing_links"].append(link_data)
            links_found += 1
            
            # Group by entity type
            entity_type = link_data["entity_type"]
            if entity_type not in entity_types:
                entity_types[entity_type] = []
            entity_types[entity_type].append(link_data)
            
            if link_data["connection_score"] > 0.7:
                high_score_links += 1
        
        # Organize by entity type
        report["by_entity_type"] = {
            entity_type: {
                "count": len(links),
                "top_links": links[:3]  # Top 3 per type
            }
            for entity_type, links in entity_types.items()
        }
        
        # Generate summary
        report["summary"] = {
            "total_missing_links": links_found,
            "high_score_links": high_score_links,
            "entity_types_affected": len(entity_types)
        }
        
        # Generate recommendations
        if high_score_links > 0 and report["missing_links"]:
            top_link = report["missing_links"][0]
            report["recommendations"].append({
                "priority": "high",
                "action": "Create connection content",
                "details": top_link["suggested_topic"],
                "entities": [top_link["entity1"], top_link["entity2"]]
            })
        
        # Type-specific recommendations
        for entity_type, data in report["by_entity_type"].items():
            if data["count"] > 5:
                report["recommendations"].append({
                    "priority": "medium",
                    "action": f"Increase {entity_type} connections",
                    "details": f"Many unconnected {entity_type} entities could benefit from collaborative content"
                })
        
        logger.info(f"Generated missing links report for {podcast_name}: {links_found} links found")
        
    except Exception as e:
        logger.error(f"Error generating missing links report: {e}")
        report["error"] = str(e)
    
    return report


def generate_diversity_dashboard(podcast_name: str, session) -> Dict[str, Any]:
    """Generate diversity metrics dashboard for a podcast.
    
    Queries EcologicalMetrics and shows topic distribution,
    diversity trends, and balance insights.
    
    Args:
        podcast_name: Name of the podcast to analyze
        session: Neo4j session
        
    Returns:
        Dictionary with diversity dashboard data
    """
    dashboard = {
        "podcast_name": podcast_name,
        "report_type": "diversity_dashboard",
        "generated_at": datetime.now().isoformat(),
        "current_metrics": {},
        "topic_distribution": {},
        "historical_trend": [],
        "insights": {},
        "recommendations": []
    }
    
    try:
        # Get current metrics
        metrics_query = """
        MATCH (m:EcologicalMetrics {id: 'global'})
        RETURN m
        """
        
        result = session.run(metrics_query)
        record = result.single()
        
        if record:
            metrics = record["m"]
            
            # Current metrics
            dashboard["current_metrics"] = {
                "diversity_score": metrics.get("diversity_score", 0),
                "balance_score": metrics.get("balance_score", 0),
                "total_topics": metrics.get("total_topics", 0),
                "trend": metrics.get("trend", "unknown")
            }
            
            # Topic distribution (top 20)
            topic_dist = metrics.get("topic_distribution", {})
            sorted_topics = sorted(topic_dist.items(), key=lambda x: x[1], reverse=True)[:20]
            dashboard["topic_distribution"] = dict(sorted_topics)
            
            # Get historical trend
            history_query = """
            MATCH (m:EcologicalMetrics {id: 'global'})-[:HAS_HISTORY]->(h:MetricsHistory)
            RETURN h.timestamp as timestamp,
                   h.diversity_score as diversity,
                   h.balance_score as balance
            ORDER BY h.timestamp DESC
            LIMIT 30
            """
            
            history_result = session.run(history_query)
            dashboard["historical_trend"] = [
                {
                    "date": record["timestamp"].split("T")[0] if hasattr(record["timestamp"], 'split') else str(record["timestamp"]),
                    "diversity": round(record["diversity"], 3),
                    "balance": round(record["balance"], 3)
                }
                for record in history_result
            ]
            
            # Generate insights
            diversity_score = dashboard["current_metrics"]["diversity_score"]
            balance_score = dashboard["current_metrics"]["balance_score"]
            
            if diversity_score < 0.3:
                dashboard["insights"]["diversity_level"] = "low"
                dashboard["insights"]["diversity_message"] = "Content is highly focused on few topics"
            elif diversity_score < 0.7:
                dashboard["insights"]["diversity_level"] = "moderate"
                dashboard["insights"]["diversity_message"] = "Healthy topic diversity with room for expansion"
            else:
                dashboard["insights"]["diversity_level"] = "high"
                dashboard["insights"]["diversity_message"] = "Excellent topic diversity across many areas"
            
            if balance_score < 0.5:
                dashboard["insights"]["balance_level"] = "imbalanced"
                dashboard["insights"]["balance_message"] = "Some topics are significantly over or under-represented"
            else:
                dashboard["insights"]["balance_level"] = "balanced"
                dashboard["insights"]["balance_message"] = "Topics are relatively evenly distributed"
            
            # Find over and under-explored topics
            if topic_dist:
                mean_count = sum(topic_dist.values()) / len(topic_dist)
                
                dashboard["insights"]["over_explored"] = [
                    topic for topic, count in sorted_topics[:5]
                    if count > mean_count * 2
                ]
                
                dashboard["insights"]["under_explored"] = [
                    topic for topic, count in sorted_topics[-5:]
                    if count < mean_count * 0.5
                ]
            
            # Generate recommendations
            if diversity_score < 0.5:
                dashboard["recommendations"].append({
                    "priority": "high",
                    "action": "Increase topic diversity",
                    "details": "Explore new subject areas to broaden content appeal"
                })
            
            if dashboard["insights"].get("under_explored"):
                topics = dashboard["insights"]["under_explored"][:3]
                dashboard["recommendations"].append({
                    "priority": "medium",
                    "action": "Develop under-explored topics",
                    "details": f"Consider more content on: {', '.join(topics)}"
                })
            
            trend = dashboard["current_metrics"]["trend"]
            if trend == "decreasing":
                dashboard["recommendations"].append({
                    "priority": "high",
                    "action": "Reverse diversity decline",
                    "details": "Diversity is decreasing - introduce fresh perspectives"
                })
        
        logger.info(f"Generated diversity dashboard for {podcast_name}")
        
    except Exception as e:
        logger.error(f"Error generating diversity dashboard: {e}")
        dashboard["error"] = str(e)
    
    return dashboard


def generate_content_intelligence_report(
    podcast_name: str,
    session,
    min_gap_score: float = 0.5,
    episode_range: Optional[int] = None
) -> Dict[str, Any]:
    """Generate combined content intelligence report.
    
    Combines gap analysis, missing links, and diversity insights
    into a comprehensive report with prioritized recommendations.
    
    Args:
        podcast_name: Name of the podcast to analyze
        session: Neo4j session
        min_gap_score: Minimum gap score to include
        episode_range: Limit analysis to last N episodes
        
    Returns:
        Dictionary with complete intelligence report
    """
    # Generate individual reports
    gap_report = generate_gap_report(podcast_name, session)
    links_report = generate_missing_links_report(podcast_name, session)
    diversity_dashboard = generate_diversity_dashboard(podcast_name, session)
    
    # Combine into comprehensive report
    intelligence_report = {
        "podcast_name": podcast_name,
        "report_type": "content_intelligence",
        "generated_at": datetime.now().isoformat(),
        "executive_summary": {},
        "key_findings": [],
        "prioritized_recommendations": [],
        "detailed_analysis": {
            "knowledge_gaps": gap_report,
            "missing_connections": links_report,
            "diversity_metrics": diversity_dashboard
        }
    }
    
    # Generate executive summary
    intelligence_report["executive_summary"] = {
        "total_gaps": gap_report["summary"].get("total_gaps", 0),
        "total_missing_links": links_report["summary"].get("total_missing_links", 0),
        "diversity_score": diversity_dashboard["current_metrics"].get("diversity_score", 0),
        "diversity_trend": diversity_dashboard["current_metrics"].get("trend", "unknown"),
        "content_health": _calculate_content_health(gap_report, links_report, diversity_dashboard)
    }
    
    # Compile key findings
    if gap_report["summary"].get("high_score_gaps", 0) > 0:
        intelligence_report["key_findings"].append({
            "category": "gaps",
            "finding": f"Found {gap_report['summary']['high_score_gaps']} significant knowledge gaps",
            "impact": "high"
        })
    
    if links_report["summary"].get("high_score_links", 0) > 0:
        intelligence_report["key_findings"].append({
            "category": "connections",
            "finding": f"Identified {links_report['summary']['high_score_links']} high-value missing connections",
            "impact": "high"
        })
    
    diversity_level = diversity_dashboard["insights"].get("diversity_level", "unknown")
    if diversity_level in ["low", "high"]:
        intelligence_report["key_findings"].append({
            "category": "diversity",
            "finding": diversity_dashboard["insights"].get("diversity_message", ""),
            "impact": "medium" if diversity_level == "high" else "high"
        })
    
    # Prioritize recommendations
    all_recommendations = []
    
    # Add recommendations from each report with source
    for rec in gap_report.get("recommendations", []):
        rec["source"] = "gap_analysis"
        all_recommendations.append(rec)
    
    for rec in links_report.get("recommendations", []):
        rec["source"] = "missing_links"
        all_recommendations.append(rec)
    
    for rec in diversity_dashboard.get("recommendations", []):
        rec["source"] = "diversity"
        all_recommendations.append(rec)
    
    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    all_recommendations.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 3))
    
    intelligence_report["prioritized_recommendations"] = all_recommendations[:10]  # Top 10
    
    logger.info(f"Generated comprehensive intelligence report for {podcast_name}")
    
    return intelligence_report


def _calculate_content_health(gap_report: Dict, links_report: Dict, diversity_dashboard: Dict) -> str:
    """Calculate overall content health score.
    
    Args:
        gap_report: Gap analysis report
        links_report: Missing links report
        diversity_dashboard: Diversity dashboard
        
    Returns:
        Health rating: "excellent", "good", "needs_attention", or "critical"
    """
    # Simple scoring based on key metrics
    score = 0
    max_score = 0
    
    # Gap score (inverse - fewer gaps is better)
    gaps = gap_report["summary"].get("total_gaps", 0)
    if gaps < 5:
        score += 3
    elif gaps < 10:
        score += 2
    elif gaps < 20:
        score += 1
    max_score += 3
    
    # Missing links score (inverse)
    links = links_report["summary"].get("total_missing_links", 0)
    if links < 10:
        score += 3
    elif links < 20:
        score += 2
    elif links < 30:
        score += 1
    max_score += 3
    
    # Diversity score
    diversity = diversity_dashboard["current_metrics"].get("diversity_score", 0)
    if diversity > 0.7:
        score += 3
    elif diversity > 0.5:
        score += 2
    elif diversity > 0.3:
        score += 1
    max_score += 3
    
    # Calculate percentage
    if max_score > 0:
        percentage = score / max_score
        if percentage > 0.8:
            return "excellent"
        elif percentage > 0.6:
            return "good"
        elif percentage > 0.4:
            return "needs_attention"
        else:
            return "critical"
    
    return "unknown"


def export_to_json(report: Dict[str, Any], output_path: Optional[Path] = None) -> str:
    """Export report to JSON format.
    
    Args:
        report: Report dictionary
        output_path: Optional file path to save JSON
        
    Returns:
        JSON string
    """
    json_str = json.dumps(report, indent=2, ensure_ascii=False, default=str)
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json_str)
        logger.info(f"Exported JSON report to {output_path}")
    
    return json_str


def export_to_markdown(report: Dict[str, Any], output_path: Optional[Path] = None) -> str:
    """Export report to Markdown format.
    
    Args:
        report: Report dictionary
        output_path: Optional file path to save Markdown
        
    Returns:
        Markdown string
    """
    md_lines = []
    report_type = report.get("report_type", "report")
    
    # Header
    md_lines.append(f"# {report_type.replace('_', ' ').title()}: {report.get('podcast_name', 'Unknown')}")
    md_lines.append(f"\n*Generated: {report.get('generated_at', 'Unknown')}*\n")
    
    # Executive summary for intelligence reports
    if "executive_summary" in report:
        md_lines.append("## Executive Summary\n")
        summary = report["executive_summary"]
        md_lines.append(f"- **Content Health**: {summary.get('content_health', 'unknown')}")
        md_lines.append(f"- **Knowledge Gaps**: {summary.get('total_gaps', 0)}")
        md_lines.append(f"- **Missing Connections**: {summary.get('total_missing_links', 0)}")
        md_lines.append(f"- **Diversity Score**: {summary.get('diversity_score', 0):.2f}")
        md_lines.append(f"- **Diversity Trend**: {summary.get('diversity_trend', 'unknown')}\n")
    
    # Key findings
    if "key_findings" in report:
        md_lines.append("## Key Findings\n")
        for finding in report["key_findings"]:
            impact = finding.get("impact", "").upper()
            md_lines.append(f"- **[{impact}]** {finding.get('finding', '')}")
        md_lines.append("")
    
    # Recommendations
    if "prioritized_recommendations" in report or "recommendations" in report:
        md_lines.append("## Recommendations\n")
        recommendations = report.get("prioritized_recommendations", report.get("recommendations", []))
        
        for i, rec in enumerate(recommendations, 1):
            priority = rec.get("priority", "medium").upper()
            md_lines.append(f"### {i}. {rec.get('action', 'Action')} [{priority}]\n")
            md_lines.append(f"{rec.get('details', '')}\n")
            
            if "bridge_suggestions" in rec:
                md_lines.append("**Bridge concepts**: " + ", ".join(rec["bridge_suggestions"]))
            if "entities" in rec:
                md_lines.append("**Entities**: " + ", ".join(rec["entities"]))
            md_lines.append("")
    
    # Type-specific sections
    if report_type == "gap_analysis" and "gaps" in report:
        md_lines.append("## Top Knowledge Gaps\n")
        for i, gap in enumerate(report["gaps"][:10], 1):
            md_lines.append(f"### Gap {i} (Score: {gap['gap_score']:.2f})\n")
            md_lines.append(f"- **Cluster 1**: {', '.join(gap['cluster1'])}")
            md_lines.append(f"- **Cluster 2**: {', '.join(gap['cluster2'])}")
            if gap.get("potential_bridges"):
                md_lines.append(f"- **Bridges**: {', '.join(gap['potential_bridges'])}")
            md_lines.append("")
    
    elif report_type == "missing_links" and "by_entity_type" in report:
        md_lines.append("## Missing Links by Type\n")
        for entity_type, data in report["by_entity_type"].items():
            md_lines.append(f"### {entity_type} ({data['count']} total)\n")
            for link in data.get("top_links", [])[:3]:
                md_lines.append(f"- {link['entity1']} ↔ {link['entity2']} (score: {link['connection_score']:.2f})")
                md_lines.append(f"  - Suggestion: {link.get('suggested_topic', 'N/A')}")
            md_lines.append("")
    
    elif report_type == "diversity_dashboard":
        if "topic_distribution" in report:
            md_lines.append("## Top Topics\n")
            for topic, count in list(report["topic_distribution"].items())[:10]:
                md_lines.append(f"- {topic}: {count}")
            md_lines.append("")
        
        if "insights" in report:
            insights = report["insights"]
            md_lines.append("## Insights\n")
            md_lines.append(f"- **Diversity Level**: {insights.get('diversity_level', 'unknown')}")
            md_lines.append(f"- **Balance**: {insights.get('balance_level', 'unknown')}")
            
            if insights.get("over_explored"):
                md_lines.append(f"\n**Over-explored topics**: {', '.join(insights['over_explored'])}")
            if insights.get("under_explored"):
                md_lines.append(f"\n**Under-explored topics**: {', '.join(insights['under_explored'])}")
            md_lines.append("")
    
    markdown_str = "\n".join(md_lines)
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_str)
        logger.info(f"Exported Markdown report to {output_path}")
    
    return markdown_str


def export_to_csv(report: Dict[str, Any], output_path: Optional[Path] = None) -> str:
    """Export report to CSV format.
    
    Different report types generate different CSV structures.
    
    Args:
        report: Report dictionary
        output_path: Optional file path to save CSV
        
    Returns:
        CSV string
    """
    output = StringIO()
    report_type = report.get("report_type", "report")
    
    if report_type == "gap_analysis":
        writer = csv.DictWriter(output, fieldnames=[
            "gap_score", "cluster1_topics", "cluster2_topics", "potential_bridges"
        ])
        writer.writeheader()
        
        for gap in report.get("gaps", []):
            writer.writerow({
                "gap_score": gap["gap_score"],
                "cluster1_topics": "; ".join(gap["cluster1"]),
                "cluster2_topics": "; ".join(gap["cluster2"]),
                "potential_bridges": "; ".join(gap.get("potential_bridges", []))
            })
    
    elif report_type == "missing_links":
        writer = csv.DictWriter(output, fieldnames=[
            "entity1", "entity2", "entity_type", "connection_score",
            "suggested_topic", "entity1_frequency", "entity2_frequency"
        ])
        writer.writeheader()
        
        for link in report.get("missing_links", []):
            writer.writerow({
                "entity1": link["entity1"],
                "entity2": link["entity2"],
                "entity_type": link["entity_type"],
                "connection_score": link["connection_score"],
                "suggested_topic": link.get("suggested_topic", ""),
                "entity1_frequency": link["frequency"]["entity1"],
                "entity2_frequency": link["frequency"]["entity2"]
            })
    
    elif report_type == "diversity_dashboard":
        writer = csv.DictWriter(output, fieldnames=["topic", "count"])
        writer.writeheader()
        
        for topic, count in report.get("topic_distribution", {}).items():
            writer.writerow({"topic": topic, "count": count})
    
    elif report_type == "content_intelligence":
        # For combined report, create summary CSV
        writer = csv.DictWriter(output, fieldnames=[
            "metric", "value", "category"
        ])
        writer.writeheader()
        
        summary = report.get("executive_summary", {})
        writer.writerow({"metric": "content_health", "value": summary.get("content_health", ""), "category": "overall"})
        writer.writerow({"metric": "total_gaps", "value": summary.get("total_gaps", 0), "category": "gaps"})
        writer.writerow({"metric": "total_missing_links", "value": summary.get("total_missing_links", 0), "category": "connections"})
        writer.writerow({"metric": "diversity_score", "value": summary.get("diversity_score", 0), "category": "diversity"})
        writer.writerow({"metric": "diversity_trend", "value": summary.get("diversity_trend", ""), "category": "diversity"})
        
        # Add recommendations
        for i, rec in enumerate(report.get("prioritized_recommendations", [])[:10], 1):
            writer.writerow({
                "metric": f"recommendation_{i}",
                "value": rec.get("action", ""),
                "category": rec.get("priority", "")
            })
    
    csv_str = output.getvalue()
    
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            f.write(csv_str)
        logger.info(f"Exported CSV report to {output_path}")
    
    return csv_str