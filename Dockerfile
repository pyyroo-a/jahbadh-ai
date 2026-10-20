# Jahbadh in one container: the built desk UI served by the Python API.

# Stage 1: build the web UI
FROM node:22-slim AS web
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: the app
FROM python:3.13-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
COPY data/showcase/ ./data/showcase/
COPY --from=web /build/web/dist/ ./web/dist/

# The daily live counter lives on the mounted file share in the cloud.
ENV JAHBADH_STATE_DIR=/data/state \
    JAHBADH_WEB_DIST=/app/web/dist \
    JAHBADH_SHOWCASE_DIR=/app/data/showcase \
    OTEL_PYTHON_FASTAPI_EXCLUDED_URLS=api/health

RUN useradd --create-home --uid 10001 jahbadh \
    && mkdir -p /data/state \
    && chown -R jahbadh:jahbadh /data/state
USER jahbadh

EXPOSE 8000
CMD ["uvicorn", "jahbadh.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
