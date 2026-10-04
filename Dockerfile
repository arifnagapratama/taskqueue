FROM node:24-alpine AS frontend
WORKDIR /build
COPY webui/package.json webui/package-lock.json ./
RUN npm ci
COPY webui/index.html webui/vite.config.js ./
COPY webui/src ./src
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.11.24 AS uv
FROM python:3.13-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend ./backend
COPY --from=frontend /build/dist ./dist
RUN useradd --uid 10001 --create-home app && mkdir /data && chown app:app /data
ENV DATABASE_PATH=/data/task-queue.sqlite3 STATIC_PATH=/app/dist PYTHONDONTWRITEBYTECODE=1 PATH=/app/.venv/bin:$PATH
USER app
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3)"
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
