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

# exec replaces sh with uvicorn so uvicorn is PID 1 and receives signals
# (SIGTERM from Railway) directly — prevents silent SIGKILL on shutdown.
# ${PORT:-8000} still expands correctly via the shell before exec fires.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
