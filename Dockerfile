FROM python:3.14.7-slim-bookworm@sha256:23c59390fc717bf09f9336908199a0ae75d9c4264bf296123f94ad772fea3b52

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-runtime.txt ./
RUN python -m pip install --requirement requirements-runtime.txt

RUN groupadd --gid 10001 privacy \
    && useradd --uid 10001 --gid privacy --create-home --home-dir /home/privacy privacy

COPY --chown=10001:10001 config ./config
COPY --chown=10001:10001 docs ./docs
COPY --chown=10001:10001 src ./src
COPY --chown=10001:10001 pyproject.toml README.md ./

RUN mkdir --parents /app/output \
    && chown 10001:10001 /app/output \
    && chmod 0750 /app/output /app/config /app/docs

USER 10001:10001

CMD ["python", "-m", "src.cli", "status"]
