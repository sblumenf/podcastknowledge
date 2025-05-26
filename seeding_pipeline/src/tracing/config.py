"""Configuration for distributed tracing."""

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class TracingConfig:
    """Configuration for distributed tracing."""
    
    # Service identification
    service_name: str = "podcast-kg-pipeline"
    service_version: Optional[str] = None
    environment: str = "development"
    
    # Jaeger configuration
    jaeger_enabled: bool = True
    jaeger_host: str = "localhost"
    jaeger_port: int = 6831
    jaeger_collector_endpoint: Optional[str] = None
    
    # Sampling configuration
    sampling_rate: float = 1.0  # 1.0 = 100% sampling
    
    # Export configuration
    console_export: bool = False
    batch_span_processor: bool = True
    max_queue_size: int = 2048
    max_export_batch_size: int = 512
    export_timeout_millis: int = 30000
    
    # Instrumentation flags
    instrument_neo4j: bool = True
    instrument_redis: bool = True
    instrument_requests: bool = True
    instrument_logging: bool = True
    instrument_langchain: bool = True
    instrument_whisper: bool = True
    
    # Context propagation
    propagators: str = "tracecontext,baggage"
    
    # Custom span attributes
    custom_attributes: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_env(cls) -> "TracingConfig":
        """Create configuration from environment variables."""
        return cls(
            service_name=os.getenv("TRACING_SERVICE_NAME", "podcast-kg-pipeline"),
            service_version=os.getenv("TRACING_SERVICE_VERSION"),
            environment=os.getenv("ENVIRONMENT", "development"),
            
            jaeger_enabled=os.getenv("JAEGER_ENABLED", "true").lower() == "true",
            jaeger_host=os.getenv("JAEGER_HOST", "localhost"),
            jaeger_port=int(os.getenv("JAEGER_PORT", "6831")),
            jaeger_collector_endpoint=os.getenv("JAEGER_COLLECTOR_ENDPOINT"),
            
            sampling_rate=float(os.getenv("TRACING_SAMPLING_RATE", "1.0")),
            
            console_export=os.getenv("TRACING_CONSOLE_EXPORT", "false").lower() == "true",
            batch_span_processor=os.getenv("TRACING_BATCH_PROCESSOR", "true").lower() == "true",
            max_queue_size=int(os.getenv("TRACING_MAX_QUEUE_SIZE", "2048")),
            max_export_batch_size=int(os.getenv("TRACING_MAX_BATCH_SIZE", "512")),
            export_timeout_millis=int(os.getenv("TRACING_EXPORT_TIMEOUT", "30000")),
            
            instrument_neo4j=os.getenv("INSTRUMENT_NEO4J", "true").lower() == "true",
            instrument_redis=os.getenv("INSTRUMENT_REDIS", "true").lower() == "true",
            instrument_requests=os.getenv("INSTRUMENT_REQUESTS", "true").lower() == "true",
            instrument_logging=os.getenv("INSTRUMENT_LOGGING", "true").lower() == "true",
            instrument_langchain=os.getenv("INSTRUMENT_LANGCHAIN", "true").lower() == "true",
            instrument_whisper=os.getenv("INSTRUMENT_WHISPER", "true").lower() == "true",
            
            propagators=os.getenv("OTEL_PROPAGATORS", "tracecontext,baggage"),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "service_name": self.service_name,
            "service_version": self.service_version,
            "environment": self.environment,
            "jaeger": {
                "enabled": self.jaeger_enabled,
                "host": self.jaeger_host,
                "port": self.jaeger_port,
                "collector_endpoint": self.jaeger_collector_endpoint,
            },
            "sampling": {
                "rate": self.sampling_rate,
            },
            "export": {
                "console": self.console_export,
                "batch_processor": self.batch_span_processor,
                "max_queue_size": self.max_queue_size,
                "max_batch_size": self.max_export_batch_size,
                "timeout_millis": self.export_timeout_millis,
            },
            "instrumentation": {
                "neo4j": self.instrument_neo4j,
                "redis": self.instrument_redis,
                "requests": self.instrument_requests,
                "logging": self.instrument_logging,
                "langchain": self.instrument_langchain,
                "whisper": self.instrument_whisper,
            },
            "propagators": self.propagators,
            "custom_attributes": self.custom_attributes,
        }