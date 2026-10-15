# syntax=docker/dockerfile:1
# Production image for the Syncra backend. The API and the worker share it (see docker-compose.yml).
# Not used for local development.
#
# CPU-only torch by default (small image). On an NVIDIA host build with:
#   docker compose build --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu124

FROM python:3.12-slim AS builder
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /src
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip \
    && pip install torch --index-url ${TORCH_INDEX_URL} \
    && pip install .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app \
    HF_HOME=/models
RUN useradd --create-home --uid 1000 syncra \
    && mkdir -p /models \
    && chown syncra:syncra /models
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=syncra:syncra pyproject.toml alembic.ini ./
COPY --chown=syncra:syncra app ./app
COPY --chown=syncra:syncra config ./config
COPY --chown=syncra:syncra scripts ./scripts
COPY --chown=syncra:syncra migrations ./migrations
USER syncra
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
# One uvicorn worker on purpose: models are cached in-process; more workers = more copies in RAM.
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
