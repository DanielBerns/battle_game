# Use an official Python runtime with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set working directory
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy dependency definition
COPY pyproject.toml .

# Install dependencies
# --system installs into the system python, avoiding the need for venv activation inside Docker
RUN uv pip install --system -r pyproject.toml

# Copy the entire monorepo
# (We copy everything so server can see 'shared' and client can see 'shared')
COPY shared/ ./shared/
COPY server/ ./server/
COPY client/ ./client/

# Critical: Add /app to PYTHONPATH so 'from shared import ...' works
ENV PYTHONPATH=/app

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
