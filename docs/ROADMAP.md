# AI Business Workflow Automator — Build Roadmap

12 sequenced steps from empty folder to deployed product. About half
the steps reuse patterns already proven in [InsightFinder](https://github.com/Forward0125/InsightFinder).

## Foundation
- [x] **1. Scaffold project folder** — README, .gitignore, .gitattributes, .env.example, docker-compose, init SQL, verify script, roadmap
- [x] **2. Postgres + pgvector running** — fresh Neon project verified (PG 16.12); `pgvector` 0.8.0 + `pg_trgm` 1.6 loaded; vector literal round-trips
- [x] **3. FastAPI backend skeleton** — pydantic-settings, asyncpg + pgvector adapters, structlog, `/health` returns `{"status":"ok","db":"ok"}` against Neon
- [x] **4. Database schema + migrations** — 9 tables, 2 enums, 27 indexes (incl. GIN JSONB on `research_results.payload`), applied to Neon via Alembic
- [x] **5. Next.js frontend skeleton** — Next 16 + Tailwind, design tokens copied from InsightFinder, sidebar (Lead / Workflows / Dashboard), 3 route shells, `/health` probe wired, vercel.json pinned

## Workflow engine
- [ ] **6. Lead intake + URL fetcher** — `POST /leads`; httpx + selectolax fetch with size/time caps; cached to data/raw
- [ ] **7. Research agent** — Brave Search wrapper + LLM extraction → structured `{industry, size, recent_news, key_people, tech_stack}` JSON
- [ ] **8. Qualify agent** — BANT scoring (Budget / Authority / Need / Timing) with reasoning + `qualified` boolean
- [ ] **9. Personalize agent** — outreach email + subject with `[research.*]` citation markers; tone toggle (technical / executive / casual)
- [ ] **10. Mocked actions layer** — fake CRM card, fake calendar slot, fake email send; emitted as SSE events with believable timing

## Frontend (3 surfaces)
- [ ] **11. Lead page** — URL form, live workflow DAG (React Flow), three result cards (research / qualification / email draft) streaming in
- [ ] **12. Dashboard + deploy** — leads-processed KPIs, qualified-rate chart, top industries; Render + Vercel deploy with cost guards

---

**Currently:** finished step 5.

## Notes captured during planning

- AI parts are real (research extraction, qualification, email gen). Integration parts are mocked (CRM/calendar/email send) — no SaaS sandboxes or visitor OAuth needed.
- Eval gate: regex-check the email for `[research.*]` markers, then LLM-as-judge for "is this actually personalized vs. a template?"
- Cost: ~$0.005 per lead end-to-end (research + qualify + personalize + eval). $5/day cap covers ~1000 demo runs.
- Web search: Brave Search free tier (2k/mo). Falls back to URL-scrape-only if `BRAVE_API_KEY` is blank.
