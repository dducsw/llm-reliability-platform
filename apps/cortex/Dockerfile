# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
WORKDIR /src
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY . .
RUN uv sync --frozen --no-dev --package reflex-cortex

FROM python:3.12-slim-bookworm
WORKDIR /app
COPY --from=build /src/.venv /app/.venv
COPY --from=build /src/VERSION /app/VERSION
ENV PATH="/app/.venv/bin:$PATH"
CMD ["ddtrace-run", "reflex-cortex", "serve"]
