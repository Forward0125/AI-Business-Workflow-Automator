# AI Business Workflow Automator

A sales-automation pipeline that turns a company URL into a qualified lead and a personalized outreach email — visualized as a live workflow DAG. Second flagship case study for the [TwilightCore](https://twilightcore.dev) portfolio (the first is [InsightFinder](https://github.com/Forward0125/InsightFinder)).

## What it does

Paste a company URL and watch the pipeline run end-to-end:

1. **Research** — fetch the homepage, search the web for context, LLM extracts a structured company profile (industry, size, recent news, key people, tech stack).
2. **Qualify** — score the lead BANT-style (Budget / Authority / Need / Timing) with reasoning, surface a `qualified` boolean and a fit summary.
3. **Personalize** — draft a 4-paragraph outreach email + subject line, with citations back to specific research findings.
4. **Mocked actions** — fake CRM update, fake demo-slot booking, fake email send. Clearly labelled "demo mode" — no SaaS sandboxes or visitor OAuth required.

Every stage emits SSE events so the frontend animates the DAG live.

## Honest demo design

The AI parts are real. The integration parts are mocked.

| Stage | Real | Mocked |
|---|---|---|
| Web fetch + scrape (httpx + selectolax) | ✓ | |
| Web search (Brave Search free tier) | ✓ | |
| LLM research extraction | ✓ | |
| BANT qualification | ✓ | |
| Outreach email generation | ✓ | |
| CRM update | | ✓ believable fake-card UI |
| Calendar booking | | ✓ fake Calendly slot |
| Email send | | ✓ visible draft, no SMTP call |

This way visitors see a complete-looking pipeline with no signups, no API keys to provide, and no risk of misrepresenting what shipped.

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 16 (App Router), Tailwind, framer-motion, React Flow, Tremor, Recharts |
| Backend | FastAPI (Python 3.12+), asyncpg, structlog |
| Database | Postgres 16 + `pgvector` + Postgres FTS |
| Web search | Brave Search API (free tier, 2k req/mo) |
| Generator / Qualifier | OpenAI `gpt-4o-mini` |
| Eval | LLM-as-judge (citation grounding + personalization check) |
| Deploy | Vercel (web) + Render (api) + Neon (db) |

## Getting started

### Prerequisites

- Docker Desktop *(optional — Neon also works)*
- Python 3.12+ with [`uv`](https://docs.astral.sh/uv/)
- Node.js 20+
- API keys: OpenAI, Brave Search

### Setup

```bash
# 1. Copy env template, fill in keys
cp .env.example .env

# 2. Postgres (use docker compose up -d, OR a Neon connection string)
docker compose up -d

# 3. Backend
cd api
uv sync                       # creates .venv and installs deps
uv run alembic upgrade head
uv run python run.py          # starts dev server on http://localhost:8000

# 4. Frontend (in a second terminal)
cd web
npm install
npm run dev
```

Visit `http://localhost:3000`, paste any company URL, click Run.

## Project structure

```
ai-business-workflow-automator/
├── api/                      # FastAPI backend (scaffolded in step 3)
├── web/                      # Next.js frontend (scaffolded in step 5)
├── data/
│   ├── raw/                  # web-fetch caches (gitignored)
│   └── processed/
├── infra/postgres/init/      # extension bootstrap
├── scripts/                  # utilities
├── docs/                     # ROADMAP, DEPLOY, design notes
├── docker-compose.yml        # local Postgres + pgvector
└── .env.example              # env template
```

## Status

**Step 1 of 12** — project scaffold complete. See [`docs/ROADMAP.md`](./docs/ROADMAP.md) for what's next.
