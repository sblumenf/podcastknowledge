"""
Component impact tracking for the podcast knowledge pipeline.

This module provides tools to track and analyze the impact of individual
components in the extraction pipeline, helping identify redundant or 
low-impact components that can be removed.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Tuple
import functools
import hashlib
import json
import time

from ..monitoring import get_metrics_collector
from ..utils.logging import get_logger
logger = get_logger(__name__)


@dataclass
class ComponentImpact:
    """Tracks the impact of a single component execution."""
    component_name: str
    execution_time: float
    items_added: int = 0
    items_modified: int = 0
    items_removed: int = 0
    properties_added: Dict[str, int] = field(default_factory=dict)
    relationships_added: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ComponentContribution:
    """Tracks detailed contributions from a component."""
    component_name: str
    contribution_type: str  # e.g., 'entity', 'relationship', 'property'
    count: int = 0
    examples: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    
@dataclass  
class ComponentMetrics:
    """Aggregated metrics for a component."""
    component_name: str
    total_executions: int = 0
    total_execution_time: float = 0.0
    avg_execution_time: float = 0.0
    total_items_added: int = 0
    total_items_modified: int = 0
    total_items_removed: int = 0
    contributions: List[ComponentContribution] = field(default_factory=list)


@dataclass
class ComponentDependency:
    """Tracks dependencies between components."""
    component_name: str
    depends_on: List[str] = field(default_factory=list)
    used_by: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    metadata: Dict[str, Any] = field(default_factory=dict)


class ComponentTracker:
    """Tracks component execution and impact."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize the component tracker.
        
        Args:
            output_dir: Directory to save tracking data
        """
        self.output_dir = output_dir or Path("component_tracking")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.impacts: Dict[str, List[ComponentImpact]] = defaultdict(list)
        self.baseline_results: Dict[str, Any] = {}
        self.metrics = get_metrics_collector()
        
    def track_impact(self, component_name: str) -> 'ImpactContext':
        """
        Create a context for tracking component impact.
        
        Args:
            component_name: Name of the component being tracked
            
        Returns:
            Context manager for tracking
        """
        return ImpactContext(self, component_name)
    
    def record_impact(self, impact: ComponentImpact) -> None:
        """Record a component impact."""
        self.impacts[impact.component_name].append(impact)
        
        # Update metrics
        self.metrics.processing_duration.observe(
            impact.execution_time,
            labels={"stage": f"component_{impact.component_name}"}
        )
        
        # Save to disk
        self._save_impact(impact)
        
    def track_contribution(self, contribution: ComponentContribution) -> None:
        """Track a component contribution."""
        # Save to disk
        self._save_contribution(contribution)
        
    def _save_impact(self, impact: ComponentImpact) -> None:
        """Save impact data to disk."""
        file_path = self.output_dir / f"{impact.component_name}_impacts.jsonl"
        
        with open(file_path, 'a') as f:
            json.dump({
                "component_name": impact.component_name,
                "execution_time": impact.execution_time,
                "items_added": impact.items_added,
                "items_modified": impact.items_modified,
                "items_removed": impact.items_removed,
                "properties_added": impact.properties_added,
                "relationships_added": impact.relationships_added,
                "metadata": impact.metadata,
                "timestamp": impact.timestamp
            }, f)
            f.write('\n')
    
    def _save_contribution(self, contribution: ComponentContribution) -> None:
        """Save contribution data to disk."""
        file_path = self.output_dir / f"{contribution.component_name}_contributions.jsonl"
        
        with open(file_path, 'a') as f:
            json.dump({
                "component_name": contribution.component_name,
                "contribution_type": contribution.contribution_type,
                "count": contribution.count,
                "examples": contribution.examples,
                "metadata": contribution.metadata
            }, f)
            f.write('\n')
    
    def generate_impact_report(self) -> Dict[str, Any]:
        """Generate a comprehensive impact report for all components."""
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "components": {},
            "summary": {
                "total_components": len(self.impacts),
                "total_executions": sum(len(impacts) for impacts in self.impacts.values()),
                "total_time": sum(
                    impact.execution_time 
                    for impacts in self.impacts.values() 
                    for impact in impacts
                )
            }
        }
        
        # Analyze each component
        for component_name, impacts in self.impacts.items():
            component_stats = self._analyze_component(component_name, impacts)
            report["components"][component_name] = component_stats
        
        # Add recommendations
        report["recommendations"] = self._generate_recommendations(report["components"])
        
        return report
    
    def _analyze_component(self, component_name: str, 
                          impacts: List[ComponentImpact]) -> Dict[str, Any]:
        """Analyze impacts for a single component."""
        if not impacts:
            return {}
        
        total_time = sum(impact.execution_time for impact in impacts)
        total_additions = sum(impact.items_added for impact in impacts)
        total_modifications = sum(impact.items_modified for impact in impacts)
        
        # Aggregate property additions
        all_properties = defaultdict(int)
        for impact in impacts:
            for prop, count in impact.properties_added.items():
                all_properties[prop] += count
        
        # Aggregate relationship additions
        all_relationships = defaultdict(int)
        for impact in impacts:
            for rel, count in impact.relationships_added.items():
                all_relationships[rel] += count
        
        return {
            "execution_count": len(impacts),
            "total_time": total_time,
            "avg_time": total_time / len(impacts),
            "total_items_added": total_additions,
            "total_items_modified": total_modifications,
            "avg_items_per_execution": (total_additions + total_modifications) / len(impacts),
            "properties_added": dict(all_properties),
            "relationships_added": dict(all_relationships),
            "impact_score": self._calculate_impact_score(
                total_additions, total_modifications, total_time
            )
        }
    
    def _calculate_impact_score(self, additions: int, modifications: int, 
                               time_spent: float) -> float:
        """Calculate an impact score for a component."""
        # Simple scoring: items per second, weighted by type
        if time_spent == 0:
            return 0.0
        
        score = (additions * 1.0 + modifications * 0.5) / time_spent
        return round(score, 2)
    
    def _generate_recommendations(self, 
                                components: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate recommendations based on component analysis."""
        recommendations = []
        
        # Sort components by impact score
        sorted_components = sorted(
            components.items(),
            key=lambda x: x[1].get("impact_score", 0),
            reverse=True
        )
        
        # Identify low-impact components
        for component_name, stats in sorted_components:
            if stats.get("impact_score", 0) < 0.1:
                recommendations.append({
                    "component": component_name,
                    "type": "low_impact",
                    "message": f"Component has low impact score ({stats['impact_score']})",
                    "suggestion": "Consider removing or optimizing this component"
                })
            
            if stats.get("avg_time", 0) > 5.0:
                recommendations.append({
                    "component": component_name,
                    "type": "slow_execution",
                    "message": f"Component takes {stats['avg_time']:.1f}s on average",
                    "suggestion": "Optimize for performance or move to async processing"
                })
            
            if stats.get("total_items_added", 0) == 0:
                recommendations.append({
                    "component": component_name,
                    "type": "no_additions",
                    "message": "Component adds no new items",
                    "suggestion": "Verify component is functioning correctly or remove if redundant"
                })
        
        return recommendations
    
    def compare_with_baseline(self, baseline_name: str, 
                            current_results: Dict[str, Any]) -> Dict[str, Any]:
        """Compare current results with a baseline."""
        if baseline_name not in self.baseline_results:
            self.baseline_results[baseline_name] = current_results
            return {"status": "baseline_saved"}
        
        baseline = self.baseline_results[baseline_name]
        comparison = {
            "baseline": baseline_name,
            "differences": {},
            "improvements": [],
            "regressions": []
        }
        
        # Compare metrics
        for key in set(baseline.keys()) | set(current_results.keys()):
            if key in baseline and key in current_results:
                baseline_val = baseline[key]
                current_val = current_results[key]
                
                if isinstance(baseline_val, (int, float)) and isinstance(current_val, (int, float)):
                    diff = current_val - baseline_val
                    pct_change = (diff / baseline_val * 100) if baseline_val != 0 else 0
                    
                    comparison["differences"][key] = {
                        "baseline": baseline_val,
                        "current": current_val,
                        "change": diff,
                        "pct_change": pct_change
                    }
                    
                    if pct_change > 10:
                        comparison["improvements"].append(f"{key} improved by {pct_change:.1f}%")
                    elif pct_change < -10:
                        comparison["regressions"].append(f"{key} regressed by {abs(pct_change):.1f}%")
        
        return comparison
    
    def identify_redundant_components(self) -> List[str]:
        """Identify potentially redundant components."""
        redundant = []
        
        for component_name, impacts in self.impacts.items():
            if not impacts:
                continue
            
            # Check if component has minimal impact
            total_impact = sum(
                impact.items_added + impact.items_modified 
                for impact in impacts
            )
            
            if total_impact == 0:
                redundant.append(component_name)
            elif len(impacts) > 10 and total_impact / len(impacts) < 0.1:
                redundant.append(component_name)
        
        return redundant


