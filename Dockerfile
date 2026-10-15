# Complaint Replay service: widget intake, dashboard, and the built-in demo shop (with its own browser).
# Build: docker build -t complaint-replay .      Run: docker compose up
FROM node:22-slim AS dashboard
WORKDIR /app/dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY dashboard/ ./
RUN npm run build

# Playwright's image already holds Chromium and its system libraries, matching playwright==1.63.0.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble
COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=automatic PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY replay/ replay/
COPY server/ server/
COPY badshop/ badshop/
RUN uv sync --frozen --no-dev
COPY --from=dashboard /app/dashboard/dist dashboard/dist
RUN useradd --create-home app && mkdir -p results workspace && chown -R app results workspace
USER app
EXPOSE 8200
HEALTHCHECK --interval=30s --timeout=5s CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8200/api/v1/me')"
CMD ["uv", "run", "--no-sync", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8200"]
