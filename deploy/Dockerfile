# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=0

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl dnsutils \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install .
RUN python -m playwright install --with-deps chromium

COPY app.py main.py ./
COPY static ./static
COPY templates ./templates

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
