# ==============================================================================
# Production Dockerfile for Peregrine Central Arabic AI API — Beta V-001
# Lightweight, multi-stage, rootless, enterprise-ready Python 3.11 container.
# ==============================================================================

FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy package requirements and build wheels
COPY central_runtime_api/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final Runtime Image
FROM python:3.11-slim AS runtime

WORKDIR /app

# Create non-privileged service user and group (appuser: UID 10001, GID 10001)
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/bash -m appuser

# Copy installed Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application package
COPY central_runtime_api /app/central_runtime_api

# Create and set permissions for persistent data directory
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# Declare persistent volume mount point
VOLUME ["/app/data"]

# Configure environment variables
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    CENTRAL_AI_HOST=0.0.0.0 \
    CENTRAL_AI_PORT=8000 \
    CENTRAL_AI_ENV=production \
    CENTRAL_AI_PROVIDER=mock \
    CENTRAL_AI_DATA_DIR=/app/data \
    CENTRAL_AI_CORS_ORIGINS=https://ai.peregrineacademy.in \
    CENTRAL_AI_MAX_BODY_BYTES=2097152 \
    CENTRAL_AI_RATE_LIMIT_RPM=60

USER appuser

EXPOSE 8000

# Health check against native /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

ENTRYPOINT ["python3", "-m", "central_runtime_api.run"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--server", "asgi"]
