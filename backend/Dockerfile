FROM python:3.12-slim

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency + lock files first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies into a project venv
RUN uv sync --no-dev --frozen

# Copy application code
COPY . .

# Create data/logs directories
RUN mkdir -p data logs

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
