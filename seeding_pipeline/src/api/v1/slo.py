"""
SLO Status API endpoints

Provides endpoints for checking SLO compliance and error budget status.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from datetime import datetime
import yaml

from ...core.error_budget import get_error_budget_tracker
from ...api.metrics import get_metrics_collector
from ...utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/slo", tags=["slo"])


@router.get("/status")
async def get_slo_status() -> Dict[str, Any]:
    """
    Get current SLO status and error budget information.
    
    Returns:
        Dictionary containing SLO compliance and error budget status
    """
    try:
        tracker = get_error_budget_tracker()
        metrics = get_metrics_collector()
        
        # Calculate current SLIs
        total_processed = metrics.episodes_processed.get()
        total_failed = metrics.episodes_failed.get()
        total_episodes = total_processed + total_failed
        
        if total_episodes > 0:
            availability_sli = (total_processed / total_episodes) * 100
        else:
            availability_sli = 100.0
        
        # Get error budget status for availability
        status = tracker.calculate_error_budget_status(
            slo_name="availability",
            current_sli=availability_sli,
            good_events=int(total_processed),
            total_events=int(total_episodes),
            time_range_hours=720  # 30 days
        )
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "slos": {
                "availability": {
                    "current_sli": round(availability_sli, 2),
                    "target_slo": 99.5,
                    "is_meeting_slo": availability_sli >= 99.5,
                    "error_budget": {
                        "total_minutes": status.budget_total_minutes,
                        "consumed_minutes": round(status.budget_consumed_minutes, 1),
                        "remaining_minutes": round(status.budget_remaining_minutes, 1),
                        "remaining_percent": round(status.budget_remaining_percent, 1),
                        "burn_rates": {
                            "1h": round(status.burn_rate_1h, 3),
                            "6h": round(status.burn_rate_6h, 3),
                            "24h": round(status.burn_rate_24h, 3)
                        },
                        "alerts": {
                            "fast_burn": status.is_burning_fast,
                            "slow_burn": status.is_burning_slow
                        }
                    }
                }
            },
            "overall_status": "healthy" if status.budget_remaining_percent > 20 else "at_risk"
        }
    except Exception as e:
        logger.error(f"Failed to get SLO status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_slo_config() -> Dict[str, Any]:
    """
    Get SLO configuration and definitions.
    
    Returns:
        Dictionary containing SLO definitions and targets
    """
    try:
        # Load SLO config
        with open("/home/sergeblumenfeld/podcastknowledge/modular/podcast_kg_pipeline/config/slo.yml", "r") as f:
            config = yaml.safe_load(f)
        
        # Extract key information
        slo_summary = []
        for slo in config.get("slos", []):
            slo_summary.append({
                "name": slo["name"],
                "description": slo["description"],
                "objective": slo["objective"],
                "type": slo["sli"]["metric_type"],
                "windows": [w["name"] for w in slo.get("windows", [])]
            })
        
        return {
            "slos": slo_summary,
            "error_budget_policies": config.get("error_budget_policies", []),
            "composite_slos": config.get("composite_slos", [])
        }
    except Exception as e:
        logger.error(f"Failed to get SLO config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def get_slo_report(window: str = "24h") -> Dict[str, Any]:
    """
    Generate SLO compliance report for specified time window.
    
    Args:
        window: Time window for report (1h, 24h, 7d, 30d)
        
    Returns:
        Dictionary containing SLO compliance report
    """
    try:
        tracker = get_error_budget_tracker()
        metrics = get_metrics_collector()
        
        # Map window to hours
        window_hours = {
            "1h": 1,
            "24h": 24,
            "7d": 168,
            "30d": 720
        }.get(window, 24)
        
        # Get overall statistics
        summary = tracker.get_status_summary()
        
        # Add performance metrics
        perf_summary = metrics.get_summary()
        
        return {
            "window": window,
            "timestamp": datetime.utcnow().isoformat(),
            "compliance_summary": summary,
            "performance_metrics": perf_summary,
            "recommendations": _generate_recommendations(summary, perf_summary)
        }
    except Exception as e:
        logger.error(f"Failed to generate SLO report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register")
async def register_slo(slo_definition: Dict[str, Any]) -> Dict[str, str]:
    """
    Register a new SLO for tracking.
    
    Args:
        slo_definition: Dictionary containing SLO definition
        
    Returns:
        Success message
    """
    try:
        tracker = get_error_budget_tracker()
        
        # Validate required fields
        required = ["name", "description", "target"]
        for field in required:
            if field not in slo_definition:
                raise ValueError(f"Missing required field: {field}")
        
        # Register SLO
        tracker.register_slo(
            name=slo_definition["name"],
            description=slo_definition["description"],
            target=slo_definition["target"],
            measurement_window_days=slo_definition.get("window_days", 30),
            error_budget_minutes=slo_definition.get("error_budget_minutes")
        )
        
        return {"message": f"SLO '{slo_definition['name']}' registered successfully"}
    except Exception as e:
        logger.error(f"Failed to register SLO: {e}")
        raise HTTPException(status_code=400, detail=str(e))


def _generate_recommendations(summary: Dict[str, Any], perf_metrics: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on SLO status and performance metrics."""
    recommendations = []
    
    # Check overall health
    if summary["overall_health"] == "critical":
        recommendations.append("CRITICAL: Multiple SLOs at risk. Consider freezing deployments.")
    elif summary["overall_health"] == "warning":
        recommendations.append("WARNING: Some SLOs under pressure. Review recent changes.")
    
    # Check specific SLOs
    for slo_name, slo_data in summary.get("slos", {}).items():
        if slo_data["budget_remaining_percent"] < 10:
            recommendations.append(f"SLO '{slo_name}' has less than 10% error budget remaining.")
        
        if slo_data["is_burning_fast"]:
            recommendations.append(f"SLO '{slo_name}' is burning error budget rapidly.")
    
    # Performance recommendations
    if perf_metrics["resources"]["memory_mb"] > 6000:
        recommendations.append("High memory usage detected. Consider scaling or optimization.")
    
    if perf_metrics["performance"]["p95_processing_time"] > 300:
        recommendations.append("Episode processing time exceeding target. Review pipeline efficiency.")
    
    if perf_metrics["episodes"]["success_rate"] < 0.995:
        recommendations.append("Success rate below SLO target. Investigate failure causes.")
    
    # If no issues found
    if not recommendations:
        recommendations.append("All SLOs are healthy. Continue normal operations.")
    
    return recommendations