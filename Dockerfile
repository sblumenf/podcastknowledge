# Multi-stage Dockerfile for Podcast Knowledge System
# Supports both transcriber and seeding pipeline

# === Base Stage ===
FROM python:3.9-slim AS base
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# === Transcriber Build Stage ===
FROM base AS transcriber-build
COPY transcriber/requirements.txt /tmp/transcriber-requirements.txt
RUN pip install --no-cache-dir -r /tmp/transcriber-requirements.txt

# === Seeding Pipeline Build Stage ===
FROM base AS seeding-build
COPY seeding_pipeline/requirements.txt /tmp/seeding-requirements.txt
RUN pip install --no-cache-dir -r /tmp/seeding-requirements.txt

# === Transcriber Runtime ===
FROM base AS transcriber
COPY --from=transcriber-build /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=transcriber-build /usr/local/bin /usr/local/bin
COPY transcriber/src /app/transcriber
COPY config/transcriber.yaml /app/config/transcriber.yaml
COPY config/common.yaml /app/config/common.yaml
WORKDIR /app/transcriber
CMD ["python", "cli.py"]

# === Seeding Pipeline Runtime ===
FROM base AS seeding
COPY --from=seeding-build /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=seeding-build /usr/local/bin /usr/local/bin
COPY seeding_pipeline/src /app/seeding
COPY config/seeding.yaml /app/config/seeding.yaml
COPY config/common.yaml /app/config/common.yaml
WORKDIR /app/seeding
CMD ["python", "cli.py"]