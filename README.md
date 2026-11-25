# Lyftr AI — Resilient LLM Chatbot

A React + FastAPI full-stack chatbot with LiteLLM-backed caching, two-key automatic fallback, SQLite conversation history, per-request token tracking, Docker Compose, and failure simulation.

> **Submission status:** Source code only. The project is **not deployed**, and live-provider behavior has **not been verified** in this environment. Configure two real working keys, test everything, deploy both tiers, record a demo, and add the URLs before submitting.

## 1. Live URLs

- Frontend: **ADD YOUR DEPLOYED URL**
- Backend: **ADD YOUR DEPLOYED URL**
- GitHub: **ADD YOUR PUBLIC REPO URL**
- Demo video: **ADD YOUR VIDEO URL**

## 2. Run locally: with Docker and without

### Prerequisites

- Docker Desktop and Docker Compose, or Python 3.11+ and Node.js 20+
- Two working provider API keys, for the same model configured by `LLM_MODEL`

### Docker

```bash
cp .env.example .env
# Edit .env: insert real keys and select an available model
make up
# Frontend: http://localhost:3000
# Backend health: http://localhost:8000/health
# Stop: make down
```

On Windows PowerShell, use `Copy-Item .env.example .env`. If `make` is unavailable, use `docker compose up --build -d` and `docker compose down`.

### Without Docker

```bash
cd backend
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Set LLM_API_KEYS, LLM_MODEL, DATABASE_URL, ALLOWED_ORIGINS, ENABLE_FAILURE_SIMULATION
uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm install
# Set VITE_API_URL=http://localhost:8000 (or leave default)
npm run dev
```

Set `DATABASE_URL=sqlite:///./app.db` for a local SQLite file outside Docker. Environment variables are read by the backend process; `.env` is loaded automatically by Docker Compose, not by the standalone Python command.

## 3. Design decisions: key fallback, caching, SQLite session storage

- **LiteLLM**: `litellm.completion()` sends requests to the selected provider. A pool of comma-separated API keys is tried in order; transient errors (429, quota, 5xx, connection/timeout) trigger the next key. Only `key_1`, `key_2`, etc. are exposed to the client. A non-retryable provider error is returned as a sanitized 503 by the API layer.
- **Caching**: LiteLLM's built-in `Cache(type='local')` backend is used explicitly. SHA-256 of the model name plus the entire ordered LLM message list (system prompt, stored history, new user message) is the cache key. Cached records contain the exact answer, model and usage counts. Cache hits report `LLM_CACHE`, `key_id: null`, and `fallback_attempts: 0`. Local memory cache resets when the backend process restarts; this is allowed by the assignment.
- **SQLite**: a `messages` table is created automatically. Each successful exchange is stored atomically (user and assistant in one transaction), ordered by autoincrement ID, and isolated by `session_id`. Failed requests are not saved. A named Docker volume stores `/data/app.db` across container restarts.
- **Latency**: measured server-side with a monotonic clock, including cache lookup or inference.
- **Session behavior**: the frontend generates a fresh UUID-based ID on each page load; only the new user message and session ID are sent to `/chat`.
- **Failure simulation**: when `ENABLE_FAILURE_SIMULATION=true`, `X-Simulate-Failure: key_1=429` skips key_1 for that request. `*=429` simulates failure of every configured key. This hook must be enabled on the deployed backend as specified in the assignment.

**Operational limitation:** In-memory caching is per backend process. Deploy exactly one backend worker/replica if you want repeatable cache-hit behavior without a shared cache. Simulated failures are checked after cache lookup; use fresh uncached prompts when testing fallback.

## 4. Verification: how to see failover, cache hits and per-message token usage

Run backend tests:

```bash
cd backend
python -m pytest -q
```

