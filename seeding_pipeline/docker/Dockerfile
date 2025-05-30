# Multi-stage build for optimal image size
FROM python:3.10-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.10-slim

# Install runtime dependencies (minimal)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash vtt-processor

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PODCAST_KG_LOG_LEVEL=INFO

# Create application directory
WORKDIR /app

# Copy application code
COPY --chown=vtt-processor:vtt-processor . .

# Install the package in production mode
RUN pip install --no-deps -e .

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/checkpoints && \
    chown -R vtt-processor:vtt-processor /app

# Switch to non-root user
USER vtt-processor

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; from src.api.health import health_check; sys.exit(0 if health_check()['healthy'] else 1)"

# Default command for VTT processing
ENTRYPOINT ["python", "-m", "cli"]
CMD ["--help"]