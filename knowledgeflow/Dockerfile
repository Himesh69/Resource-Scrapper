# ============================================================
# KnowledgeFlow — Dockerfile
# Multi-stage build for a lean production image.
# Base: python:3.11-slim
# System deps: ffmpeg (audio extraction), libGL (OpenCV)
# ============================================================

FROM python:3.11-slim AS base

# System dependencies
# - ffmpeg: audio extraction from video files
# - libsm6, libxext6, libgl1: required by OpenCV headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps in a separate layer (for Docker cache efficiency)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

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
