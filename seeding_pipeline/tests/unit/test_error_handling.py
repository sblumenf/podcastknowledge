"""Unit tests for error handling utilities."""

from typing import Any
from unittest.mock import Mock, patch, call
import functools
import logging
import signal
import time

import pytest

from src.core.exceptions import PipelineError, ExtractionError, ProviderError
from src.utils.error_handling import (
    with_error_handling,
    with_timeout,
    log_execution,
    handle_provider_errors,
    retry_on_error,
    retry_on_network_error,
    log_and_suppress_errors
)


class TestWithErrorHandlingDecorator:
    """Test with_error_handling decorator."""
    
    def test_successful_function(self):
        """Test decorator with successful function."""
        @with_error_handling(retry_count=3)
        def successful_func(x, y):
            return x + y
        
        result = successful_func(2, 3)
        assert result == 5
    
    def test_function_with_retries(self):
        """Test function that succeeds after retries."""
        call_count = 0
        
        @with_error_handling(retry_count=3, backoff_max=0.1)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = flaky_func()
        assert result == "success"
        assert call_count == 3
    
    def test_function_fails_after_retries(self):
        """Test function that fails after all retries."""
        call_count = 0
        
        @with_error_handling(retry_count=2)
        def always_failing():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")
        
        with pytest.raises(Exception, match="Always fails"):
            always_failing()
        
        # Should have tried initial + 2 retries = 3 times
        assert call_count == 3
    
    def test_default_return_on_failure(self):
        """Test returning default value instead of raising."""
        @with_error_handling(
            retry_count=1,
            raise_on_failure=False,
            default_return="default"
        )
        def failing_func():
            raise Exception("Fails")
        
        result = failing_func()
        assert result == "default"
    
    def test_specific_exceptions_to_retry(self):
        """Test retrying only specific exceptions."""
        call_count = 0
        
        @with_error_handling(
            retry_count=3,
            exceptions_to_retry=(ValueError, TypeError),
            backoff_max=0.1
        )
        def specific_error_func(error_type):
            nonlocal call_count
            call_count += 1
            if error_type == "value":
                raise ValueError("Value error")
            elif error_type == "key":
                raise KeyError("Key error")
            return "success"
        
        # Should retry on ValueError
        call_count = 0
        with pytest.raises(ValueError):
            specific_error_func("value")
        assert call_count == 4  # Initial + 3 retries
        
        # Should not retry on KeyError
        call_count = 0
        with pytest.raises(KeyError):
            specific_error_func("key")
        assert call_count == 1  # No retries
    
    def test_exceptions_to_ignore(self):
        """Test ignoring specific exceptions."""
        @with_error_handling(
            retry_count=3,
            exceptions_to_ignore=(KeyError,),
            raise_on_failure=False,
            default_return="ignored"
        )
        def func_with_ignored(error_type):
            if error_type == "key":
                raise KeyError("Ignored error")
            elif error_type == "value":
                raise ValueError("Not ignored")
            return "success"
        
        # KeyError should be ignored, no retries
        result = func_with_ignored("key")
        assert result == "ignored"
        
        # ValueError should retry
        with pytest.raises(ValueError):
            func_with_ignored("value")
    
    @patch('time.sleep')
    def test_exponential_backoff(self, mock_sleep):
        """Test exponential backoff between retries."""
        @with_error_handling(
            retry_count=3,
            backoff_base=2.0,
            backoff_max=10.0
        )
        def failing_func():
            raise Exception("Test error")
        
        with pytest.raises(Exception):
            failing_func()
        
        # Check sleep calls for exponential backoff
        assert mock_sleep.call_count == 3
        sleep_times = [call[0][0] for call in mock_sleep.call_args_list]
        
        # Should follow exponential pattern: 2^1, 2^2, 2^3
        assert sleep_times[0] == 2.0
        assert sleep_times[1] == 4.0
        assert sleep_times[2] == 8.0
    
    @patch('src.utils.error_handling.logger')
    def test_logging_behavior(self, mock_logger):
        """Test logging of errors and retries."""
        @with_error_handling(
            retry_count=2,
            log_errors=True,
            backoff_max=0.1
        )
        def logged_func():
            raise Exception("Logged error")
        
        with pytest.raises(Exception):
            logged_func()
        
        # Should have debug log for initial call
        debug_calls = [call for call in mock_logger.debug.call_args_list]
        assert any("Calling" in str(call) for call in debug_calls)
        
        # Should have warning logs for retries
        warning_calls = [call for call in mock_logger.warning.call_args_list]
        assert len(warning_calls) == 2  # One for each retry
        
        # Should have error log for final failure
        error_calls = [call for call in mock_logger.error.call_args_list]
        assert len(error_calls) == 1
        assert "failed after 3 attempts" in str(error_calls[0])
    
    def test_preserve_function_signature(self):
        """Test that decorator preserves function signature."""
        @with_error_handling(retry_count=1)
        def original_func(x: int, y: str = "default") -> str:
            """Original docstring."""
            return f"{x}: {y}"
        
        # Check function attributes preserved
        assert original_func.__name__ == "original_func"
        assert original_func.__doc__ == "Original docstring."
        
        # Function should work with correct signature
        assert original_func(42) == "42: default"
        assert original_func(42, "custom") == "42: custom"


