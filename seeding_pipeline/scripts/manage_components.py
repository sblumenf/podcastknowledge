#!/usr/bin/env python3
"""
Script to manage component enablement and configuration.

This script provides CLI tools for enabling/disabling components,
analyzing their impact, and managing the cleanup process.
"""

import argparse
import sys
import json
from pathlib import Path
from typing import Dict, Any, List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.feature_flags import FeatureFlag, set_flag, get_all_flags
from src.utils.component_tracker import get_component_tracker
from src.utils.log_utils import get_logger, setup_logging
import yaml

logger = get_logger(__name__)


def enable_component(component_name: str) -> bool:
    """Enable a specific component."""
    flag_map = {
        "timestamp_injection": FeatureFlag.ENABLE_TIMESTAMP_INJECTION,
        "speaker_injection": FeatureFlag.ENABLE_SPEAKER_INJECTION,
        "quote_postprocessing": FeatureFlag.ENABLE_QUOTE_POSTPROCESSING,
        "metadata_enrichment": FeatureFlag.ENABLE_METADATA_ENRICHMENT,
        "entity_resolution_postprocess": FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS,
    }
    
    if component_name not in flag_map:
        logger.error(f"Unknown component: {component_name}")
        return False
    
    set_flag(flag_map[component_name], True)
    logger.info(f"Enabled component: {component_name}")
    return True


def disable_component(component_name: str) -> bool:
    """Disable a specific component."""
    flag_map = {
        "timestamp_injection": FeatureFlag.ENABLE_TIMESTAMP_INJECTION,
        "speaker_injection": FeatureFlag.ENABLE_SPEAKER_INJECTION,
        "quote_postprocessing": FeatureFlag.ENABLE_QUOTE_POSTPROCESSING,
        "metadata_enrichment": FeatureFlag.ENABLE_METADATA_ENRICHMENT,
        "entity_resolution_postprocess": FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS,
    }
    
    if component_name not in flag_map:
        logger.error(f"Unknown component: {component_name}")
        return False
    
    # Check dependencies
    if not check_dependencies_before_disable(component_name):
        return False
    
    set_flag(flag_map[component_name], False)
    logger.info(f"Disabled component: {component_name}")
    return True


def check_dependencies_before_disable(component_name: str) -> bool:
    """Check if it's safe to disable a component."""
    # Load dependency configuration
    dep_file = Path("config/component_dependencies.yml")
    if not dep_file.exists():
        logger.warning("No dependency configuration found")
        return True
    
    with open(dep_file) as f:
        dep_config = yaml.safe_load(f)
    
    # Check if any other component depends on this one
    components = dep_config.get("components", {})
    dependents = []
    
    for comp_name, comp_info in components.items():
        deps = comp_info.get("depends_on", [])
        if component_name in deps:
            dependents.append(comp_name)
    
    if dependents:
        logger.warning(
            f"Component '{component_name}' has dependents: {dependents}. "
            f"Disabling may cause issues."
        )
        response = input("Continue anyway? (y/N): ")
        return response.lower() == 'y'
    
    return True


def list_components() -> None:
    """List all components and their status."""
    print("\n=== Component Status ===\n")
    
    components = {
        "timestamp_injection": FeatureFlag.ENABLE_TIMESTAMP_INJECTION,
        "speaker_injection": FeatureFlag.ENABLE_SPEAKER_INJECTION,
        "quote_postprocessing": FeatureFlag.ENABLE_QUOTE_POSTPROCESSING,
        "metadata_enrichment": FeatureFlag.ENABLE_METADATA_ENRICHMENT,
        "entity_resolution_postprocess": FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS,
    }
    
    flags = get_all_flags()
    
    for comp_name, flag in components.items():
        flag_info = flags.get(flag.value, {})
        status = "✓ ENABLED" if flag_info.get("current", False) else "✗ DISABLED"
        print(f"{comp_name:30} {status}")
        print(f"  {flag_info.get('description', '')}")
        print()


def analyze_component_impact(component_name: str) -> None:
    """Analyze the impact of a specific component."""
    tracker = get_component_tracker()
    report = tracker.generate_impact_report()
    
    component_stats = report.get("components", {}).get(component_name)
    if not component_stats:
        print(f"No impact data found for component: {component_name}")
        return
    
    print(f"\n=== Impact Analysis: {component_name} ===\n")
    print(f"Executions: {component_stats.get('execution_count', 0)}")
    print(f"Total Time: {component_stats.get('total_time', 0):.3f}s")
    print(f"Average Time: {component_stats.get('avg_time', 0):.3f}s")
    print(f"Items Added: {component_stats.get('total_items_added', 0)}")
    print(f"Items Modified: {component_stats.get('total_items_modified', 0)}")
    print(f"Impact Score: {component_stats.get('impact_score', 0)}")
    
    # Show recommendations
    recommendations = [
        r for r in report.get("recommendations", [])
        if r.get("component") == component_name
    ]
    
    if recommendations:
        print("\nRecommendations:")
        for rec in recommendations:
            print(f"- {rec.get('message')}")
            print(f"  Suggestion: {rec.get('suggestion')}")