Example commands after starting the backend (replace prompts to ensure a cache miss):

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat -H 'Content-Type: application/json' -d '{"session_id":"first","message":"What is the capital of France?"}'
curl -X POST http://localhost:8000/chat -H 'Content-Type: application/json' -d '{"session_id":"second","message":"What is the capital of France?"}'
curl http://localhost:8000/sessions/first/messages
curl -X POST http://localhost:8000/chat -H 'Content-Type: application/json' -H 'X-Simulate-Failure: key_1=429' -d '{"session_id":"failover","message":"Explain what a mutex is in one sentence."}'
curl -i -X POST http://localhost:8000/chat -H 'Content-Type: application/json' -H 'X-Simulate-Failure: *=429' -d '{"session_id":"allfailed","message":"Describe an uncommon type of cloud in one sentence."}'
```

Expected: `/health` returns 200 with `keys_configured >= 2` and `cache_enabled: true`; first chat is `LIVE_INFERENCE`; same first prompt in a fresh session is `LLM_CACHE`; simulated key_1 failure succeeds with `key_2`; simulated all-key failure returns 503 with `{"detail":"all providers unavailable"}` and no new history. The frontend shows resolution source, model, latency, input and output tokens for each assistant message.

**Important:** If the failover test prompt is already cached, the cache wins; use an uncached message for that test. For best results, use the same provider/model on both keys and test them independently.

## 5. Setup Used: your editor and AI tools

- Editor: **FILL IN YOUR ACTUAL EDITOR**
- AI tools: ChatGPT (GPT-6) was used to generate the initial project implementation; review, test, and modify the code before submission.
- Local environment: **FILL IN YOUR ACTUAL OS AND TOOL VERSIONS**

## 6. Bonus features (if any): what you added beyond the requirements and why

- Dark responsive interface with suggestion prompts, session indicator and loading states.
- Optional session system prompt control.
- Extra metadata chip for fallback attempt count.

## Deployment guide

1. Create a **public** GitHub repository and push this folder (without `.env`).
2. Deploy the backend as a Docker service on a host that supports **persistent volumes** (e.g. Railway with a volume, or another suitable host). Set `DATABASE_URL=sqlite:////data/app.db` and mount persistent storage at `/data`. Set `LLM_API_KEYS`, `LLM_MODEL`, `ENABLE_FAILURE_SIMULATION=true`, and `ALLOWED_ORIGINS` to the exact deployed frontend origin. Expose port 8000 and use `/health` as health check. Make sure the selected host plan supports persistent disks.
3. Deploy the frontend on Vercel. Set `VITE_API_URL=https://YOUR-BACKEND-URL` **before building**. Vite embeds this at build time. For Vercel, select `frontend` as the root directory, `npm run build` as the build command, and `dist` as the output directory.
4. Verify the deployed frontend can send messages to the deployed backend (check browser console for CORS errors). Run the acceptance commands against the **deployed** API as well as locally.
5. Record a 2–3 minute narrated screen recording demonstrating the live UI, all endpoints, caching, simulated key fallback, and per-request usage.
6. Fill in the four links in section 1, commit the final README, and submit the links using the assignment submission form.

## API contract

| Method | Path | Behavior |
|---|---|---|
| GET | `/health` | Database and key-pool readiness, cache status |
| POST | `/chat` | Validate request, call LiteLLM or cache, store successful exchange |
| GET | `/sessions/{session_id}/messages` | Return stored history oldest-first, 404 if unknown |

POST `/chat` request: `{"session_id":"s-123","message":"Hello","system_prompt":"Optional"}`.

Response metadata includes: `resolution_source`, `model`, `latency_ms`, `input_tokens`, `output_tokens`, `key_id`, `fallback_attempts`.

## Security notes

Never commit `.env` or print API keys in logs. Only backend code has access to keys. The simulated failure hook is required by the assignment and should be disabled for a real production service after evaluation. The sample API is intentionally unauthenticated to meet the public evaluator contract; do not use it for sensitive data or high-traffic production without adding authentication, rate limiting, and abuse protections.