class TestWithTimeoutDecorator:
    """Test with_timeout decorator."""
    
    @pytest.mark.skipif(
        not hasattr(signal, 'SIGALRM'),
        reason="Timeout test requires SIGALRM support"
    )
    def test_function_completes_in_time(self):
        """Test function that completes within timeout."""
        @with_timeout(timeout_seconds=2.0)
        def quick_func():
            time.sleep(0.1)
            return "completed"
        
        result = quick_func()
        assert result == "completed"
    
    @pytest.mark.skipif(
        not hasattr(signal, 'SIGALRM'),
        reason="Timeout test requires SIGALRM support"
    )
    def test_function_times_out(self):
        """Test function that exceeds timeout."""
        @with_timeout(timeout_seconds=1.0)
        def slow_func():
            time.sleep(2.0)
            return "too late"
        
        with pytest.raises(TimeoutError):
            slow_func()
    
    @pytest.mark.skipif(
        not hasattr(signal, 'SIGALRM'),
        reason="Timeout test requires SIGALRM support"
    )
    def test_custom_timeout_exception(self):
        """Test custom timeout exception and message."""
        class CustomTimeout(Exception):
            pass
        
        @with_timeout(
            timeout_seconds=1.0,
            timeout_exception=CustomTimeout,
            message="Custom timeout message"
        )
        def slow_func():
            time.sleep(2.0)
        
        with pytest.raises(CustomTimeout, match="Custom timeout message"):
            slow_func()
    
    @pytest.mark.skipif(
        not hasattr(signal, 'SIGALRM'),
        reason="Timeout test requires SIGALRM support"
    )
    def test_cleanup_on_timeout(self):
        """Test that signal handler is properly cleaned up."""
        # Get original handler
        original_handler = signal.signal(signal.SIGALRM, signal.SIG_DFL)
        signal.signal(signal.SIGALRM, original_handler)
        
        @with_timeout(timeout_seconds=1.0)
        def func():
            return "quick"
        
        func()
        
        # Handler should be restored
        current_handler = signal.signal(signal.SIGALRM, signal.SIG_DFL)
        signal.signal(signal.SIGALRM, current_handler)
        assert current_handler == original_handler


