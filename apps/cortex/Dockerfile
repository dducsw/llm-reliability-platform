# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
# Build tại /app (trùng runtime): shebang trong .venv/bin là đường dẫn tuyệt đối
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY . .
# Cache uv dùng chung giữa các image (không tải lại package mỗi lần build)
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable --package reflex-cortex

FROM python:3.12-slim-bookworm
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/VERSION /app/VERSION
# Seed catalog + scenario YAML đọc theo đường dẫn tương đối (fallback khi Mongo chưa có)
COPY --from=build /app/seeds /app/seeds
COPY --from=build /app/scenarios /app/scenarios
ENV PATH="/app/.venv/bin:$PATH"
CMD ["ddtrace-run", "reflex-cortex", "serve"]