def analyze_all_components() -> None:
    """Analyze impact of all components."""
    tracker = get_component_tracker()
    report = tracker.generate_impact_report()
    
    print("\n=== Component Impact Summary ===\n")
    
    # Sort by impact score
    components = report.get("components", {})
    sorted_components = sorted(
        components.items(),
        key=lambda x: x[1].get("impact_score", 0),
        reverse=True
    )
    
    print(f"{'Component':<30} {'Impact Score':<15} {'Avg Time':<10} {'Items Added':<12}")
    print("-" * 70)
    
    for comp_name, stats in sorted_components:
        print(f"{comp_name:<30} "
              f"{stats.get('impact_score', 0):<15.2f} "
              f"{stats.get('avg_time', 0):<10.3f} "
              f"{stats.get('total_items_added', 0):<12}")
    
    # Show redundant components
    redundant = tracker.identify_redundant_components()
    if redundant:
        print("\n⚠️  Potentially Redundant Components:")
        for comp in redundant:
            print(f"  - {comp}")
    
    # Show overall recommendations
    print("\n📋 Recommendations:")
    for rec in report.get("recommendations", [])[:5]:  # Top 5 recommendations
        print(f"  - {rec.get('component')}: {rec.get('message')}")


def remove_disabled_components(dry_run: bool = True) -> None:
    """Remove code for disabled components."""
    print("\n=== Component Removal Analysis ===\n")
    
    # Get disabled components
    components = {
        "timestamp_injection": FeatureFlag.ENABLE_TIMESTAMP_INJECTION,
        "speaker_injection": FeatureFlag.ENABLE_SPEAKER_INJECTION,
        "quote_postprocessing": FeatureFlag.ENABLE_QUOTE_POSTPROCESSING,
        "metadata_enrichment": FeatureFlag.ENABLE_METADATA_ENRICHMENT,
        "entity_resolution_postprocess": FeatureFlag.ENABLE_ENTITY_RESOLUTION_POSTPROCESS,
    }
    
    flags = get_all_flags()
    disabled_components = []
    
    for comp_name, flag in components.items():
        flag_info = flags.get(flag.value, {})
        if not flag_info.get("current", False):
            disabled_components.append(comp_name)
    
    if not disabled_components:
        print("No disabled components found.")
        return
    
    print("Disabled components:")
    for comp in disabled_components:
        print(f"  - {comp}")
    
    if dry_run:
        print("\n[DRY RUN] Would remove code for the above components.")
        print("Run with --execute to actually remove code.")
    else:
        print("\n⚠️  This will permanently remove code!")
        response = input("Are you sure? (yes/NO): ")
        if response.lower() == 'yes':
            # Here we would implement actual code removal
            # For safety, we're not implementing this in the demo
            print("Code removal not implemented for safety.")
        else:
            print("Cancelled.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage extraction pipeline components"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List command
    subparsers.add_parser("list", help="List all components and their status")
    
    # Enable command
    enable_parser = subparsers.add_parser("enable", help="Enable a component")
    enable_parser.add_argument("component", help="Component name")
    
    # Disable command
    disable_parser = subparsers.add_parser("disable", help="Disable a component")
    disable_parser.add_argument("component", help="Component name")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze component impact")
    analyze_parser.add_argument(
        "component",
        nargs="?",
        help="Component name (analyze all if not specified)"
    )
    
    # Remove command
    remove_parser = subparsers.add_parser(
        "remove",
        help="Remove disabled component code"
    )
    remove_parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually remove code (default is dry run)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    # Execute command
    if args.command == "list":
        list_components()
    elif args.command == "enable":
        success = enable_component(args.component)
        sys.exit(0 if success else 1)
    elif args.command == "disable":
        success = disable_component(args.component)
        sys.exit(0 if success else 1)
    elif args.command == "analyze":
        if args.component:
            analyze_component_impact(args.component)
        else:
            analyze_all_components()
    elif args.command == "remove":
        remove_disabled_components(dry_run=not args.execute)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()