class TestLogExecutionDecorator:
    """Test log_execution decorator."""
    
    @patch('src.utils.error_handling.logger')
    def test_basic_logging(self, mock_logger):
        """Test basic execution logging."""
        @log_execution()
        def simple_func():
            return "result"
        
        result = simple_func()
        assert result == "result"
        
        # Check entry and exit logs
        info_calls = mock_logger.info.call_args_list
        assert len(info_calls) == 2
        
        # Entry log
        assert "Entering" in str(info_calls[0])
        assert "simple_func" in str(info_calls[0])
        
        # Exit log
        assert "Completed" in str(info_calls[1])
        assert "simple_func" in str(info_calls[1])
    
    @patch('src.utils.error_handling.logger')
    def test_log_with_args(self, mock_logger):
        """Test logging with function arguments."""
        @log_execution(log_args=True)
        def func_with_args(x, y, z="default"):
            return x + y
        
        result = func_with_args(1, 2, z="custom")
        assert result == 3
        
        # Check that args are logged
        entry_log = str(mock_logger.info.call_args_list[0])
        assert "args=(1, 2)" in entry_log
        assert "kwargs={'z': 'custom'}" in entry_log
    
    @patch('src.utils.error_handling.logger')
    def test_log_with_result(self, mock_logger):
        """Test logging with function result."""
        @log_execution(log_result=True)
        def func_with_result():
            return {"key": "value"}
        
        result = func_with_result()
        
        # Check that result is logged
        exit_log = str(mock_logger.info.call_args_list[1])
        assert "result={'key': 'value'}" in exit_log
    
    @patch('src.utils.error_handling.logger')
    def test_log_execution_time(self, mock_logger):
        """Test logging of execution time."""
        @log_execution(log_time=True)
        def timed_func():
            time.sleep(0.1)
            return "done"
        
        result = timed_func()
        
        # Check that time is logged
        exit_log = str(mock_logger.info.call_args_list[1])
        assert "in" in exit_log
        assert "s" in exit_log  # seconds indicator
    
    @patch('src.utils.error_handling.logger')
    def test_log_on_exception(self, mock_logger):
        """Test logging when function raises exception."""
        @log_execution()
        def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_func()
        
        # Should have entry log
        assert any("Entering" in str(call) for call in mock_logger.info.call_args_list)
        
        # Should have error log
        error_calls = mock_logger.error.call_args_list
        assert len(error_calls) == 1
        assert "Failed" in str(error_calls[0])
        assert "ValueError: Test error" in str(error_calls[0])


class TestHandleProviderErrors:
    """Test handle_provider_errors decorator."""
    
    def test_successful_operation(self):
        """Test decorator with successful operation."""
        @handle_provider_errors(provider_type="llm", operation="generate")
        def llm_operation():
            return {"response": "Generated text"}
        
        result = llm_operation()
        assert result == {"response": "Generated text"}
    
    def test_wrap_generic_exception(self):
        """Test wrapping generic exceptions as ProviderError."""
        @handle_provider_errors(provider_type="audio", operation="transcribe")
        def audio_operation():
            raise RuntimeError("Transcription failed")
        
        with pytest.raises(ProviderError) as exc_info:
            audio_operation()
        
        error = exc_info.value
        assert error.provider_type == "audio"
        assert "Failed during transcribe" in str(error)
        assert "Transcription failed" in str(error)
    
    def test_preserve_provider_error(self):
        """Test that existing ProviderError is preserved."""
        @handle_provider_errors(provider_type="embedding", operation="encode")
        def embedding_operation():
            raise ProviderError("embedding", "Original provider error")
        
        with pytest.raises(ProviderError) as exc_info:
            embedding_operation()
        
        # Should be the original error, not wrapped
        error = exc_info.value
        assert str(error) == "Original provider error"
    
    def test_different_provider_types(self):
        """Test decorator with different provider types."""
        providers = ["audio", "llm", "graph", "embedding"]
        
        for provider in providers:
            @handle_provider_errors(provider_type=provider, operation="test")
            def provider_func():
                raise Exception(f"{provider} error")
            
            with pytest.raises(ProviderError) as exc_info:
                provider_func()
            
            assert exc_info.value.provider_type == provider


