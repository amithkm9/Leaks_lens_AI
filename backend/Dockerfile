FROM ghcr.io/gitleaks/gitleaks:v8.30.1 AS gitleaks
FROM ghcr.io/astral-sh/uv:0.11.3 AS uv
FROM python:3.12-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
COPY --from=gitleaks /usr/bin/gitleaks /usr/local/bin/gitleaks
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/* && useradd -m -u 10001 analyst
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN mkdir -p /data/uploads /data/staging /data/repos && chown -R analyst:analyst /data /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER analyst
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
