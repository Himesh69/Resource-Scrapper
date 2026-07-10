# ============================================================
# KnowledgeFlow — Dockerfile
# Multi-stage build for a lean production image.
# Base: python:3.11-slim
# System deps: ffmpeg (audio extraction)
# ============================================================

# Stage 1: Builder
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Download static ffmpeg (handles both amd64 and arm64)
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"; \
    elif [ "$ARCH" = "aarch64" ]; then \
        URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    curl -sSL $URL -o ffmpeg.tar.xz && \
    tar xvf ffmpeg.tar.xz && \
    mv ffmpeg-*-static/ffmpeg /usr/local/bin/ffmpeg && \
    mv ffmpeg-*-static/ffprobe /usr/local/bin/ffprobe && \
    rm -rf ffmpeg*

# Create a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python deps in a separate layer
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Final
FROM python:3.11-slim AS final

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy ffmpeg and ffprobe from builder
COPY --from=builder /usr/local/bin/ffmpeg /usr/local/bin/
COPY --from=builder /usr/local/bin/ffprobe /usr/local/bin/

# Copy application source
COPY . .

# Create cache directory
RUN mkdir -p .cache

# ── Environment ───────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# EasyOCR downloads models to this directory on first run
ENV EASYOCR_MODULE_PATH=/app/.easyocr

# ── Run ───────────────────────────────────────────────────────
CMD ["python", "main.py"]
