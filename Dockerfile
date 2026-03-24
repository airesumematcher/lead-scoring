# Multi-stage Dockerfile for Lead Scoring System
# Stage 1: Build dependencies
FROM python:3.10-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime image
FROM python:3.10-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Set PATH to include user site-packages
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy application code
COPY config/ /app/config/
COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY models/ /app/models/
COPY data_processed/ /app/data_processed/
COPY index.html /app/index.html
COPY requirements.txt /app/

# Prepare writable runtime directories
RUN mkdir -p /app/data /app/logs

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default environment variables
ENV DATABASE_URL="sqlite:////app/data/leads.db" \
    LOG_LEVEL="INFO" \
    APP_ENV="production" \
    PYTHONPATH="/app/src"

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "src.lead_scoring.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
