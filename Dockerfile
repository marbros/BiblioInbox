FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv

WORKDIR /app
# 1) Solo copiamos el archivo de config para aprovechar caché
COPY pyproject.toml ./
# 2) Generamos lock y sincronizamos deps
RUN uv lock && uv sync --frozen

# 3) Ahora copiamos el código
COPY app ./app
COPY .env ./.env

# (opcional) lint/format sin romper build
RUN ./.venv/bin/ruff format . && ./.venv/bin/ruff check . || true

FROM python:3.11-slim AS runtime
WORKDIR /app
COPY --from=base /app/.venv ./.venv
COPY app ./app
COPY .env ./.env
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
