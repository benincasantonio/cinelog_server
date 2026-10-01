FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv==0.10.7

# Copy dependency metadata and install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY . .

# Expose port
EXPOSE 5009

# Run uvicorn
# Note: --reload is removed for production; use docker-compose.local.yml for local development with reload
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5009"]
