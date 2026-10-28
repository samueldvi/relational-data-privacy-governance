FROM python:3.15.1-slim-bookworm@sha256:575f8bc12ec26542e0678bc6b60e385218248019d433157ec327264a78c3a853

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade --yes \
    && rm -rf /var/lib/apt/lists/*

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
