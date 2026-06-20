# syntax=docker/dockerfile:1
# Memorised them All — local, token-free file → knowledge-graph memory (MCP server).
#
# Multi-stage: build into a venv (build tools available), then copy that venv into a
# slim runtime carrying only the Tesseract OCR system tool. The engine is fully
# model-free and offline — no LLM, no Ollama, no embedding model, no network: a digest
# always succeeds deterministically with nothing to download.

FROM python:3.12-slim-bookworm AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY . /src
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install .

FROM python:3.12-slim-bookworm
LABEL org.opencontainers.image.title="Memorised them All" \
      org.opencontainers.image.description="Local, token-free file → knowledge-graph memory for Claude (MCP)." \
      org.opencontainers.image.source="https://github.com/GRU-953/memorised-them-all" \
      org.opencontainers.image.licenses="MIT"
ENV PATH="/opt/venv/bin:$PATH" \
    MTA_HOME=/data \
    MTA_HTTP_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 mta \
 && mkdir -p /data && chown mta:mta /data
COPY --from=build /opt/venv /opt/venv
USER mta
VOLUME ["/data"]
EXPOSE 8765
# Liveness via the unauthenticated /healthz probe (python is already on PATH).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/healthz',timeout=3).status==200 else 1)"
# Default: serve the eight tools over MCP Streamable HTTP. A bearer token is generated
# and printed on first start (see `docker logs`); the store persists in the /data volume.
# Keep it on the host loopback:  docker run -p 127.0.0.1:8765:8765 -v mta:/data ...
ENTRYPOINT ["mta"]
CMD ["serve", "--http", "--allow-remote"]
