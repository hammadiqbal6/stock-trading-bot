FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY trading_bot ./trading_bot
COPY config ./config

RUN pip install --upgrade pip && pip install -e ".[dev]"

COPY scripts ./scripts
COPY tests ./tests
COPY docs ./docs

RUN mkdir -p data/cache data/models logs

EXPOSE 8000

CMD ["uvicorn", "trading_bot.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
