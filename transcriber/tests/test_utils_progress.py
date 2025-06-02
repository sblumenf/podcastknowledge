"""Unit tests for utils/progress.py module."""

import pytest
import sys
import time
from io import StringIO
from unittest.mock import patch, MagicMock

from src.utils.progress import ProgressBar, simple_progress, log_progress


class TestProgressBar:
    """Test ProgressBar class functionality."""
    
    def test_init(self):
        """Test ProgressBar initialization."""
        pb = ProgressBar(total=100, width=50, prefix="Test")
        assert pb.total == 100
        assert pb.width == 50
        assert pb.prefix == "Test"
        assert pb.current == 0
        assert pb.last_update_time == 0
    
    def test_init_defaults(self):
        """Test ProgressBar with default values."""
        pb = ProgressBar(total=50)
        assert pb.total == 50
        assert pb.width == 50
        assert pb.prefix == "Progress"
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_update_basic(self, mock_stdout):
        """Test basic progress bar update."""
        pb = ProgressBar(total=10, width=10)
        pb.update(5)
        
        output = mock_stdout.getvalue()
        assert "50%" in output
        assert "(5/10)" in output
        assert "█" in output  # Filled portion
        assert "░" in output  # Empty portion
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_update_with_suffix(self, mock_stdout):
        """Test progress bar update with suffix."""
        pb = ProgressBar(total=10)
        pb.update(3, suffix="Processing file.txt")
        
        output = mock_stdout.getvalue()
        assert "Processing file.txt" in output
        assert "30%" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_update_long_suffix_truncation(self, mock_stdout):
        """Test that long suffixes are truncated."""
        pb = ProgressBar(total=10)
        long_suffix = "This is a very long suffix that should be truncated to fit"
        pb.update(5, suffix=long_suffix)
        
        output = mock_stdout.getvalue()
        assert "..." in output
        assert len(output) < 200  # Reasonable line length
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_update_zero_total(self, mock_stdout):
        """Test progress bar with zero total."""
        pb = ProgressBar(total=0)
        pb.update(0)
        
        output = mock_stdout.getvalue()
        assert "0%" in output
        assert "(0/0)" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    @patch('time.time')
    def test_update_with_eta(self, mock_time, mock_stdout):
        """Test progress bar ETA calculation."""
        # Mock time to control elapsed time
        mock_time.side_effect = [0, 10]  # start_time, current_time
        
        pb = ProgressBar(total=100)
        pb.update(25)  # 25% complete after 10 seconds
        
        output = mock_stdout.getvalue()
        assert "ETA:" in output
        # Should estimate ~30 seconds remaining (10s for 25%, so 30s for remaining 75%)
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_update_complete(self, mock_stdout):
        """Test progress bar at 100% completion."""
        pb = ProgressBar(total=10)
        pb.update(10)
        
        output = mock_stdout.getvalue()
        assert "100%" in output
        assert "(10/10)" in output
        # Should have newline when complete
        assert output.endswith("\n")
    
    def test_format_time_seconds(self):
        """Test time formatting for seconds."""
        pb = ProgressBar(total=10)
        assert pb._format_time(45) == "45s"
        assert pb._format_time(59.9) == "59s"
    
    def test_format_time_minutes(self):
        """Test time formatting for minutes."""
        pb = ProgressBar(total=10)
        assert pb._format_time(60) == "1m 0s"
        assert pb._format_time(125) == "2m 5s"
        assert pb._format_time(3599) == "59m 59s"
    
    def test_format_time_hours(self):
        """Test time formatting for hours."""
        pb = ProgressBar(total=10)
        assert pb._format_time(3600) == "1h 0m"
        assert pb._format_time(7265) == "2h 1m"
        assert pb._format_time(10800) == "3h 0m"
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_finish_with_message(self, mock_stdout):
        """Test finishing progress bar with message."""
        pb = ProgressBar(total=10)
        pb.finish("Completed successfully!")
        
        output = mock_stdout.getvalue()
        assert "Progress: Completed successfully!" in output
        assert output.endswith("\n")
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_finish_without_message_incomplete(self, mock_stdout):
        """Test finishing incomplete progress bar without message."""
        pb = ProgressBar(total=10)
        pb.current = 5  # Not complete
        pb.finish()
        
        output = mock_stdout.getvalue()
        assert output == "\n"  # Just a newline
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_finish_without_message_complete(self, mock_stdout):
        """Test finishing complete progress bar without message."""
        pb = ProgressBar(total=10)
        pb.current = 10  # Complete
        pb.finish()
        
        output = mock_stdout.getvalue()
        assert output == ""  # No additional output needed
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_ansi_escape_codes(self, mock_stdout):
        """Test that ANSI escape codes are used for line clearing."""
        pb = ProgressBar(total=10)
        pb.update(5)
        
        output = mock_stdout.getvalue()
        assert "\033[K" in output  # Clear to end of line


