#!/usr/bin/env python3
"""Run the Podcast Knowledge Pipeline API with distributed tracing."""

import os
import sys
import logging
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from src.api.app import app
from src.utils.logging import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


def main():
    """Run the API server."""
    # Configuration from environment
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "false").lower() == "true"
    workers = int(os.getenv("API_WORKERS", "1"))
    
    logger.info(f"Starting API server on {host}:{port}")
    logger.info(f"Jaeger UI available at http://localhost:16686")
    logger.info(f"API documentation available at http://localhost:{port}/docs")
    
    # Run with uvicorn
    if reload or workers == 1:
        # Development mode with auto-reload
        uvicorn.run(
            "src.api.app:app",
            host=host,
            port=port,
            reload=reload,
            log_config={
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "default": {
                        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    },
                    "access": {
                        "format": '%(asctime)s - %(levelname)s - %(client_addr)s - "%(request_line)s" %(status_code)s',
                    },
                },
                "handlers": {
                    "default": {
                        "formatter": "default",
                        "class": "logging.StreamHandler",
                        "stream": "ext://sys.stdout",
                    },
                    "access": {
                        "formatter": "access",
                        "class": "logging.StreamHandler",
                        "stream": "ext://sys.stdout",
                    },
                },
                "loggers": {
                    "uvicorn": {
                        "handlers": ["default"],
                        "level": "INFO",
                    },
                    "uvicorn.error": {
                        "level": "INFO",
                    },
                    "uvicorn.access": {
                        "handlers": ["access"],
                        "level": "INFO",
                        "propagate": False,
                    },
                },
            },
        )
    else:
        # Production mode with multiple workers
        uvicorn.run(
            "src.api.app:app",
            host=host,
            port=port,
            workers=workers,
            log_config={
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "default": {
                        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    },
                },
                "handlers": {
                    "default": {
                        "formatter": "default",
                        "class": "logging.StreamHandler",
                        "stream": "ext://sys.stdout",
                    },
                },
                "root": {
                    "level": "INFO",
                    "handlers": ["default"],
                },
            },
        )


if __name__ == "__main__":
    main()