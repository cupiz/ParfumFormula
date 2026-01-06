# ParfumVault Data Auto-Population Module
# Multi-stage build for minimal image size

FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# =============================================================================
# Production image
# =============================================================================

FROM python:3.12-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Ensure scripts are in PATH
ENV PATH=/root/.local/bin:$PATH

# Set working directory
WORKDIR /app

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_HOST=pvdb \
    DB_USER=pvault \
    DB_PASS=pvault \
    DB_NAME=pvault \
    OWNER_ID=1 \
    SCRAPER_DELAY=2 \
    LOG_LEVEL=INFO \
    DATA_DIR=/app/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from db_adapter import get_db; exit(0 if get_db().test_connection() else 1)"

# Default command shows help
CMD ["python", "ingestor.py", "--help"]
