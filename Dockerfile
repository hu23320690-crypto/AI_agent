FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/agent

WORKDIR /app
COPY requirements-lock.txt ./
RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgomp1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir -r requirements-lock.txt \
    && python -m pip check \
    && groupadd --gid 10001 agent \
    && useradd --uid 10001 --gid 10001 --create-home agent

# Copy executable source and reviewed demo inputs, without Git history or run artifacts.
COPY --chown=10001:10001 agent ./agent
COPY --chown=10001:10001 api ./api
COPY --chown=10001:10001 config ./config
COPY --chown=10001:10001 data ./data
COPY --chown=10001:10001 model ./model
COPY --chown=10001:10001 prompts ./prompts
COPY --chown=10001:10001 rag ./rag
COPY --chown=10001:10001 scripts ./scripts
COPY --chown=10001:10001 utils ./utils
RUN mkdir -p /app/rag/chroma_db /app/logs \
    && chown -R 10001:10001 /app/rag/chroma_db /app/logs

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).read()"]
CMD ["python", "-m", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--timeout-graceful-shutdown", "130"]
