# Purpose: shared locked runtime for API, workers, and organization agents.
FROM ghcr.io/astral-sh/uv:0.10.12 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
COPY backend ./backend
COPY common ./common
COPY node_simulator ./node_simulator
COPY migrations ./migrations
COPY alembic.ini ./
RUN useradd --uid 10001 --create-home app && mkdir /state && chown -R app:app /app /state
USER app
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
