FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LIFEVAULT_HOST=0.0.0.0 \
    LIFEVAULT_PORT=8000 \
    LIFEVAULT_DB_PATH=/data/archive.db

WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/app ./app

RUN pip install --no-cache-dir .

EXPOSE 8000
VOLUME ["/data"]

CMD ["python", "-m", "app.main"]
