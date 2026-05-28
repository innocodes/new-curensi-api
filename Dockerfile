FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /install /usr/local

COPY . .

RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Shell form so Railway's $PORT env var is expanded at runtime.
# Falls back to 8000 for local docker compose.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
