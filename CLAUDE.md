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

## Next up — switch the query parser LLM to Groq
Goal: a free, open-weight model for a deployed demo (no GPU server needed).
Work on a new branch `feature/groq-llm` off `main`.

1. Add `langchain-groq` to `backend/requirements.txt` (match the pinned
   `langchain-core==0.3.x` line).
2. `.env` / `.env.example`: `LLM_MODEL=groq:llama-3.1-8b-instant`, `GROQ_API_KEY=`;
   remove `LLM_PROVIDER=ollama`. Keep Ollama documented as the self-hosted option.
3. `docker-compose.yml`: pass `GROQ_API_KEY` through to the backend.
4. `query_parser.py` already supports `groq` via `init_chat_model` — verify nothing
   else needs changing; the regex fallback must still work with no key.
5. `frontend/src/components/leads/ResultsPanel.tsx` error hint mentions
   `OPENAI_API_KEY` — make it provider-neutral.
6. Rebuild, rerun the smoke test, and check backend logs show
   `provider='groq'`.

The user still needs to create a Groq API key at https://console.groq.com.
