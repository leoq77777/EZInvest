# EZInvest

AI-powered investment consulting assistant that delivers fast, accurate financial advice through a single-agent architecture with specialized tools.

## Architecture

**Single Agent + Specialized Tools** — one fine-tuned 7B LLM orchestrates domain-specific tools via a LangGraph ReAct loop:

- **RAG Retriever** — Hybrid FAISS (HNSW) + BM25 search with Redis caching, sub-110ms latency
- **FinBERT Sentiment** — Fine-tuned financial sentiment classifier (~15ms inference)
- **Quantitative Calculator** — Deterministic financial metrics (P/E, ROE, Sharpe, etc.)
- **Market Data API** — Real-time stock prices via yfinance

## Quick Start

```bash
# 1. Start infrastructure
docker compose up -d redis postgres

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# 3. Frontend
cd frontend
npm install
npm run dev
```

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry
│   │   ├── agent/            # LangGraph ReAct agent
│   │   │   ├── graph.py      # State machine
│   │   │   └── tools/        # 4 specialized tools
│   │   ├── rag/              # Hybrid retrieval pipeline
│   │   ├── models/           # FinBERT & LLM wrappers
│   │   └── schemas/          # Pydantic models
│   ├── scripts/              # Fine-tuning scripts
│   ├── tests/                # pytest suite
│   └── eval/                 # Benchmarks
├── frontend/                 # Next.js chat UI
│   ├── src/
│   │   ├── components/       # Chat, ToolCall, Sentiment UI
│   │   └── lib/              # API client, Zustand store
└── docker-compose.yml
```

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed architecture, tech stack, API design, and testing strategy.

## Testing

```bash
cd backend
pytest tests/ -v --cov=app
```
