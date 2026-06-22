FROM python:3.11-slim

WORKDIR /app

# git is needed for GitHub submission cloning.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first for better layer caching.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Migrations + alembic config (used when running `alembic upgrade head`).
COPY alembic.ini ./
COPY alembic ./alembic

RUN mkdir -p /app/data
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
