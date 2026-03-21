FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/alembic.ini /app/alembic.ini
COPY backend/alembic /app/alembic
COPY backend/app /app/app

RUN pip install --no-cache-dir -e .[dev]

COPY scripts/deploy/backend-start.sh /app/backend-start.sh
RUN sed -i 's/\r$//' /app/backend-start.sh && chmod +x /app/backend-start.sh

EXPOSE 8000

CMD ["/app/backend-start.sh"]
