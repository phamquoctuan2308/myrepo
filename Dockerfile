# ---- Stage 1: Build ----
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Stage 2: Production ----
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Security: run as non-root user
RUN useradd -m appuser

# Copy installed packages into the runtime user's home so it can execute
# Alembic/Uvicorn without needing access to /root.
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application code
COPY . .

# Create data directory with correct ownership
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/ready')" || exit 1

CMD ["sh", "-c", "python scripts/prepare_database.py && exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
