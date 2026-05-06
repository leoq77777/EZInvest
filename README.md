# EZInvest

End-to-end **AI financial research assistant**: a **ReAct-style agent** (FastAPI) calls specialized tools (market data, hybrid RAG, web scrape → vector store, calculator, FinBERT sentiment), streams progress over **SSE**, and renders a live **Markdown research report** in the **Next.js** UI. Persistent chat, merged reports, layered memory, and optional long-term memories are backed by **PostgreSQL** (+ **pgvector** for dynamic corpora).

---

## Features

| Area | What ships |
|------|------------|
| **Agent** | Multi-turn reason → act → observe loop (`graph.py`), pluggable LLMs (DeepSeek / OpenAI-compatible / Ollama / local), structured tool calls, optional clarification path |
| **RAG** | FAISS (HNSW) + BM25 + **pgvector**, RRF fusion, optional cross-encoder rerank, Redis cache, graceful fallback if dynamic DB is down |
| **Tools** | `yfinance` quotes (retries + intraday fallbacks), DDG search + async fetch + chunk + index, FinBERT sentiment, deterministic calculator |
| **API** | REST + **SSE** `/api/chat/stream`; `/api/conversations` (bootstrap, messages, reports, `commit-turn`); `/api/memories`; `/api/profile_agent`; `/api/health` |
| **Frontend** | Next.js 15, React 19, Zustand, plan/progress + tool cards, stream debug (env), **explicit “Save”** to persist a turn when conversation DB is enabled |
| **Ops** | Docker Compose (Postgres+pgvector, Redis, optional vLLM/Ollama profiles), pydantic-settings |

---

## Quick start

### 1. Prerequisites

- Python **3.11+** recommended (3.9 may work; see `backend/requirements.txt`)
- Node **18+**
- **Docker** (optional but easiest for Postgres + Redis)
- GPU optional (for local vLLM profile or heavy embedding/reranker)

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env: set LLM_PROVIDER, LLM_BASE_URL, LLM_MODEL_PATH, DATABASE_URL, REDIS_URL, etc.
```

Comments inside `.env.example` document every group (LLM, FinBERT, embeddings, persistence, CORS, frontend `NEXT_PUBLIC_*` flags).

### 3. Infrastructure

```bash
docker compose up -d postgres redis
```

On first backend start, tables are created via SQLAlchemy **`create_all`** (no separate migration step required for the default dev flow).

### 4. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### 5. Frontend

```bash
cd frontend
npm install
npm run dev
```

By default the browser uses same-origin `/api/*` (Next.js rewrites → backend); only set `NEXT_PUBLIC_API_URL` if you deliberately call the backend directly.

### 6. One-shot local restart (optional)

From repo root:

```bash
./scripts/restart-dev.sh
# ./scripts/restart-dev.sh --debug-stream --no-conversation-db   # examples
```

---

## Docs

| File | Purpose |
|------|---------|
| [**PROJECT.md**](PROJECT.md) | Deep architecture, RAG/agent design choices, diagrams |
| [**PROJECT_RESUME.zh.md**](PROJECT_RESUME.zh.md) | One-pager + **CN/EN resume bullets** for portfolios |
| [**BENCHMARK.md**](BENCHMARK.md) | Agent route benchmark (**mock = 0 LLM calls**) + how to run live safely |
| [**AGENTS.md**](AGENTS.md) | GitNexus / AI assistant workflow for this repo |

Legacy **`DEVELOPMENT.md`** (outdated LangGraph / fine-tune narrative) has been removed; use **PROJECT.md** instead.

---

## Testing

```bash
cd backend && source .venv/bin/activate && pytest tests/ -q
cd frontend && npm test -- --run
```

---

## License / disclaimer

EZInvest output may be inaccurate and is **not** financial advice. Configure API keys and CORS responsibly for production.
