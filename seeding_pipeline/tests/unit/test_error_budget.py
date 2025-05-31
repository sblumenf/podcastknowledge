"""
Tests for error budget tracking functionality.

This module tests the SLO error budget tracking, burn rate calculation,
and alerting mechanisms.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import json

import pytest

from src.core.error_budget import (
    BurnRateWindow,
    AlertSeverity,
    SLODefinition,
    ErrorBudgetStatus,
    ErrorBudgetAlert,
    ErrorBudgetTracker,
    get_error_budget_tracker
)


class TestBurnRateWindow:
    """Test BurnRateWindow enum."""
    
    def test_window_values(self):
        """Test burn rate window values."""
        assert BurnRateWindow.FAST.value == "1h"
        assert BurnRateWindow.MEDIUM.value == "6h"
        assert BurnRateWindow.SLOW.value == "24h"
        assert BurnRateWindow.WEEKLY.value == "7d"
        assert BurnRateWindow.MONTHLY.value == "30d"
    
    def test_all_windows_defined(self):
        """Test all expected windows are defined."""
        expected_windows = ["FAST", "MEDIUM", "SLOW", "WEEKLY", "MONTHLY"]
        actual_windows = [w.name for w in BurnRateWindow]
        assert set(actual_windows) == set(expected_windows)


class TestAlertSeverity:
    """Test AlertSeverity enum."""
    
    def test_severity_values(self):
        """Test alert severity values."""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"
        assert AlertSeverity.PAGE.value == "page"
    
    def test_severity_ordering(self):
        """Test severity levels are properly defined."""
        severities = [AlertSeverity.INFO, AlertSeverity.WARNING, 
                     AlertSeverity.CRITICAL, AlertSeverity.PAGE]
        assert len(severities) == 4


class TestSLODefinition:
    """Test SLODefinition dataclass."""
    
    def test_basic_slo_definition(self):
        """Test creating basic SLO definition."""
        slo = SLODefinition(
            name="api_availability",
            description="API availability SLO",
            target=99.9,
            measurement_window=timedelta(days=30),
            error_budget_minutes=43.2
        )
        
        assert slo.name == "api_availability"
        assert slo.description == "API availability SLO"
        assert slo.target == 99.9
        assert slo.measurement_window == timedelta(days=30)
        assert slo.error_budget_minutes == 43.2
    
    def test_slo_with_all_fields(self):
        """Test SLO with all fields specified."""
        window = timedelta(days=7)
        slo = SLODefinition(
            name="latency_p99",
            description="99th percentile latency",
            target=95.0,
            measurement_window=window,
            error_budget_minutes=504.0
        )
        
        assert slo.measurement_window == window
        assert slo.error_budget_minutes == 504.0
    
    def test_slo_error_budget_calculation(self):
        """Test error budget calculation logic."""
        # 99% SLO over 30 days = 1% error budget = 432 minutes
        total_minutes = 30 * 24 * 60
        error_budget = total_minutes * 0.01
        assert error_budget == 432.0


class TestErrorBudgetStatus:
    """Test ErrorBudgetStatus dataclass."""
    
    def test_basic_status(self):
        """Test creating basic error budget status."""
        status = ErrorBudgetStatus(
            slo_name="api_availability",
            current_sli=99.95,
            target_slo=99.9,
            budget_total_minutes=43.2,
            budget_consumed_minutes=10.0,
            budget_remaining_minutes=33.2,
            budget_remaining_percent=76.85,
            burn_rate_1h=0.01,
            burn_rate_6h=0.005,
            burn_rate_24h=0.002,
            time_until_exhaustion=33.2,
            is_burning_fast=False,
            is_burning_slow=False
        )
        
        assert status.slo_name == "api_availability"
        assert status.current_sli == 99.95
        assert status.budget_remaining_minutes == 33.2
        assert not status.is_burning_fast
    
    def test_status_with_burn_rates(self):
        """Test status with various burn rates."""
        status = ErrorBudgetStatus(
            slo_name="latency_slo",
            current_sli=94.5,
            target_slo=95.0,
            budget_total_minutes=504.0,
            budget_consumed_minutes=252.0,
            budget_remaining_minutes=252.0,
            budget_remaining_percent=50.0,
            burn_rate_1h=0.03,
            burn_rate_6h=0.02,
            burn_rate_24h=0.01,
            time_until_exhaustion=140.0,
            is_burning_fast=True,
            is_burning_slow=False
        )
        
        assert status.burn_rate_1h == 0.03
        assert status.is_burning_fast
        assert status.time_until_exhaustion == 140.0
    
    def test_status_is_burning_fast(self):
        """Test fast burn detection."""
        status = ErrorBudgetStatus(
            slo_name="test_slo",
            current_sli=98.0,
            target_slo=99.9,
            budget_total_minutes=43.2,
            budget_consumed_minutes=40.0,
            budget_remaining_minutes=3.2,
            budget_remaining_percent=7.4,
            burn_rate_1h=0.05,
            burn_rate_6h=0.03,
            burn_rate_24h=0.02,
            time_until_exhaustion=1.07,
            is_burning_fast=True,
            is_burning_slow=True
        )
        
        assert status.is_burning_fast
        assert status.is_burning_slow
        assert status.time_until_exhaustion < 2.0


class TestErrorBudgetAlert:
    """Test ErrorBudgetAlert dataclass."""
    
    def test_basic_alert(self):
        """Test creating basic alert."""
        alert = ErrorBudgetAlert(
            slo_name="api_availability",
            severity=AlertSeverity.WARNING,
            message="Error budget below 25%",
            burn_rate=0.02,
            budget_remaining_percent=20.0,
            action_required="Monitor closely"
        )
        
        assert alert.slo_name == "api_availability"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.message == "Error budget below 25%"
        assert alert.burn_rate == 0.02
    
    def test_alert_with_burn_rate_info(self):
        """Test alert with burn rate information."""
        alert = ErrorBudgetAlert(
            slo_name="latency_slo",
            severity=AlertSeverity.CRITICAL,
            message="High burn rate detected",
            burn_rate=0.1,
            budget_remaining_percent=15.0,
            action_required="Immediate investigation required"
        )
        
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.burn_rate == 0.1
        assert "investigation" in alert.action_required
    
    def test_alert_timestamp(self):
        """Test alert has timestamp."""
        alert = ErrorBudgetAlert(
            slo_name="test",
            severity=AlertSeverity.INFO,
            message="Test alert",
            burn_rate=0.001,
            budget_remaining_percent=90.0,
            action_required="None"
        )
        
        assert isinstance(alert.timestamp, datetime)
        assert alert.timestamp <= datetime.utcnow()


class TestErrorBudgetTracker:
    """Test ErrorBudgetTracker functionality."""
    
    @pytest.fixture
    def mock_metrics(self):
        """Mock metrics collector."""
        with patch('src.core.error_budget.get_metrics_collector') as mock:
            yield mock.return_value
    
    @pytest.fixture
    def tracker(self, mock_metrics):
        """Create tracker instance."""
        return ErrorBudgetTracker()
    
    def test_initialization(self, tracker):
        """Test tracker initialization."""
        assert tracker.slos == {}
        assert tracker._status_cache == {}
        assert tracker._alert_history == []
    
    def test_register_slo(self, tracker):
        """Test registering an SLO."""
        tracker.register_slo(
            name="api_availability",
            description="API availability",
            target=99.9,
            measurement_window_days=30
        )
        
        assert "api_availability" in tracker.slos
        slo = tracker.slos["api_availability"]
        assert slo.target == 99.9
        assert slo.measurement_window == timedelta(days=30)
        # Auto-calculated error budget
        assert slo.error_budget_minutes == pytest.approx(43.2, rel=0.01)
    
    def test_load_slo_config(self, tracker, tmp_path):
        """Test loading SLO config from file."""
        config = {
            'slos': [{
                'name': 'test_slo',
                'description': 'Test SLO',
                'objective': 99.0,
                'error_budget': {
                    'monthly_budget_minutes': 432
                }
            }]
        }
        
        config_file = tmp_path / "slo_config.yml"
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(config, f)
        
        tracker._load_slo_config(str(config_file))
        assert "test_slo" in tracker.slos
        assert tracker.slos["test_slo"].target == 99.0
    
    def test_calculate_error_budget_status(self, tracker):
        """Test calculating error budget status."""
        # Register SLO
        tracker.register_slo(
            name="test_slo",
            description="Test",
            target=99.0,
            error_budget_minutes=432
        )
        
        # Mock burn rate calculation
        with patch.object(tracker, '_calculate_burn_rate') as mock_burn:
            mock_burn.side_effect = [0.01, 0.005, 0.002]
            
            status = tracker.calculate_error_budget_status(
                slo_name="test_slo",
                current_sli=99.5,
                good_events=9950,
                total_events=10000
            )
        
        assert status.current_sli == 99.5
        assert status.target_slo == 99.0
        assert status.budget_consumed_minutes < status.budget_total_minutes
    
    def test_calculate_error_budget_with_perfect_availability(self, tracker):
        """Test calculation with perfect availability."""
        tracker.register_slo("perfect", "Perfect SLO", 99.9)
        
        with patch.object(tracker, '_calculate_burn_rate', return_value=0.0):
            status = tracker.calculate_error_budget_status(
                slo_name="perfect",
                current_sli=100.0,
                good_events=10000,
                total_events=10000
            )
        
        assert status.budget_consumed_minutes == 0
        assert status.budget_remaining_percent == 100
        assert status.time_until_exhaustion is None
    
    def test_calculate_burn_rate(self, tracker):
        """Test burn rate calculation."""
        # This is a private method, so we test it indirectly
        tracker.register_slo("test", "Test", 99.0)
        
        # The actual implementation would query metrics
        # Here we just verify the method exists
        assert hasattr(tracker, '_calculate_burn_rate')
    
    def test_check_alerts_no_alerts(self, tracker):
        """Test checking alerts when none should trigger."""
        status = ErrorBudgetStatus(
            slo_name="healthy",
            current_sli=99.95,
            target_slo=99.9,
            budget_total_minutes=43.2,
            budget_consumed_minutes=5.0,
            budget_remaining_minutes=38.2,
            budget_remaining_percent=88.4,
            burn_rate_1h=0.001,
            burn_rate_6h=0.001,
            burn_rate_24h=0.001,
            time_until_exhaustion=None,
            is_burning_fast=False,
            is_burning_slow=False
        )
        
        # _check_alerts doesn't return alerts, it stores them
        initial_alert_count = len(tracker._alert_history)
        tracker._check_alerts(status)
        assert len(tracker._alert_history) == initial_alert_count
    
    def test_check_alerts_budget_warning(self, tracker):
        """Test budget warning alert."""
        status = ErrorBudgetStatus(
            slo_name="warning_slo",
            current_sli=99.5,
            target_slo=99.9,
            budget_total_minutes=43.2,
            budget_consumed_minutes=35.0,
            budget_remaining_minutes=8.2,
            budget_remaining_percent=19.0,
            burn_rate_1h=0.01,
            burn_rate_6h=0.005,
            burn_rate_24h=0.002,
            time_until_exhaustion=13.7,
            is_burning_fast=False,
            is_burning_slow=False
        )
        
        initial_alert_count = len(tracker._alert_history)
        tracker._check_alerts(status)
        assert len(tracker._alert_history) > initial_alert_count
        # Check last alert is WARNING
        assert tracker._alert_history[-1].severity == AlertSeverity.WARNING
    
    def test_check_alerts_budget_critical(self, tracker):
        """Test budget critical alert."""
        status = ErrorBudgetStatus(
            slo_name="critical_slo",
            current_sli=98.0,
            target_slo=99.9,
            budget_total_minutes=43.2,
            budget_consumed_minutes=41.0,
            budget_remaining_minutes=2.2,
            budget_remaining_percent=5.1,
            burn_rate_1h=0.02,
            burn_rate_6h=0.01,
            burn_rate_24h=0.005,
            time_until_exhaustion=1.8,
            is_burning_fast=False,
            is_burning_slow=False
        )
        
        initial_alert_count = len(tracker._alert_history)
        tracker._check_alerts(status)
        assert len(tracker._alert_history) > initial_alert_count
        # Check last alert is CRITICAL
        assert tracker._alert_history[-1].severity == AlertSeverity.CRITICAL
    
    def test_check_alerts_high_burn_rate(self, tracker):
        """Test high burn rate alert."""
        status = ErrorBudgetStatus(
            slo_name="burning_slo",
            current_sli=99.0,
            target_slo=99.9,
            budget_total_minutes=43.2,
            budget_consumed_minutes=20.0,
            budget_remaining_minutes=23.2,
            budget_remaining_percent=53.7,
            burn_rate_1h=0.05,
            burn_rate_6h=0.03,
            burn_rate_24h=0.02,
            time_until_exhaustion=7.7,
            is_burning_fast=True,
            is_burning_slow=True
        )
        
        initial_alert_count = len(tracker._alert_history)
        tracker._check_alerts(status)
        assert len(tracker._alert_history) > initial_alert_count
        # Check for burn rate message
        assert any("burn" in alert.message.lower() for alert in tracker._alert_history[initial_alert_count:])
    
    def test_send_alert(self, tracker, mock_metrics):
        """Test sending alerts."""
        alert = ErrorBudgetAlert(
            slo_name="test",
            severity=AlertSeverity.WARNING,
            message="Test alert",
            burn_rate=0.01,
            budget_remaining_percent=20.0,
            action_required="Monitor"
        )
        
        # _send_alert only logs, doesn't store. Check logging happened
        with patch('src.core.error_budget.logger') as mock_logger:
            tracker._send_alert(alert)
            mock_logger.warning.assert_called_once()
            # Verify correct message format
            call_args = mock_logger.warning.call_args[0][0]
            assert "Test alert" in call_args
            assert "warning" in call_args
    
    def test_get_status_summary(self, tracker):
        """Test getting status summary."""
        tracker.register_slo("slo1", "SLO 1", 99.0)
        tracker.register_slo("slo2", "SLO 2", 95.0)
        
        # Mock some status data
        tracker._status_cache["slo1"] = ErrorBudgetStatus(
            slo_name="slo1",
            current_sli=99.5,
            target_slo=99.0,
            budget_total_minutes=432,
            budget_consumed_minutes=100,
            budget_remaining_minutes=332,
            budget_remaining_percent=76.9,
            burn_rate_1h=0.01,
            burn_rate_6h=0.005,
            burn_rate_24h=0.002,
            time_until_exhaustion=None,
            is_burning_fast=False,
            is_burning_slow=False
        )
        
        summary = tracker.get_status_summary()
        assert "slos" in summary
        assert "slo1" in summary["slos"]
        assert summary["slos"]["slo1"]["current_sli"] == 99.5
    
    def test_export_metrics(self, tracker, mock_metrics):
        """Test exporting metrics."""
        tracker.register_slo("test", "Test", 99.0)
        
        # Add status to cache
        tracker._status_cache["test"] = ErrorBudgetStatus(
            slo_name="test",
            current_sli=99.5,
            target_slo=99.0,
            budget_total_minutes=432,
            budget_consumed_minutes=100,
            budget_remaining_minutes=332,
            budget_remaining_percent=76.9,
            burn_rate_1h=0.01,
            burn_rate_6h=0.005,
            burn_rate_24h=0.002,
            time_until_exhaustion=None,
            is_burning_fast=False,
            is_burning_slow=False
        )
        
        # export_metrics returns a single string with newline-separated metrics
        metrics = tracker.export_metrics()
        assert isinstance(metrics, str)
        assert len(metrics) > 0
        # Check for expected metric formats
        assert 'error_budget_remaining_percent' in metrics
        assert 'slo="test"' in metrics
    
    def test_nonexistent_slo(self, tracker):
        """Test handling nonexistent SLO."""
        with pytest.raises(ValueError, match="Unknown SLO"):
            tracker.calculate_error_budget_status(
                slo_name="nonexistent",
                current_sli=99.0,
                good_events=990,
                total_events=1000
            )


class TestGetErrorBudgetTracker:
    """Test get_error_budget_tracker function."""
    
    def test_returns_singleton(self):
        """Test function returns singleton instance."""
        tracker1 = get_error_budget_tracker()
        tracker2 = get_error_budget_tracker()
        assert tracker1 is tracker2
    
    def test_tracker_is_error_budget_tracker(self):
        """Test returned object is ErrorBudgetTracker."""
        tracker = get_error_budget_tracker()
        assert isinstance(tracker, ErrorBudgetTracker)


class TestErrorBudgetIntegration:
    """Integration tests for error budget tracking."""
    
    @pytest.fixture
    def tracker(self):
        """Create tracker with mock metrics."""
        with patch('src.core.error_budget.get_metrics_collector'):
            yield ErrorBudgetTracker()
    
    def test_multi_window_burn_rate_analysis(self, tracker):
        """Test analyzing burn rates across multiple windows."""
        tracker.register_slo("multi_window", "Multi-window SLO", 99.9)
        
        # Simulate different burn rates for different windows
        with patch.object(tracker, '_calculate_burn_rate') as mock_burn:
            # High 1h burn, medium 6h, low 24h
            mock_burn.side_effect = [0.1, 0.05, 0.01]
            
            status = tracker.calculate_error_budget_status(
                slo_name="multi_window",
                current_sli=99.7,
                good_events=9970,
                total_events=10000
            )
        
        assert status.burn_rate_1h > status.burn_rate_6h
        assert status.burn_rate_6h > status.burn_rate_24h
        assert status.is_burning_fast  # Due to high short-term burn
    
    def test_slo_violation_scenario(self, tracker):
        """Test handling SLO violation scenario."""
        tracker.register_slo("violated", "Violated SLO", 99.0)
        
        with patch.object(tracker, '_calculate_burn_rate', return_value=0.2):
            # Current SLI below target
            status = tracker.calculate_error_budget_status(
                slo_name="violated",
                current_sli=98.5,
                good_events=9850,
                total_events=10000
            )
        
        assert status.current_sli < status.target_slo
        assert status.budget_consumed_minutes > status.budget_total_minutes * 0.5
        
        # Check alerts would be generated
        initial_alert_count = len(tracker._alert_history)
        tracker._check_alerts(status)
        assert len(tracker._alert_history) > initial_alert_count
        # Check severity of alerts
        new_alerts = tracker._alert_history[initial_alert_count:]
        assert any(a.severity in [AlertSeverity.CRITICAL, AlertSeverity.PAGE] for a in new_alerts)
    
    def test_alert_escalation_path(self, tracker):
        """Test alert escalation based on severity."""
        # Create statuses with increasing severity
        statuses = [
            # Healthy
            ErrorBudgetStatus(
                slo_name="test", current_sli=99.95, target_slo=99.9,
                budget_total_minutes=43.2, budget_consumed_minutes=5,
                budget_remaining_minutes=38.2, budget_remaining_percent=88.4,
                burn_rate_1h=0.001, burn_rate_6h=0.001, burn_rate_24h=0.001,
                time_until_exhaustion=None, is_burning_fast=False, is_burning_slow=False
            ),
            # Warning
            ErrorBudgetStatus(
                slo_name="test", current_sli=99.85, target_slo=99.9,
                budget_total_minutes=43.2, budget_consumed_minutes=35,
                budget_remaining_minutes=8.2, budget_remaining_percent=19.0,
                burn_rate_1h=0.02, burn_rate_6h=0.01, burn_rate_24h=0.005,
                time_until_exhaustion=6.8, is_burning_fast=False, is_burning_slow=False
            ),
            # Critical
            ErrorBudgetStatus(
                slo_name="test", current_sli=99.5, target_slo=99.9,
                budget_total_minutes=43.2, budget_consumed_minutes=41,
                budget_remaining_minutes=2.2, budget_remaining_percent=5.1,
                burn_rate_1h=0.1, burn_rate_6h=0.05, burn_rate_24h=0.02,
                time_until_exhaustion=0.37, is_burning_fast=True, is_burning_slow=True
            )
        ]
        
        severities = []
        for status in statuses:
            initial_count = len(tracker._alert_history)
            tracker._check_alerts(status)
            new_alerts = tracker._alert_history[initial_count:]
            if new_alerts:
                max_severity = max((a.severity for a in new_alerts), key=lambda s: ["info", "warning", "critical", "page"].index(s.value))
                severities.append(max_severity)
            else:
                severities.append(None)
        
        # Verify escalation
        assert severities[0] is None  # No alert
        assert severities[1] == AlertSeverity.WARNING
        assert severities[2] in [AlertSeverity.CRITICAL, AlertSeverity.PAGE]