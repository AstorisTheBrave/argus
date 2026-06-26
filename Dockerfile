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
# npm intermittently omits a platform-specific optional native binding even when
# the lockfile records it (npm/cli#4828); rolldown then aborts the build with
# "Cannot find native binding". The lockfile pins it as a direct optional dep,
# and this backstop repairs a swallowed install: if the linux-x64 binding is
# missing after npm ci, fetch the exact version rolldown expects (fatal if the
# registry is truly unavailable, rather than silently producing a broken bundle).
RUN npm ci \
    && if ! node -e "require('@rolldown/binding-linux-x64-gnu')" 2>/dev/null; then \
         npm install --no-save --include=optional \
           "@rolldown/binding-linux-x64-gnu@$(node -p "require('rolldown/package.json').version")"; \
       fi
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
