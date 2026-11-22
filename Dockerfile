# Build the frontend once, then serve its static output from the FastAPI app.
FROM node:24-bookworm-slim AS frontend-deps
WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./

FROM frontend-deps AS frontend-build
RUN npm run build

FROM frontend-deps AS frontend-test
CMD ["sh", "-c", "npm run lint && npm run test -- --run && npm run build"]

FROM python:3.12-slim AS python-deps
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt /tmp/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-pol \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && (getent group 999 >/dev/null || groupadd --system --gid 999 scamgraph) \
    && useradd --system --uid 10001 --gid 999 --create-home scamgraph \
    && mkdir -p /var/lib/scamgraph/cache /var/lib/scamgraph-live/cache \
    && chown -R 10001:999 /var/lib/scamgraph /var/lib/scamgraph-live \
    && chmod 0750 /var/lib/scamgraph /var/lib/scamgraph/cache \
        /var/lib/scamgraph-live /var/lib/scamgraph-live/cache

FROM python-deps AS backend-code
COPY backend/ ./backend/

FROM backend-code AS backend-test
CMD ["python", "-m", "pytest", "backend/tests", "-q"]

FROM backend-code AS synthetic-seed
COPY frontend/scripts/seed-synthetic-live-db.py ./frontend/scripts/seed-synthetic-live-db.py
USER scamgraph
CMD ["python", "frontend/scripts/seed-synthetic-live-db.py", "/var/lib/scamgraph/scamgraph.db"]

FROM backend-code AS app
COPY --from=frontend-build /workspace/frontend/dist ./frontend/dist
ENV SCAMGRAPH_CACHE_DIR=/var/lib/scamgraph/cache
USER scamgraph
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
