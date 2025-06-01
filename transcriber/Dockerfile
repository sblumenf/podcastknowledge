# Multi-stage Dockerfile for Podcast Transcriber

# Build stage
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && adduser --disabled-password --gecos '' --uid 1000 transcriber

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY src/ src/
COPY config/ config/
COPY setup.py .
COPY README.md .

# Install the package
RUN pip install -e .

# Create necessary directories
RUN mkdir -p data/transcripts logs && \
    chown -R transcriber:transcriber /app

# Switch to non-root user
USER transcriber

# Expose port (if needed for web interface in future)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import src; print('OK')" || exit 1

# Default command
ENTRYPOINT ["python", "-m", "src.cli"]
CMD ["--help"]

# Development stage (optional)
FROM production as development

# Switch back to root for development dependencies
USER root

# Install development dependencies
RUN pip install pytest pytest-asyncio pytest-mock pytest-cov black isort flake8

# Install test dependencies
COPY requirements-dev.txt* ./
RUN if [ -f requirements-dev.txt ]; then pip install -r requirements-dev.txt; fi

# Copy test files
COPY tests/ tests/
COPY pytest.ini .coveragerc Makefile ./

# Create development entrypoint
COPY docker-entrypoint-dev.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint-dev.sh

USER transcriber

ENTRYPOINT ["/usr/local/bin/docker-entrypoint-dev.sh"]
CMD ["pytest"]