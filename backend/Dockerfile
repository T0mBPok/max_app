FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
RUN playwright install --with-deps chromium
COPY src ./src
COPY alembic.ini ./
COPY migration ./migration
RUN uv sync --frozen --no-dev
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
