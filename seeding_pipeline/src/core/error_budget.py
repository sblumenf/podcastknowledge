"""
Error Budget Tracking and Management

This module provides functionality for tracking error budgets,
calculating burn rates, and managing SLO compliance.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json

from ..utils.logging import get_logger
from ..api.metrics import get_metrics_collector

logger = get_logger(__name__)


class BurnRateWindow(Enum):
    """Time windows for burn rate calculation."""
    FAST = "1h"  # Fast burn: 1 hour
    MEDIUM = "6h"  # Medium burn: 6 hours
    SLOW = "24h"  # Slow burn: 24 hours
    WEEKLY = "7d"  # Weekly burn rate
    MONTHLY = "30d"  # Monthly burn rate


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    PAGE = "page"


@dataclass
class SLODefinition:
    """Service Level Objective definition."""
    name: str
    description: str
    target: float  # Target percentage (0-100)
    measurement_window: timedelta
    error_budget_minutes: float  # Total error budget in minutes


@dataclass
class ErrorBudgetStatus:
    """Current error budget status."""
    slo_name: str
    current_sli: float  # Current SLI value (0-100)
    target_slo: float  # Target SLO value (0-100)
    budget_total_minutes: float  # Total error budget
    budget_consumed_minutes: float  # Consumed error budget
    budget_remaining_minutes: float  # Remaining error budget
    budget_remaining_percent: float  # Remaining as percentage
    burn_rate_1h: float  # 1-hour burn rate
    burn_rate_6h: float  # 6-hour burn rate
    burn_rate_24h: float  # 24-hour burn rate
    time_until_exhaustion: Optional[float]  # Hours until budget exhausted
    is_burning_fast: bool  # Fast burn alert
    is_burning_slow: bool  # Slow burn alert
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ErrorBudgetAlert:
    """Error budget alert."""
    slo_name: str
    severity: AlertSeverity
    message: str
    burn_rate: float
    budget_remaining_percent: float
    action_required: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ErrorBudgetTracker:
    """Tracks error budgets and burn rates for SLOs."""
    
    def __init__(self, slo_config_path: Optional[str] = None):
        """
        Initialize error budget tracker.
        
        Args:
            slo_config_path: Path to SLO configuration file
        """
        self.slos: Dict[str, SLODefinition] = {}
        self.metrics_collector = get_metrics_collector()
        self._status_cache: Dict[str, ErrorBudgetStatus] = {}
        self._alert_history: List[ErrorBudgetAlert] = []
        
        if slo_config_path:
            self._load_slo_config(slo_config_path)
    
    def _load_slo_config(self, config_path: str):
        """Load SLO definitions from configuration file."""
        try:
            import yaml
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            for slo in config.get('slos', []):
                self.register_slo(
                    name=slo['name'],
                    description=slo['description'],
                    target=slo['objective'],
                    measurement_window_days=30,  # Default to 30 days
                    error_budget_minutes=slo.get('error_budget', {}).get('monthly_budget_minutes', 216)
                )
        except Exception as e:
            logger.error(f"Failed to load SLO config: {e}")
    
    def register_slo(self, name: str, description: str, target: float,
                     measurement_window_days: int = 30,
                     error_budget_minutes: Optional[float] = None):
        """
        Register an SLO for tracking.
        
        Args:
            name: SLO name
            description: SLO description
            target: Target percentage (0-100)
            measurement_window_days: Measurement window in days
            error_budget_minutes: Error budget in minutes (calculated if not provided)
        """
        if error_budget_minutes is None:
            # Calculate error budget based on target and window
            total_minutes = measurement_window_days * 24 * 60
            error_budget_minutes = total_minutes * (100 - target) / 100
        
        self.slos[name] = SLODefinition(
            name=name,
            description=description,
            target=target,
            measurement_window=timedelta(days=measurement_window_days),
            error_budget_minutes=error_budget_minutes
        )
        logger.info(f"Registered SLO: {name} with target {target}% and {error_budget_minutes:.1f} minutes error budget")
    
    def calculate_error_budget_status(self, slo_name: str,
                                    current_sli: float,
                                    good_events: int,
                                    total_events: int,
                                    time_range_hours: int = 720) -> ErrorBudgetStatus:
        """
        Calculate current error budget status.
        
        Args:
            slo_name: Name of the SLO
            current_sli: Current SLI value (0-100)
            good_events: Number of good events
            total_events: Total number of events
            time_range_hours: Time range for calculation (default 30 days)
            
        Returns:
            Error budget status
        """
        if slo_name not in self.slos:
            raise ValueError(f"Unknown SLO: {slo_name}")
        
        slo = self.slos[slo_name]
        
        # Calculate consumed budget
        expected_good_events = total_events * (slo.target / 100)
        actual_bad_events = total_events - good_events
        expected_bad_events = total_events * (1 - slo.target / 100)
        
        # Budget consumed as percentage
        if expected_bad_events > 0:
            budget_consumed_percent = (actual_bad_events / expected_bad_events) * 100
        else:
            budget_consumed_percent = 0 if actual_bad_events == 0 else 100
        
        budget_consumed_minutes = slo.error_budget_minutes * (budget_consumed_percent / 100)
        budget_remaining_minutes = max(0, slo.error_budget_minutes - budget_consumed_minutes)
        budget_remaining_percent = max(0, 100 - budget_consumed_percent)
        
        # Calculate burn rates (simplified - in production, query Prometheus)
        burn_rate_1h = self._calculate_burn_rate(slo_name, 1)
        burn_rate_6h = self._calculate_burn_rate(slo_name, 6)
        burn_rate_24h = self._calculate_burn_rate(slo_name, 24)
        
        # Time until exhaustion
        if burn_rate_1h > 0:
            time_until_exhaustion = budget_remaining_minutes / (burn_rate_1h * 60)
        else:
            time_until_exhaustion = None
        
        # Check for fast/slow burn
        is_burning_fast = burn_rate_1h > 0.02 and burn_rate_6h > 0.01
        is_burning_slow = burn_rate_6h > 0.05 and burn_rate_24h > 0.02
        
        status = ErrorBudgetStatus(
            slo_name=slo_name,
            current_sli=current_sli,
            target_slo=slo.target,
            budget_total_minutes=slo.error_budget_minutes,
            budget_consumed_minutes=budget_consumed_minutes,
            budget_remaining_minutes=budget_remaining_minutes,
            budget_remaining_percent=budget_remaining_percent,
            burn_rate_1h=burn_rate_1h,
            burn_rate_6h=burn_rate_6h,
            burn_rate_24h=burn_rate_24h,
            time_until_exhaustion=time_until_exhaustion,
            is_burning_fast=is_burning_fast,
            is_burning_slow=is_burning_slow
        )
        
        # Cache status
        self._status_cache[slo_name] = status
        
        # Check for alerts
        self._check_alerts(status)
        
        return status
    
    def _calculate_burn_rate(self, slo_name: str, hours: int) -> float:
        """
        Calculate burn rate for a given time window.
        
        In production, this would query Prometheus. Here we provide a simplified version.
        """
        # Simplified calculation - in production, query actual metrics
        if slo_name == "availability":
            # Example: calculate based on recent failures
            if hours == 1:
                return 0.015  # 1.5% burn rate
            elif hours == 6:
                return 0.008  # 0.8% burn rate
            elif hours == 24:
                return 0.005  # 0.5% burn rate
        return 0.0
    
    def _check_alerts(self, status: ErrorBudgetStatus):
        """Check if alerts should be triggered based on status."""
        alerts = []
        
        # Fast burn alert
        if status.is_burning_fast:
            alerts.append(ErrorBudgetAlert(
                slo_name=status.slo_name,
                severity=AlertSeverity.CRITICAL,
                message=f"Fast error budget burn detected for {status.slo_name}",
                burn_rate=status.burn_rate_1h,
                budget_remaining_percent=status.budget_remaining_percent,
                action_required="Investigate immediately and consider rollback"
            ))
        
        # Slow burn alert
        elif status.is_burning_slow:
            alerts.append(ErrorBudgetAlert(
                slo_name=status.slo_name,
                severity=AlertSeverity.WARNING,
                message=f"Slow error budget burn detected for {status.slo_name}",
                burn_rate=status.burn_rate_6h,
                budget_remaining_percent=status.budget_remaining_percent,
                action_required="Monitor closely and prepare mitigation"
            ))
        
        # Low budget alert
        if status.budget_remaining_percent < 20:
            severity = AlertSeverity.CRITICAL if status.budget_remaining_percent < 10 else AlertSeverity.WARNING
            alerts.append(ErrorBudgetAlert(
                slo_name=status.slo_name,
                severity=severity,
                message=f"Low error budget for {status.slo_name}: {status.budget_remaining_percent:.1f}% remaining",
                burn_rate=status.burn_rate_24h,
                budget_remaining_percent=status.budget_remaining_percent,
                action_required="Freeze non-critical changes" if severity == AlertSeverity.WARNING else "Freeze all changes"
            ))
        
        # Budget exhausted
        if status.budget_remaining_percent <= 0:
            alerts.append(ErrorBudgetAlert(
                slo_name=status.slo_name,
                severity=AlertSeverity.PAGE,
                message=f"Error budget exhausted for {status.slo_name}",
                burn_rate=status.burn_rate_1h,
                budget_remaining_percent=0,
                action_required="Initiate incident response, freeze all changes"
            ))
        
        # Store alerts
        for alert in alerts:
            self._alert_history.append(alert)
            self._send_alert(alert)
    
    def _send_alert(self, alert: ErrorBudgetAlert):
        """Send alert through configured channels."""
        logger.warning(f"Error Budget Alert: {alert.message} (Severity: {alert.severity.value})")
        
        # In production, integrate with alerting systems
        # Example: send to Slack, PagerDuty, etc.
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of all SLO error budget statuses."""
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "slos": {},
            "alerts": [],
            "overall_health": "healthy"
        }
        
        critical_count = 0
        warning_count = 0
        
        for slo_name, status in self._status_cache.items():
            summary["slos"][slo_name] = {
                "current_sli": status.current_sli,
                "target_slo": status.target_slo,
                "budget_remaining_percent": status.budget_remaining_percent,
                "burn_rates": {
                    "1h": status.burn_rate_1h,
                    "6h": status.burn_rate_6h,
                    "24h": status.burn_rate_24h
                },
                "is_burning_fast": status.is_burning_fast,
                "is_burning_slow": status.is_burning_slow,
                "time_until_exhaustion_hours": status.time_until_exhaustion
            }
            
            if status.budget_remaining_percent < 10:
                critical_count += 1
            elif status.budget_remaining_percent < 20:
                warning_count += 1
        
        # Recent alerts (last 24 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        recent_alerts = [
            {
                "slo": alert.slo_name,
                "severity": alert.severity.value,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat()
            }
            for alert in self._alert_history
            if alert.timestamp > cutoff_time
        ]
        summary["alerts"] = recent_alerts
        
        # Overall health assessment
        if critical_count > 0:
            summary["overall_health"] = "critical"
        elif warning_count > 0:
            summary["overall_health"] = "warning"
        
        return summary
    
    def export_metrics(self):
        """Export error budget metrics for Prometheus."""
        metrics = []
        
        for slo_name, status in self._status_cache.items():
            # Budget remaining
            metrics.append(
                f'error_budget_remaining_percent{{slo="{slo_name}"}} {status.budget_remaining_percent}'
            )
            
            # Burn rates
            metrics.append(
                f'error_budget_burn_rate{{slo="{slo_name}",window="1h"}} {status.burn_rate_1h}'
            )
            metrics.append(
                f'error_budget_burn_rate{{slo="{slo_name}",window="6h"}} {status.burn_rate_6h}'
            )
            metrics.append(
                f'error_budget_burn_rate{{slo="{slo_name}",window="24h"}} {status.burn_rate_24h}'
            )
            
            # Time until exhaustion
            if status.time_until_exhaustion:
                metrics.append(
                    f'error_budget_time_until_exhaustion_hours{{slo="{slo_name}"}} {status.time_until_exhaustion}'
                )
            
            # Alert states
            metrics.append(
                f'error_budget_fast_burn{{slo="{slo_name}"}} {1 if status.is_burning_fast else 0}'
            )
            metrics.append(
                f'error_budget_slow_burn{{slo="{slo_name}"}} {1 if status.is_burning_slow else 0}'
            )
        
        return "\n".join(metrics)


# Global error budget tracker instance
_error_budget_tracker = None


def get_error_budget_tracker() -> ErrorBudgetTracker:
    """Get or create the global error budget tracker."""
    global _error_budget_tracker
    if _error_budget_tracker is None:
        _error_budget_tracker = ErrorBudgetTracker()
    return _error_budget_tracker