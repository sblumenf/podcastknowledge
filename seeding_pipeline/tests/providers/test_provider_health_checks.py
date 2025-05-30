"""
Comprehensive tests for provider health check functionality.

This module tests health checks across all provider types,
including edge cases, error scenarios, and recovery mechanisms.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import time
from datetime import datetime, timedelta

from src.core.exceptions import ProviderError, ConnectionError, ResourceError
from src.providers.audio.base import BaseAudioProvider
from src.providers.llm.base import BaseLLMProvider
from src.providers.graph.base import BaseGraphProvider
from src.providers.embeddings.base import BaseEmbeddingProvider


class TestBaseProviderHealthChecks:
    """Test health check functionality in base providers."""
    
    def test_audio_provider_health_check_healthy(self):
        """Test healthy audio provider health check."""
        class TestAudioProvider(BaseAudioProvider):
            def transcribe(self, audio_path, **kwargs):
                return "transcript"
            
            def diarize(self, audio_path, **kwargs):
                return []
            
            def _provider_specific_health_check(self):
                return {"status": "healthy", "model": "test"}
        
        provider = TestAudioProvider({})
        health = provider.health_check()
        
        assert health["status"] == "healthy"
        assert health["provider"] == "TestAudioProvider"
        assert "timestamp" in health
        assert health["model"] == "test"  # Provider-specific data is merged directly
    
    def test_audio_provider_health_check_unhealthy(self):
        """Test unhealthy audio provider health check."""
        class UnhealthyAudioProvider(BaseAudioProvider):
            def transcribe(self, audio_path, **kwargs):
                return ""
            
            def diarize(self, audio_path, **kwargs):
                return []
            
            def _provider_specific_health_check(self):
                raise ConnectionError("Model not loaded")
        
        provider = UnhealthyAudioProvider({})
        health = provider.health_check()
        
        assert health["status"] == "unhealthy"
        assert "error" in health
        assert "Model not loaded" in health["error"]
    
    def test_llm_provider_health_check_with_test_prompt(self):
        """Test LLM provider health check with test prompt."""
        class TestLLMProvider(BaseLLMProvider):
            def generate(self, prompt, **kwargs):
                return "test response"
            
            def generate_structured(self, prompt, schema, **kwargs):
                return {"result": "structured"}
            
            def count_tokens(self, text):
                return len(text.split())
            
            def _test_connection(self):
                # Simulate API test
                return True
        
        provider = TestLLMProvider({"model": "test-model"})
        health = provider.health_check()
        
        assert health["status"] == "healthy"
        assert health["provider"] == "TestLLMProvider"
        assert "model" in health["details"]
    
    def test_graph_provider_health_check_with_connection_test(self):
        """Test graph provider health check with connection testing."""
        class TestGraphProvider(BaseGraphProvider):
            def __init__(self, config):
                super().__init__(config)
                self._connected = True
            
            def create_node(self, node_type, properties):
                return "node_id"
            
            def create_relationship(self, source_id, target_id, rel_type, properties):
                return "rel_id"
            
            def get_node(self, node_id):
                return {"id": node_id}
            
            def query(self, cypher_query, parameters=None):
                return []
            
            def _test_connection(self):
                if not self._connected:
                    raise ConnectionError("neo4j", "Connection lost")
                return {"version": "4.4.0", "edition": "community"}
        
        provider = TestGraphProvider({})
        health = provider.health_check()
        
        assert health["status"] == "healthy"
        assert health["details"]["database"]["version"] == "4.4.0"
        
        # Simulate connection loss
        provider._connected = False
        health = provider.health_check()
        
        assert health["status"] == "unhealthy"
        assert "Connection lost" in health["error"]
    
    def test_embedding_provider_health_check_with_dimension_test(self):
        """Test embedding provider health check including dimension validation."""
        class TestEmbeddingProvider(BaseEmbeddingProvider):
            def __init__(self, config):
                super().__init__(config)
                self.embedding_dim = 384
            
            def embed(self, text):
                return [0.1] * self.embedding_dim
            
            def embed_batch(self, texts):
                return [self.embed(t) for t in texts]
            
            def _test_model_loading(self):
                # Test if model produces correct dimensions
                test_embedding = self.embed("test")
                if len(test_embedding) != self.embedding_dim:
                    raise ValueError(f"Expected {self.embedding_dim} dimensions, got {len(test_embedding)}")
                return {
                    "model_loaded": True,
                    "embedding_dimensions": self.embedding_dim
                }
        
        provider = TestEmbeddingProvider({})
        health = provider.health_check()
        
        assert health["status"] == "healthy"
        assert health["details"]["embedding_dimensions"] == 384


class TestHealthCheckEdgeCases:
    """Test edge cases in health check functionality."""
    
    def test_health_check_timeout(self):
        """Test health check with timeout."""
        class SlowProvider(BaseAudioProvider):
            def transcribe(self, audio_path, **kwargs):
                return ""
            
            def diarize(self, audio_path, **kwargs):
                return []
            
            def _provider_specific_health_check(self):
                time.sleep(10)  # Simulate slow check
                return {"status": "healthy"}
        
        provider = SlowProvider({"health_check_timeout": 1})
        
        start = time.time()
        health = provider.health_check()
        duration = time.time() - start
        
        # Should timeout quickly
        assert duration < 2
        assert health["status"] == "unhealthy"
        assert "timeout" in health.get("error", "").lower() or "timed out" in health.get("error", "").lower()
    
    def test_health_check_partial_failure(self):
        """Test health check with partial component failures."""
        class PartiallyHealthyProvider(BaseLLMProvider):
            def generate(self, prompt, **kwargs):
                return "response"
            
            def generate_structured(self, prompt, schema, **kwargs):
                raise ProviderError("llm", "Structured generation not available")
            
            def count_tokens(self, text):
                return 10
            
            def _test_connection(self):
                return True
            
            def health_check(self):
                health = super().health_check()
                # Add component-specific checks
                health["components"] = {
                    "text_generation": "healthy",
                    "structured_generation": "unhealthy",
                    "token_counting": "healthy"
                }
                # Overall status is degraded if any component fails
                if any(status == "unhealthy" for status in health["components"].values()):
                    health["status"] = "degraded"
                return health
        
        provider = PartiallyHealthyProvider({})
        health = provider.health_check()
        
        assert health["status"] == "degraded"
        assert health["components"]["text_generation"] == "healthy"
        assert health["components"]["structured_generation"] == "unhealthy"
    
    def test_health_check_resource_constraints(self):
        """Test health check under resource constraints."""
        class ResourceConstrainedProvider(BaseEmbeddingProvider):
            def __init__(self, config):
                super().__init__(config)
                self.memory_limit_mb = config.get("memory_limit_mb", 1000)
            
            def embed(self, text):
                return [0.1] * 384
            
            def embed_batch(self, texts):
                return [self.embed(t) for t in texts]
            
            def _check_resources(self):
                import psutil
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                
                if memory_mb > self.memory_limit_mb:
                    raise ResourceError(
                        f"Memory usage ({memory_mb:.1f}MB) exceeds limit ({self.memory_limit_mb}MB)",
                        resource_type="memory"
                    )
                
                return {
                    "memory_usage_mb": memory_mb,
                    "memory_limit_mb": self.memory_limit_mb,
                    "memory_available": True
                }
            
            def health_check(self):
                health = super().health_check()
                try:
                    resource_status = self._check_resources()
                    health["resources"] = resource_status
                except ResourceError as e:
                    health["status"] = "unhealthy"
                    health["error"] = str(e)
                    health["resources"] = {"memory_available": False}
                return health
        
        # Provider with reasonable limit
        provider = ResourceConstrainedProvider({"memory_limit_mb": 10000})
        health = provider.health_check()
        assert health["resources"]["memory_available"] is True
        
        # Provider with very low limit
        provider_constrained = ResourceConstrainedProvider({"memory_limit_mb": 1})
        health_constrained = provider_constrained.health_check()
        assert health_constrained["status"] == "unhealthy"
        assert health_constrained["resources"]["memory_available"] is False
    
    def test_health_check_recovery(self):
        """Test health check recovery after transient failures."""
        class RecoveringProvider(BaseGraphProvider):
            def __init__(self, config):
                super().__init__(config)
                self.fail_count = 0
                self.max_failures = 3
            
            def create_node(self, node_type, properties):
                return "node_id"
            
            def create_relationship(self, source_id, target_id, rel_type, properties):
                return "rel_id"
            
            def get_node(self, node_id):
                return {"id": node_id}
            
            def query(self, cypher_query, parameters=None):
                return []
            
            def _test_connection(self):
                # Fail first few times, then recover
                if self.fail_count < self.max_failures:
                    self.fail_count += 1
                    raise ConnectionError("neo4j", "Temporary connection issue")
                
                # Reset fail count after recovery
                self.fail_count = 0
                return {"status": "connected"}
        
        provider = RecoveringProvider({})
        
        # First few checks should fail
        for i in range(3):
            health = provider.health_check()
            assert health["status"] == "unhealthy"
            assert "Temporary connection issue" in health["error"]
        
        # Next check should succeed (recovery)
        health = provider.health_check()
        assert health["status"] == "healthy"
        
        # Subsequent checks should also succeed
        health = provider.health_check()
        assert health["status"] == "healthy"
    
    def test_health_check_cascading_failures(self):
        """Test health check with cascading component failures."""
        class CascadingFailureProvider(BaseLLMProvider):
            def __init__(self, config):
                super().__init__(config)
                self.api_healthy = True
                self.cache_healthy = True
                self.fallback_healthy = True
            
            def generate(self, prompt, **kwargs):
                if not self.api_healthy:
                    if not self.fallback_healthy:
                        raise ProviderError("llm", "All endpoints failed")
                return "response"
            
            def generate_structured(self, prompt, schema, **kwargs):
                return {}
            
            def count_tokens(self, text):
                return 10
            
            def health_check(self):
                health = {
                    "provider": self.__class__.__name__,
                    "timestamp": datetime.now().isoformat(),
                    "components": {}
                }
                
                # Check primary API
                if self.api_healthy:
                    health["components"]["primary_api"] = "healthy"
                else:
                    health["components"]["primary_api"] = "unhealthy"
                
                # Check cache (depends on API)
                if self.api_healthy and self.cache_healthy:
                    health["components"]["cache"] = "healthy"
                else:
                    health["components"]["cache"] = "unhealthy"
                    self.cache_healthy = False  # Cache fails if API fails
                
                # Check fallback
                if self.fallback_healthy:
                    health["components"]["fallback_api"] = "healthy"
                else:
                    health["components"]["fallback_api"] = "unhealthy"
                
                # Determine overall status
                if all(status == "healthy" for status in health["components"].values()):
                    health["status"] = "healthy"
                elif health["components"].get("primary_api") == "unhealthy" and \
                     health["components"].get("fallback_api") == "healthy":
                    health["status"] = "degraded"
                else:
                    health["status"] = "unhealthy"
                
                return health
        
        provider = CascadingFailureProvider({})
        
        # Initially healthy
        health = provider.health_check()
        assert health["status"] == "healthy"
        assert all(status == "healthy" for status in health["components"].values())
        
        # Primary API fails
        provider.api_healthy = False
        health = provider.health_check()
        assert health["status"] == "degraded"  # Fallback still works
        assert health["components"]["primary_api"] == "unhealthy"
        assert health["components"]["cache"] == "unhealthy"  # Cascading failure
        assert health["components"]["fallback_api"] == "healthy"
        
        # Fallback also fails
        provider.fallback_healthy = False
        health = provider.health_check()
        assert health["status"] == "unhealthy"  # Everything failed
    
    def test_health_check_with_metrics(self):
        """Test health check that includes performance metrics."""
        class MetricsProvider(BaseAudioProvider):
            def __init__(self, config):
                super().__init__(config)
                self.request_times = []
                self.error_count = 0
                self.total_requests = 0
            
            def transcribe(self, audio_path, **kwargs):
                start = time.time()
                self.total_requests += 1
                
                # Simulate variable processing time
                time.sleep(0.01 * (self.total_requests % 5))
                
                # Simulate occasional errors
                if self.total_requests % 10 == 0:
                    self.error_count += 1
                    raise ProviderError("audio", "Transcription failed")
                
                self.request_times.append(time.time() - start)
                return "transcript"
            
            def diarize(self, audio_path, **kwargs):
                return []
            
            def _calculate_metrics(self):
                if not self.request_times:
                    return {
                        "avg_response_time_ms": 0,
                        "error_rate": 0,
                        "requests_processed": 0
                    }
                
                avg_time = sum(self.request_times) / len(self.request_times)
                error_rate = (self.error_count / self.total_requests * 100) if self.total_requests > 0 else 0
                
                return {
                    "avg_response_time_ms": avg_time * 1000,
                    "error_rate": error_rate,
                    "requests_processed": self.total_requests,
                    "p95_response_time_ms": sorted(self.request_times)[int(len(self.request_times) * 0.95)] * 1000 if self.request_times else 0
                }
            
            def health_check(self):
                health = super().health_check()
                metrics = self._calculate_metrics()
                health["metrics"] = metrics
                
                # Determine health based on metrics
                if metrics["error_rate"] > 10:
                    health["status"] = "unhealthy"
                    health["error"] = f"High error rate: {metrics['error_rate']:.1f}%"
                elif metrics["avg_response_time_ms"] > 5000:
                    health["status"] = "degraded"
                    health["warning"] = f"High latency: {metrics['avg_response_time_ms']:.1f}ms"
                
                return health
        
        provider = MetricsProvider({})
        
        # Process some requests
        for i in range(15):
            try:
                provider.transcribe(f"audio_{i}.mp3")
            except ProviderError:
                pass  # Expected for some requests
        
        health = provider.health_check()
        
        assert "metrics" in health
        assert health["metrics"]["requests_processed"] == 15
        assert health["metrics"]["error_rate"] > 0  # Some errors occurred
        assert health["metrics"]["avg_response_time_ms"] > 0
        assert "p95_response_time_ms" in health["metrics"]


class TestHealthCheckIntegration:
    """Test health check integration scenarios."""
    
    def test_coordinated_health_checks(self):
        """Test coordinating health checks across multiple providers."""
        providers = {
            "audio": Mock(health_check=Mock(return_value={"status": "healthy", "provider": "audio"})),
            "llm": Mock(health_check=Mock(return_value={"status": "degraded", "provider": "llm"})),
            "graph": Mock(health_check=Mock(return_value={"status": "unhealthy", "provider": "graph", "error": "Connection failed"})),
            "embedding": Mock(health_check=Mock(return_value={"status": "healthy", "provider": "embedding"}))
        }
        
        # Perform all health checks
        health_results = {}
        overall_status = "healthy"
        
        for name, provider in providers.items():
            health = provider.health_check()
            health_results[name] = health
            
            # Update overall status
            if health["status"] == "unhealthy":
                overall_status = "unhealthy"
            elif health["status"] == "degraded" and overall_status != "unhealthy":
                overall_status = "degraded"
        
        # Verify results
        assert health_results["audio"]["status"] == "healthy"
        assert health_results["llm"]["status"] == "degraded"
        assert health_results["graph"]["status"] == "unhealthy"
        assert health_results["embedding"]["status"] == "healthy"
        assert overall_status == "unhealthy"  # Worst status wins
    
    def test_health_check_circuit_breaker(self):
        """Test circuit breaker pattern in health checks."""
        class CircuitBreakerProvider(BaseGraphProvider):
            def __init__(self, config):
                super().__init__(config)
                self.consecutive_failures = 0
                self.circuit_open = False
                self.circuit_open_time = None
                self.failure_threshold = 3
                self.recovery_timeout = 5  # seconds
            
            def create_node(self, node_type, properties):
                return "node_id"
            
            def create_relationship(self, source_id, target_id, rel_type, properties):
                return "rel_id"
            
            def get_node(self, node_id):
                return {"id": node_id}
            
            def query(self, cypher_query, parameters=None):
                return []
            
            def _test_connection(self):
                # Always fail for this test
                raise ConnectionError("graph", "Connection refused")
            
            def health_check(self):
                # Check if circuit should be closed (recovery period passed)
                if self.circuit_open and self.circuit_open_time:
                    if (datetime.now() - self.circuit_open_time).total_seconds() > self.recovery_timeout:
                        self.circuit_open = False
                        self.consecutive_failures = 0
                
                # If circuit is open, fail fast
                if self.circuit_open:
                    return {
                        "provider": self.__class__.__name__,
                        "status": "unhealthy",
                        "error": "Circuit breaker open",
                        "circuit_breaker": {
                            "state": "open",
                            "consecutive_failures": self.consecutive_failures,
                            "will_retry_after": (
                                self.circuit_open_time + timedelta(seconds=self.recovery_timeout)
                            ).isoformat()
                        },
                        "timestamp": datetime.now().isoformat()
                    }
                
                # Try normal health check
                try:
                    self._test_connection()
                    # If successful, reset failure count
                    self.consecutive_failures = 0
                    return {
                        "provider": self.__class__.__name__,
                        "status": "healthy",
                        "circuit_breaker": {"state": "closed"},
                        "timestamp": datetime.now().isoformat()
                    }
                except Exception as e:
                    self.consecutive_failures += 1
                    
                    # Open circuit if threshold reached
                    if self.consecutive_failures >= self.failure_threshold:
                        self.circuit_open = True
                        self.circuit_open_time = datetime.now()
                    
                    return {
                        "provider": self.__class__.__name__,
                        "status": "unhealthy",
                        "error": str(e),
                        "circuit_breaker": {
                            "state": "open" if self.circuit_open else "closed",
                            "consecutive_failures": self.consecutive_failures
                        },
                        "timestamp": datetime.now().isoformat()
                    }
        
        provider = CircuitBreakerProvider({})
        
        # First few failures should not open circuit
        for i in range(2):
            health = provider.health_check()
            assert health["status"] == "unhealthy"
            assert health["circuit_breaker"]["state"] == "closed"
        
        # Third failure should open circuit
        health = provider.health_check()
        assert health["status"] == "unhealthy"
        assert health["circuit_breaker"]["state"] == "open"
        
        # Subsequent checks should fail fast
        start = time.time()
        health = provider.health_check()
        duration = time.time() - start
        
        assert duration < 0.1  # Should fail fast
        assert health["error"] == "Circuit breaker open"
        assert "will_retry_after" in health["circuit_breaker"]