# Deploy AI Business Workflow Automator

Two services, deployed in this order:

1. **API → Render** (Docker) — gets a URL like `https://workflow-automator-api.onrender.com`
2. **Web → Vercel** (Next.js) — gets a URL like `https://ai-business-workflow-automator-xxx.vercel.app`

The frontend's env points at the API URL; the API's CORS list points back. The chicken-and-egg is broken with one redeploy.

You've already done this dance once for [InsightFinder](https://github.com/Forward0125/InsightFinder). This is the same play.

---

## 1. Render — API

### A. Create the service via Blueprint

1. [render.com](https://render.com) → **+ New** → **Blueprint**  ← *not* "Web Service"
2. Pick the **`AI-Business-Workflow-Automator`** repo
3. Render reads [`render.yaml`](../render.yaml) and pre-fills:
   - **Name:** `workflow-automator-api`
   - **Region:** Oregon
   - **Root directory:** `api`
   - **Runtime:** Docker
   - **Plan:** Free
   - **Health check path:** `/health`

### B. Fill in 3 secret env vars

The values from `render.yaml` marked `sync: false`:

| Key | Value |
|---|---|
| `DATABASE_URL` | Your Neon `workflow_automator` connection string |
| `OPENAI_API_KEY` | Your `sk-proj-...` key |
| `API_CORS_ORIGINS` | `*` for now — we tighten this in step 4 |

Click **Apply**.

### C. Wait for first deploy (~5 min)

Watch the **Logs** tab. You should see:

```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial
INFO  [alembic.runtime.migration] Running upgrade 0001_initial -> 0002_lead_nullable
INFO     Started server process [1]
INFO     Application startup complete.
INFO     Uvicorn running on http://0.0.0.0:10000
```

(Render injects `PORT=10000` for free-tier services.)

### D. Verify

```
curl https://workflow-automator-api.onrender.com/health
# expect: {"status":"ok","db":"ok"}
```

If `db: "unreachable"` — `DATABASE_URL` is wrong; fix in **Environment** and Render auto-redeploys.

---

## 2. Vercel — Web

### A. Create the project

1. [vercel.com/new](https://vercel.com/new) → import the **`AI-Business-Workflow-Automator`** repo
2. **Configure:**
   - **Framework Preset:** Next.js (auto-detected)
   - **Root Directory:** `web`  ← **set this manually**
   - Build / Output: leave defaults (pinned by `web/vercel.json`)

### B. Set env vars

| Key | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://workflow-automator-api.onrender.com` (no trailing slash) |

Click **Deploy**.

### C. Wait (~2 min) — Vercel gives you a URL like
`https://ai-business-workflow-automator-forward0125.vercel.app`

---

## 3. Tighten Render's CORS

Render → service → **Environment**:

- Edit `API_CORS_ORIGINS`
  - Old: `*`
  - New: `https://ai-business-workflow-automator-xxxx.vercel.app` (your actual Vercel URL)

Render auto-redeploys.

---

## 4. Smoke-test the live site

Open your Vercel URL:

- **`/`** — Lead page. Click the `stripe.com` chip → Run → DAG animates → 4 result cards populate live.
- **`/workflows`** — placeholder for now (no separate workflow list view in v1).
- **`/dashboard`** — KPIs + 7-day chart + alerts feed populated from the same DB.

First request to the API after idleness will be slow (~30s) — Render's free tier sleeps after 15min. Subsequent requests are normal speed.

---

## Updating

```bash
git push
```

Render: ~3 min for Docker rebuild. Vercel: ~1 min for Next.js build.

---

## Production differences from local

| | Local | Production |
|---|---|---|
| Daily $ cap | $5 | $5 |
| Per-IP rate limit (`/workflows/runs`) | 5/hr | 5/hr |
| Cold start | none | ~30 s after 15min idle |
| Brave Search | optional | optional (set `BRAVE_API_KEY` in dashboard if desired) |
