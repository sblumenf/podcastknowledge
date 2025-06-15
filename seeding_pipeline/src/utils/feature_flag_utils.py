"""
Utilities for managing feature flags in the podcast knowledge pipeline.

This module provides CLI tools and utilities for feature flag management.
"""

from pathlib import Path
from typing import Dict, Any, Optional
import json
import os
import sys

from ..core.feature_flags import FeatureFlag, get_feature_flag_manager, get_all_flags
from ..utils.logging import get_logger
import yaml
logger = get_logger(__name__)


def print_feature_flags() -> None:
    """Print all feature flags and their current values."""
    flags = get_all_flags()

    print("\n=== Feature Flags Status ===\n")

    # Group by category
    schemaless_flags = []
    component_flags = []

    for flag_name, info in flags.items():
        if "SCHEMALESS" in flag_name or "ENTITY_RESOLUTION_V2" in flag_name:
            schemaless_flags.append((flag_name, info))
        else:
            component_flags.append((flag_name, info))

    # Print schemaless flags
    print("Schemaless Extraction Flags:")
    print("-" * 40)
    for flag_name, info in sorted(schemaless_flags):
        status = "✓ ENABLED" if info["current"] else "✗ DISABLED"
        print(f"{flag_name:40} {status}")
        print(f"  Description: {info['description']}")
        print(f"  Environment Variable: {info['env_var']}")
        print(f"  Default: {info['default']}")
        print()

    # Print component flags
    print("\nComponent Enhancement Flags:")
    print("-" * 40)
    for flag_name, info in sorted(component_flags):
        status = "✓ ENABLED" if info["current"] else "✗ DISABLED"
        print(f"{flag_name:40} {status}")
        print(f"  Description: {info['description']}")
        print(f"  Environment Variable: {info['env_var']}")
        print(f"  Default: {info['default']}")
        print()


def export_feature_flags(
    output_path: Optional[Path] = None, format: str = "json"
) -> Dict[str, Any]:
    """
    Export feature flags to a file.

    Args:
        output_path: Path to write the export (if None, returns dict only)
        format: Export format ('json' or 'yaml')

    Returns:
        Dictionary of feature flags
    """
    flags = get_all_flags()

    # Create export format
    export_data = {"feature_flags": {}, "environment_variables": {}}

    for flag_name, info in flags.items():
        export_data["feature_flags"][flag_name] = {
            "enabled": info["current"],
            "default": info["default"],
            "description": info["description"],
        }
        export_data["environment_variables"][info["env_var"]] = (
            "true" if info["current"] else "false"
        )

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            if format == "json":
                json.dump(export_data, f, indent=2)
            elif format == "yaml":
                yaml.dump(export_data, f, default_flow_style=False)
            else:
                raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Feature flags exported to {output_path}")

    return export_data


def generate_env_template(output_path: Optional[Path] = None) -> str:
    """
    Generate a .env template with all feature flags.

    Args:
        output_path: Path to write the template (if None, returns string only)

    Returns:
        Environment variable template string
    """
    flags = get_all_flags()

    lines = [
        "# Feature Flags for Podcast Knowledge Pipeline",
        "# Generated template - uncomment and modify as needed",
        "",
    ]

    # Group by category
    lines.append("# Core Extraction Flags")
    for flag_name, info in sorted(flags.items()):
        if "ENTITY_RESOLUTION_V2" in flag_name or "LOG_SCHEMA_DISCOVERY" in flag_name:
            lines.append(f"# {info['description']}")
            lines.append(f"# {info['env_var']}={str(info['default']).lower()}")
            lines.append("")

    lines.append("# Component Enhancement Flags")
    for flag_name, info in sorted(flags.items()):
        if "ENTITY_RESOLUTION_V2" not in flag_name and "LOG_SCHEMA_DISCOVERY" not in flag_name:
            lines.append(f"# {info['description']}")
            lines.append(f"# {info['env_var']}={str(info['default']).lower()}")
            lines.append("")

    template = "\n".join(lines)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(template)
        logger.info(f"Environment template written to {output_path}")

    return template


def validate_feature_flags() -> bool:
    """
    Validate that feature flag combinations are valid.

    Returns:
        True if all validations pass
    """
    manager = get_feature_flag_manager()

    # Check for invalid combinations
    issues = []

    # Migration mode requires schemaless extraction
    if manager.is_enabled(FeatureFlag.SCHEMALESS_MIGRATION_MODE) and not manager.is_enabled(
        FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION
    ):
        issues.append(
            "SCHEMALESS_MIGRATION_MODE requires ENABLE_SCHEMALESS_EXTRACTION to be enabled"
        )

    # Entity resolution V2 requires schemaless extraction
    if manager.is_enabled(FeatureFlag.ENABLE_ENTITY_RESOLUTION_V2) and not manager.is_enabled(
        FeatureFlag.ENABLE_SCHEMALESS_EXTRACTION
    ):
        issues.append(
            "ENABLE_ENTITY_RESOLUTION_V2 requires ENABLE_SCHEMALESS_EXTRACTION to be enabled"
        )

    if issues:
        logger.error("Feature flag validation failed:")
        for issue in issues:
            logger.error(f"  - {issue}")
        return False

    logger.info("Feature flag validation passed")
    return True


def set_feature_flag_from_env(flag_name: str, value: str) -> bool:
    """
    Set a feature flag from an environment variable string.

    Args:
        flag_name: Name of the feature flag
        value: String value ("true", "false", "1", "0", etc.)

    Returns:
        True if successfully set
    """
    try:
        # Find the flag
        flag = None
        for f in FeatureFlag:
            if f.value == flag_name:
                flag = f
                break

        if not flag:
            logger.error(f"Unknown feature flag: {flag_name}")
            return False

        # Parse boolean value
        bool_value = value.lower() in ("true", "1", "yes", "on")

        # Set the flag
        manager = get_feature_flag_manager()
        manager.set_flag(flag, bool_value)

        return True

    except Exception as e:
        logger.error(f"Failed to set feature flag {flag_name}: {e}")
        return False


# CLI command functions
def feature_flag_cli_handler(args) -> int:
    """Handle feature flag CLI commands."""
    if args.command == "list":
        print_feature_flags()
    elif args.command == "export":
        export_feature_flags(args.output, args.format)
        print(f"Feature flags exported to {args.output}")
    elif args.command == "env-template":
        generate_env_template(args.output)
        print(f"Environment template generated at {args.output}")
    elif args.command == "validate":
        if validate_feature_flags():
            print("✓ Feature flag validation passed")
        else:
            print("✗ Feature flag validation failed")
            return 1

    return 0
