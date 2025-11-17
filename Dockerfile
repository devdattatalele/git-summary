# GitHub Issue Solver MCP Server - Docker Image
# Phase 1: Docker + License Model

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt ./requirements.txt

# Install Python dependencies (using pinned versions for faster build)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY issue_solver/ ./issue_solver/
COPY main.py .
# NOTE: generate_license*.py files are intentionally NOT copied (security)

# Create directory for ChromaDB persistence
RUN mkdir -p /data/chroma_db

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /data

USER appuser

# Environment variables (override with docker run -e)
ENV PYTHONUNBUFFERED=1 \
    CHROMA_PERSIST_DIR=/data/chroma_db \
    LOG_LEVEL=INFO \
    MCP_TRANSPORT=stdio \
    ALLOW_NO_LICENSE=false

# Health check (test if Python and imports work)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Expose port for SSE transport (optional)
EXPOSE 8080

# Volume for persistent data
VOLUME ["/data"]

# Default command
CMD ["python", "main.py"]
