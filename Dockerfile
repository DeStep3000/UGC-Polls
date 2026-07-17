# syntax=docker/dockerfile:1.6

FROM python:3.12-slim AS builder
WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && pip install --no-cache-dir -U pip uv \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN uv pip compile pyproject.toml -o requirements.txt && \
    python -m pip wheel --no-cache-dir -r requirements.txt -w /wheels

FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

RUN groupadd -r app && useradd -r -g app app
COPY --chown=app:app ./app /app

USER app
EXPOSE 8000
