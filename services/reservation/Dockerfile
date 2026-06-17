# syntax=docker/dockerfile:1.6
# ──────────── Stage 1: Build ────────────
FROM python:3.12-slim AS build
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY services/reservation/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ──────────── Stage 2: Runtime ────────────
FROM python:3.12-slim AS runtime

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

# Copy Python packages from build stage
COPY --from=build /root/.local /home/appuser/.local

# Copy application code
COPY services/reservation/src/ /app/

# Set ownership
RUN chown -R appuser:appuser /app

# Drop to non-root
USER appuser
WORKDIR /app

# Environment
ENV PATH="/home/appuser/.local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz').read()" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers=2", "--threads=4", "--access-logfile=-", "--error-logfile=-", "main:app"]