class TestSimpleProgress:
    """Test simple_progress function."""
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_simple_progress_basic(self, mock_stdout):
        """Test simple_progress with basic iterable."""
        items = list(simple_progress([1, 2, 3], prefix="Processing"))
        
        assert items == [1, 2, 3]
        output = mock_stdout.getvalue()
        assert "Processing" in output
        assert "100%" in output
        assert "(3/3)" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_simple_progress_empty(self, mock_stdout):
        """Test simple_progress with empty iterable."""
        items = list(simple_progress([], prefix="Processing"))
        
        assert items == []
        output = mock_stdout.getvalue()
        assert output == ""  # No output for empty iterable
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_simple_progress_generator(self, mock_stdout):
        """Test simple_progress with generator."""
        def gen():
            yield from range(5)
        
        items = list(simple_progress(gen(), prefix="Generating"))
        
        assert items == [0, 1, 2, 3, 4]
        output = mock_stdout.getvalue()
        assert "Generating" in output
        assert "(5/5)" in output
    
    @patch('src.utils.progress.ProgressBar')
    def test_simple_progress_calls_progress_bar(self, mock_progress_bar_class):
        """Test that simple_progress properly uses ProgressBar."""
        mock_pb = MagicMock()
        mock_progress_bar_class.return_value = mock_pb
        
        items = list(simple_progress([1, 2, 3], prefix="Test"))
        
        # Verify ProgressBar was created with correct parameters
        mock_progress_bar_class.assert_called_once_with(3, prefix="Test")
        
        # Verify update was called for each item
        assert mock_pb.update.call_count == 3
        mock_pb.update.assert_any_call(1)
        mock_pb.update.assert_any_call(2)
        mock_pb.update.assert_any_call(3)
        
        # Verify finish was called
        mock_pb.finish.assert_called_once()


class TestLogProgress:
    """Test log_progress function."""
    
    def test_log_progress_basic(self, capsys):
        """Test basic log_progress output."""
        log_progress(5, 10, "Processing files")
        
        captured = capsys.readouterr()
        assert "Progress: 50% (5/10) - Processing files" in captured.out
    
    def test_log_progress_complete(self, capsys):
        """Test log_progress at 100%."""
        log_progress(10, 10, "Done")
        
        captured = capsys.readouterr()
        assert "Progress: 100% (10/10) - Done" in captured.out
    
    def test_log_progress_zero_total(self, capsys):
        """Test log_progress with zero total."""
        log_progress(5, 0, "Processing")
        
        captured = capsys.readouterr()
        assert "Progress: 5 items - Processing" in captured.out
    
    def test_log_progress_no_message(self, capsys):
        """Test log_progress without message."""
        log_progress(3, 10)
        
        captured = capsys.readouterr()
        assert "Progress: 30% (3/10) - " in captured.out
    
    def test_log_progress_percentage_calculation(self, capsys):
        """Test various percentage calculations."""
        test_cases = [
            (1, 3, 33),   # 33.33% -> 33%
            (2, 3, 66),   # 66.66% -> 66%
            (1, 4, 25),   # 25%
            (3, 4, 75),   # 75%
            (0, 10, 0),   # 0%
        ]
        
        for current, total, expected_percent in test_cases:
            log_progress(current, total, "Test")
            captured = capsys.readouterr()
            assert f"Progress: {expected_percent}%" in captured.out


class TestProgressBarEdgeCases:
    """Test edge cases and error conditions."""
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_progress_bar_negative_total(self, mock_stdout):
        """Test ProgressBar with negative total."""
        pb = ProgressBar(total=-10)
        pb.update(5)
        
        # Should handle gracefully
        output = mock_stdout.getvalue()
        assert output  # Some output produced
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_progress_bar_current_exceeds_total(self, mock_stdout):
        """Test updating beyond total."""
        pb = ProgressBar(total=10)
        pb.update(15)  # More than total
        
        output = mock_stdout.getvalue()
        assert "150%" in output  # Should show actual percentage
        assert "(15/10)" in output
    
    @patch('sys.stdout', new_callable=StringIO)
    @patch('time.time')
    def test_eta_calculation_edge_cases(self, mock_time, mock_stdout):
        """Test ETA calculation edge cases."""
        # Test with zero current (avoid division by zero)
        mock_time.side_effect = [0, 10]
        pb = ProgressBar(total=100)
        pb.update(0)
        
        output = mock_stdout.getvalue()
        assert "ETA: N/A" in output  # Should show N/A for zero progress
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_unicode_rendering(self, mock_stdout):
        """Test that unicode characters render correctly."""
        pb = ProgressBar(total=10, width=10)
        pb.update(5)
        
        output = mock_stdout.getvalue()
        # Count unicode characters
        filled_count = output.count("█")
        empty_count = output.count("░")
        
        assert filled_count == 5
        assert empty_count == 5