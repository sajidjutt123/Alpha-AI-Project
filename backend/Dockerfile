# Backend image — production.
#
# Build from the REPOSITORY ROOT so the SQL migrations ship inside the image
# (the runner reads MIGRATIONS_DIR, see app/db/migrate.py):
#
#   docker build -f backend/Dockerfile -t alpha-ai-backend .
#   docker run --rm \
#     -e ADMIN_DATABASE_URL=postgresql://... \
#     -e APP_DB_PASSWORD=... \
#     alpha-ai-backend python -m app.db.migrate
#   docker run -p 8000:8000 --env-file .env alpha-ai-backend

FROM python:3.12-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MIGRATIONS_DIR=/app/database/migrations \
    ENVIRONMENT=production

# non-root runtime user
RUN addgroup --system alpha && adduser --system --ingroup alpha alpha

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY backend/app ./app
COPY database/migrations ./database/migrations

USER alpha
EXPOSE 8000

# Liveness from inside the container (slim images have no curl/wget).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"]

# --proxy-headers: the API always sits behind a platform proxy (Railway/
# Render/nginx). Trust forwarded metadata so request.client reflects the
# real caller — rate limiting keys on it (see docs/security-audit.md).
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", \
     "--timeout-keep-alive", "75"]
