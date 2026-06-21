# Argus reference image: the released SDK + the basic example bot, so a known
# good version can be run as a container. Published per release to GHCR as
# ghcr.io/astoristhebrave/argus:<version> and :latest.
#
#   docker run -e DISCORD_TOKEN=... -p 9191:9191 ghcr.io/astoristhebrave/argus:latest
#
# Pin to a version tag in production so a mid-development change can never reach
# a deployment; :latest tracks the most recent release.

# Stage 1: build the dashboard SPA.
FROM node:24-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: build the wheel with the SPA bundled in.
FROM python:3.12-slim AS build
WORKDIR /src
COPY . .
COPY --from=web /web/dist/ src/argus/dashboard/static/
RUN pip install --no-cache-dir build && python -m build --wheel

# Stage 3: slim runtime.
FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/AstorisTheBrave/argus"
LABEL org.opencontainers.image.description="Operational metrics for discord.py bots (reference image)."
LABEL org.opencontainers.image.licenses="AGPL-3.0-or-later"
COPY --from=build /src/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl
COPY examples/basic_bot.py /app/bot.py
RUN useradd --system --uid 10001 argus
WORKDIR /app
ENV ARGUS_HOST=0.0.0.0
EXPOSE 9191
USER argus
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:9191/healthz').status==200 else 1)"]
CMD ["python", "bot.py"]
