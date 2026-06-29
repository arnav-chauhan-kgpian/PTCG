# Pokémon TCG AI — production image
#
# Build:    docker build -t pokemon-ai:latest .
# Run CPU:  docker run --rm -p 8000:8000 pokemon-ai:latest
# Run GPU:  docker run --gpus all --rm -p 8000:8000 pokemon-ai:latest
#
# The default entrypoint launches the FastAPI server on port 8000.
# Override with: docker run pokemon-ai:latest pokemon-ai benchmark
#
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POKEMON_AI_CHECKPOINT="" \
    POKEMON_AI_HOST=0.0.0.0 \
    POKEMON_AI_PORT=8000 \
    POKEMON_AI_LOG_LEVEL=INFO

WORKDIR /app

# Install system dependencies needed for torch CPU wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY EN_Card_Data.csv ./EN_Card_Data.csv

# Install application + minimum dependencies. Heavy ML deps are optional.
RUN pip install -e ".[server]" || pip install -e .

# Create a non-root user and hand over /app. Running as root is unnecessary
# for an HTTP server and a common production-hardening finding.
RUN useradd --create-home --uid 1000 --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Healthcheck hits the FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD curl -fsS "http://localhost:${POKEMON_AI_PORT}/health" || exit 1

EXPOSE 8000

ENTRYPOINT ["pokemon-ai"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
