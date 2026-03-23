FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY agents /app/agents
COPY tests /app/tests

RUN pip install --upgrade pip && \
    pip install '.[dev]'

WORKDIR /app/agents

EXPOSE 8000

CMD ["adk", "api_server"]