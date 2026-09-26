# AgentReach

Lead-generation tool locked to one niche: it finds **real estate agents & brokerages**
from a natural-language query ("luxury agents in Austin, TX"), enriches, verifies and
scores them, and exports CSV.

## Stack
- **Backend** — FastAPI + LangGraph pipeline (`backend/app/agents/graph.py`).
  Nodes in `backend/app/nodes/`: `query_parser` → `maps_scraper` → `enricher` →
  `email_verifier` → `lead_scorer`.
- **Frontend** — Next.js 14 + zustand (`frontend/src`).
- **DB** — MongoDB (`backend/app/db.py`): `users` and `searches` (each search stores
  its pipeline events and scored leads, scoped per user). Job state lives in Mongo,
  not process memory.
- **Auth** — JWT + bcrypt (`backend/app/auth.py`, routes in `backend/app/api/auth_routes.py`).

## Running
- `make up` / `make down` / `make logs-back` / `make shell-db` — everything runs in Docker.
- Backend :8000 (docs at `/docs`), frontend :3000, local mongo on 127.0.0.1:27017.
- Local DB = `COMPOSE_PROFILES=local-db`. Atlas = set `MONGO_URI` and drop that profile.
- The backend only sees env vars listed explicitly in `docker-compose.yml`
  (there is no `env_file`) — a new key must be added to `.env`, `.env.example`
  **and** the compose `environment:` block.

## Env
`.env` holds only keys the code uses (see `.env.example` for docs). The DB name is
`agentreach`. `.env` was once polluted with another project's keys ("self_atlas",
Pinecone, LangSmith) — don't reintroduce them.

## Testing
No unit tests yet. `python3 backend/tests/smoke_test.py` runs an end-to-end test against the running stack
(auth, per-user isolation, a real search with `max_results: 2`, saved search
get/delete, CSV download) — 21/21 passing at merge `8fce7b2`. Keep real searches
small: they spend RapidAPI/SearchApi quota.

## LLM (query parser)
The only LLM call is `backend/app/nodes/query_parser.py` (query → location/radius/filters
JSON). Default: Groq free tier, `LLM_MODEL=groq:openai/gpt-oss-20b` + `GROQ_API_KEY`.
(`llama-3.1-8b-instant` was avoided — Groq lists it as enterprise-only.) `langchain-groq`
is pinned to 0.2.1, the last version compatible with `langchain-core==0.3.16`.
With no/invalid key the parser falls back to a regex parser, so searches still work.

## Maps scraping
`maps_scraper.py`: RapidAPI Local Business Data is primary (emails come back under
`emails_and_contacts.emails`); per search term it falls back to SearchApi.io on any error.
A 429 that survives the backoff retry pauses RapidAPI (until `X-RateLimit-Requests-Reset`,
10 min default, 6 h max) so later terms/searches go straight to SearchApi.

## Deployment (free tier)
- Backend → Render (Docker, `render.yaml` blueprint, free plan, Frankfurt).
  Dockerfile honors `$PORT` and `WEB_CONCURRENCY` (default 1 worker).
- Frontend → Vercel, root dir `frontend`, env `NEXT_PUBLIC_API_URL` = Render URL
  (baked in at build time — redeploy after changing it).
- DB → MongoDB Atlas M0 (`MONGO_URI`, network access 0.0.0.0/0 since Render IPs are dynamic).
- Guardrails for the public demo: `MAX_RESULTS_CAP` (request is clamped, not rejected;
  enforced after enrichment in `enricher.py`), `DAILY_SEARCH_LIMIT` per user per 24h (429),
  `CORS_ORIGINS` = Vercel URL.
- Render free sleeps after ~15 min idle; an UptimeRobot ping on `/api/health` keeps it warm.
