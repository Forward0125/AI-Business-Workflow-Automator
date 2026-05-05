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
- [x] **6. Lead intake + URL fetcher** — `POST /leads` validates URL (rejects file://, blocks SSRF targets via DNS resolution + private/loopback/link-local check), fetches with size/time caps via httpx, parses title/description/canonical with selectolax, upserts companies + inserts leads, caches raw HTML to data/raw/<domain>/<sha>.html. Verified end-to-end against stripe.com (581 KB / 1.5s) and anthropic.com (258 KB / 1.3s)
- [x] **7. Research agent** — `POST /research/{lead_id}`: html_to_text via selectolax, optional Brave Search (no-op when key blank), gpt-4o-mini extraction with strict JSON-schema response format. Tested against stripe.com → industry: fintech, size: 1000+, Patrick Collison identified, real news. ~$0.0007 / call (3126 in / 411 out tokens)
- [x] **8. Qualify agent** — `POST /qualify/{lead_id}`: gpt-4o-mini scores Budget/Authority/Need/Timing 0-1 each + reasoning. Composite = mean; threshold 0.6. Tested: Stripe 0.88 qualified, Anthropic 0.38 not qualified — model differentiates from extracted research findings. ~$0.0002 / call
- [ ] **9. Personalize agent** — outreach email + subject with `[research.*]` citation markers; tone toggle (technical / executive / casual)
- [ ] **10. Mocked actions layer** — fake CRM card, fake calendar slot, fake email send; emitted as SSE events with believable timing

## Frontend (3 surfaces)
- [ ] **11. Lead page** — URL form, live workflow DAG (React Flow), three result cards (research / qualification / email draft) streaming in
- [ ] **12. Dashboard + deploy** — leads-processed KPIs, qualified-rate chart, top industries; Render + Vercel deploy with cost guards

---

**Currently:** finished step 8.

## Notes captured during planning

- AI parts are real (research extraction, qualification, email gen). Integration parts are mocked (CRM/calendar/email send) — no SaaS sandboxes or visitor OAuth needed.
- Eval gate: regex-check the email for `[research.*]` markers, then LLM-as-judge for "is this actually personalized vs. a template?"
- Cost: ~$0.005 per lead end-to-end (research + qualify + personalize + eval). $5/day cap covers ~1000 demo runs.
- Web search: Brave Search free tier (2k/mo). Falls back to URL-scrape-only if `BRAVE_API_KEY` is blank.