class ImpactContext:
    """Context manager for tracking component impact."""
    
    def __init__(self, tracker: ComponentTracker, component_name: str):
        self.tracker = tracker
        self.component_name = component_name
        self.start_time = None
        self.impact = None
        self.initial_state = {}
        
    def __enter__(self):
        """Start tracking."""
        self.start_time = time.time()
        self.impact = ComponentImpact(component_name=self.component_name, execution_time=0)
        
        # Capture initial state (would be implemented based on actual data structure)
        self.initial_state = self._capture_state()
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Finish tracking and record impact."""
        self.impact.execution_time = time.time() - self.start_time
        
        # Calculate changes
        final_state = self._capture_state()
        self._calculate_changes(self.initial_state, final_state)
        
        # Record the impact
        self.tracker.record_impact(self.impact)
    
    def _capture_state(self) -> Dict[str, Any]:
        """Capture current state (placeholder - would be implemented based on actual data)."""
        return {
            "item_count": 0,
            "properties": {},
            "relationships": {}
        }
    
    def _calculate_changes(self, initial: Dict[str, Any], final: Dict[str, Any]) -> None:
        """Calculate what changed between states."""
        # This would be implemented based on actual data structures
        # For now, it's a placeholder
        pass
    
    def add_items(self, count: int) -> None:
        """Record items added."""
        self.impact.items_added += count
    
    def modify_items(self, count: int) -> None:
        """Record items modified."""
        self.impact.items_modified += count
    
    def add_properties(self, property_counts: Dict[str, int]) -> None:
        """Record properties added."""
        for prop, count in property_counts.items():
            self.impact.properties_added[prop] = self.impact.properties_added.get(prop, 0) + count
    
    def add_relationships(self, relationship_counts: Dict[str, int]) -> None:
        """Record relationships added."""
        for rel, count in relationship_counts.items():
            self.impact.relationships_added[rel] = self.impact.relationships_added.get(rel, 0) + count
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata about the execution."""
        self.impact.metadata[key] = value


