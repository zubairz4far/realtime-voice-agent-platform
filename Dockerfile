FROM node:24-alpine AS client-build
WORKDIR /client
COPY client/package.json client/tsconfig.json client/index.html ./
COPY client/src ./src
RUN npm install --no-audit --no-fund
RUN npm run build

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY pyproject.toml ./
COPY server ./server
RUN pip install --no-cache-dir .
COPY --from=client-build /client/dist ./client/dist
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)"
CMD ["sh", "-c", "uvicorn server.app.main:app --host 0.0.0.0 --port ${PORT} --no-server-header"]
