# ─────────────────────────────────────────────────────────────────
# AI Business Workflow Automator API
#
# Single-stage build using uv. No heavy ML deps in this project --
# OpenAI is called over the network, no local sentence-transformers
# or torch -- so the image stays under ~250 MB and fits Render free
# tier comfortably.
# ─────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# uv binary, copied from the published image. Pin a known-good
# version so deploys are reproducible.
COPY --from=ghcr.io/astral-sh/uv:0.4.18 /uv /uvx /bin/

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Install dependencies (no dev tools, project not installed as a pkg).
# `--no-install-project` skips installing this repo as a package --
# uvicorn finds `app.main:app` via WORKDIR + sys.path, and an
# editable install would trip on Hatchling's README check since
# .dockerignore omits the README from the build context.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# App source.
COPY app     ./app
COPY alembic ./alembic
COPY alembic.ini ./

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000

# Render injects $PORT. alembic runs every boot -- migrations are idempotent.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
