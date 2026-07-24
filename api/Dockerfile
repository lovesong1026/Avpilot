FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations

ENV PATH="/app/.venv/bin:$PATH"

RUN groupadd --gid 10001 avpilot \
    && useradd --uid 10001 --gid 10001 --create-home avpilot \
    && mkdir -p /app/storage /app/beat-data \
    && chown -R avpilot:avpilot /app/storage /app/beat-data

USER avpilot

CMD ["celery", "-A", "app.worker.celery_app", "worker", "-l", "INFO"]
