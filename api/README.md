# Workflow Automator API

FastAPI backend for the [AI Business Workflow Automator](../README.md).

## Run

From the repo root, ensure `.env` is set up (see `../.env.example`), then:

```bash
cd api
uv sync                       # creates .venv and installs deps
uv run python run.py          # starts dev server on http://localhost:8000
```

Visit:
- [http://localhost:8000/docs](http://localhost:8000/docs) -- Swagger UI
- [http://localhost:8000/health](http://localhost:8000/health) -- liveness + DB check

## Layout

```
api/
├── pyproject.toml      # deps + ruff/pytest config
├── app/
│   ├── main.py         # FastAPI app + lifespan
│   ├── settings.py     # env-driven config (pydantic-settings)
│   ├── db.py           # async psycopg pool with pgvector adapters
│   ├── logging.py      # structlog setup
│   ├── jobs.py         # in-memory event broker (added in step 8)
│   └── api/
│       └── health.py   # /health endpoint
├── alembic/            # migrations (added in step 4)
└── tests/              # pytest suite
```

## Dev commands

```bash
uv run ruff check .                # lint
uv run ruff format .               # format
uv run pytest                      # tests
```

## Migrations

Alembic with hand-written raw-SQL migrations (no SQLAlchemy ORM).
Same convention as InsightFinder.

```bash
uv run alembic upgrade head           # apply all pending migrations
uv run alembic downgrade -1           # roll back one migration
uv run alembic current                # show current revision
uv run alembic history                # list all revisions
```