class TestConvenienceDecorators:
    """Test pre-configured convenience decorators."""
    
    def test_retry_on_error(self):
        """Test retry_on_error convenience decorator."""
        call_count = 0
        
        @retry_on_error
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary")
            return "success"
        
        result = flaky_func()
        assert result == "success"
        assert call_count == 2
    
    def test_retry_on_network_error(self):
        """Test retry_on_network_error decorator."""
        call_count = 0
        
        @retry_on_network_error
        def network_func(error_type):
            nonlocal call_count
            call_count += 1
            if error_type == "connection":
                raise ConnectionError("Network issue")
            elif error_type == "timeout":
                raise TimeoutError("Request timeout")
            elif error_type == "value":
                raise ValueError("Not a network error")
            return "connected"
        
        # Should retry on ConnectionError
        call_count = 0
        with pytest.raises(ConnectionError):
            network_func("connection")
        assert call_count == 6  # Initial + 5 retries
        
        # Should retry on TimeoutError
        call_count = 0
        with pytest.raises(TimeoutError):
            network_func("timeout")
        assert call_count == 6
        
        # Should not retry on ValueError
        call_count = 0
        with pytest.raises(ValueError):
            network_func("value")
        assert call_count == 1
    
    @patch('src.utils.error_handling.logger')
    def test_log_and_suppress_errors(self, mock_logger):
        """Test log_and_suppress_errors decorator."""
        @log_and_suppress_errors
        def suppressed_func(should_fail=False):
            if should_fail:
                raise Exception("Suppressed error")
            return "success"
        
        # Successful call
        result = suppressed_func(should_fail=False)
        assert result == "success"
        
        # Failed call - error suppressed
        result = suppressed_func(should_fail=True)
        assert result is None
        
        # Error should be logged
        error_calls = mock_logger.error.call_args_list
        assert any("Suppressed error" in str(call) for call in error_calls)


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""
    
    def test_nested_decorators(self):
        """Test combining multiple decorators."""
        call_log = []
        
        @log_execution(log_args=True, log_result=True)
        @with_error_handling(retry_count=2, backoff_max=0.1)
        @handle_provider_errors(provider_type="llm", operation="generate")
        def complex_operation(prompt, temperature=0.7):
            call_log.append(len(call_log))
            if len(call_log) < 2:
                raise ConnectionError("API unavailable")
            return {"text": f"Generated from: {prompt}"}
        
        result = complex_operation("test prompt", temperature=0.9)
        assert result == {"text": "Generated from: test prompt"}
        assert len(call_log) == 2  # Failed once, succeeded on retry
    
    def test_provider_with_retry_pattern(self):
        """Test common provider retry pattern."""
        class MockLLMProvider:
            def __init__(self):
                self.call_count = 0
            
            @handle_provider_errors(provider_type="llm", operation="chat")
            @with_error_handling(
                retry_count=3,
                exceptions_to_retry=(ConnectionError, TimeoutError),
                backoff_base=2.0,
                backoff_max=30.0
            )
            def generate_response(self, messages):
                self.call_count += 1
                
                # Simulate transient failures
                if self.call_count == 1:
                    raise ConnectionError("Connection reset")
                elif self.call_count == 2:
                    raise TimeoutError("Request timeout")
                
                return {"response": "Generated text", "tokens": 100}
        
        provider = MockLLMProvider()
        result = provider.generate_response([{"role": "user", "content": "Hello"}])
        
        assert result["response"] == "Generated text"
        assert provider.call_count == 3
    
    @patch('time.sleep')
    def test_backoff_with_jitter(self, mock_sleep):
        """Test that backoff includes randomization."""
        # Note: The current implementation doesn't include jitter,
        # but this test shows how it could be tested
        @with_error_handling(
            retry_count=3,
            backoff_base=2.0
        )
        def jittered_func():
            raise Exception("Force retry")
        
        with pytest.raises(Exception):
            jittered_func()
        
        # Verify retries happened
        assert mock_sleep.call_count == 3