def track_component_impact(name: Optional[str] = None, version: Optional[str] = None):
    """
    Decorator to track component impact.
    
    Args:
        name: Component name (defaults to function name)
        version: Component version (optional)
        
    Example:
        @track_component_impact("segment_preprocessor", "1.0.0")
        def preprocess_segments(segments):
            # Process segments
            return processed_segments
    """
    def decorator(func):
        component_name = name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get or create tracker
            tracker = get_component_tracker()
            
            with tracker.track_impact(component_name) as impact:
                # Execute function
                result = func(*args, **kwargs)
                
                # Try to automatically detect changes
                # This would need to be customized based on return types
                if isinstance(result, list):
                    impact.add_items(len(result))
                elif isinstance(result, dict) and "added" in result:
                    impact.add_items(result.get("added", 0))
                    impact.modify_items(result.get("modified", 0))
                
                return result
        
        # Add marker to indicate this is tracked
        wrapper.__tracked__ = True
        wrapper.__component_name__ = component_name
        
        return wrapper
    return decorator


# Functions for backward compatibility
def analyze_component_impact(component_name: str) -> Dict[str, Any]:
    """Analyze impact of a specific component."""
    tracker = get_component_tracker()
    return tracker.generate_impact_report()["components"].get(component_name, {})


def compare_component_versions(component_name: str, version1: str, version2: str) -> Dict[str, Any]:
    """Compare different versions of a component."""
    # For backward compatibility
    return {
        "component": component_name,
        "version1": version1,
        "version2": version2,
        "comparison": "Use compare_with_baseline instead"
    }


def identify_redundancies() -> List[str]:
    """Identify potentially redundant components."""
    tracker = get_component_tracker()
    return tracker.identify_redundant_components()


# Global tracker instance
_global_tracker: Optional[ComponentTracker] = None


def get_component_tracker() -> ComponentTracker:
    """Get the global component tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = ComponentTracker()
    return _global_tracker


def get_tracker() -> ComponentTracker:
    """Get the global component tracker instance (backward compatibility)."""
    return get_component_tracker()