# EZInvest — Development Guide

## 1. Project Overview

EZInvest is an AI-powered investment consulting assistant designed for **low-latency, high-accuracy** financial advice. It adopts a **single-agent + specialized tools** architecture: one fine-tuned 7B LLM serves as the reasoning core, orchestrating domain-specific tools (RAG retriever, FinBERT sentiment analyzer, quantitative calculator, market data API) via a LangGraph ReAct loop.

### Design Rationale

An initial multi-agent design (separate agents for sentiment analysis, quantitative analysis, and advisory) was evaluated but rejected due to compounding latency from sequential LLM calls. The current single-agent architecture reduces LLM invocations to 1–2 per query while preserving domain specialization through dedicated tools:

| Concern | Solution | Why |
|---------|----------|-----|
| Financial reasoning | Fine-tuned 7B LLM | Domain knowledge + complex reasoning |
| Sentiment analysis | Fine-tuned FinBERT | Fast inference (~15ms), high accuracy on financial text |
| Quantitative analysis | Deterministic Python functions | Zero hallucination, exact computation |
| Knowledge retrieval | FAISS + BM25 hybrid RAG | Sub-110ms latency with Redis caching |

---

## 2. Tech Stack

### Backend

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| API Server | FastAPI | 0.115+ | Async REST + WebSocket |
| Agent Framework | LangGraph | 0.2+ | Stateful ReAct orchestration |
| LLM Inference | vLLM / llama.cpp | latest | Optimized 7B model serving |
| Vector Search | FAISS | 1.8+ | HNSW index for dense retrieval |
| Sparse Search | rank_bm25 | latest | BM25 for keyword retrieval |
| Reranker | sentence-transformers (cross-encoder) | latest | Result reranking |
| Cache | Redis | 7+ | Query cache + session store |
| Database | PostgreSQL + pgvector | 16+ | Structured data + vector fallback |
| Sentiment Model | transformers (FinBERT) | 4.40+ | Financial sentiment classification |
| Fine-tuning | PEFT (QLoRA) + bitsandbytes | latest | 4-bit quantized fine-tuning |
| Task Queue | Celery (optional) | 5+ | Async heavy tasks (indexing) |

### Frontend

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | Next.js | 15+ | SSR + App Router |
| Styling | Tailwind CSS | 4+ | Utility-first CSS |
| Charts | Recharts | 2+ | Stock/portfolio visualization |
| State | Zustand | 5+ | Lightweight state management |
| Streaming | EventSource (SSE) | native | Real-time LLM token streaming |

### Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Containerization | Docker + Docker Compose | Local dev & deployment |
| CI/CD | GitHub Actions | Lint, test, build |
| Linting | Ruff (Python), ESLint (JS) | Code quality |
| Testing | pytest (backend), Vitest (frontend) | Unit + integration tests |

---

## 3. Architecture

### 3.1 System Architecture

```
┌─────────────────────────────────────────────────────┐
│                Frontend (Next.js)                     │
│     Chat UI  ·  Portfolio Dashboard  ·  Reports       │
└───────────────────────┬─────────────────────────────┘
                        │ REST + SSE (streaming)
┌───────────────────────▼─────────────────────────────┐
│               API Gateway (FastAPI)                   │
│       /chat  ·  /health  ·  /feedback                 │
│       Auth Middleware  ·  Rate Limiter                 │
└───────────────────────┬─────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────┐
│           Agent Orchestrator (LangGraph)               │
│                                                        │
│   ┌─────────┐    ┌──────────┐    ┌─────────────┐     │
│   │  Plan    │───▶│ Execute  │───▶│  Reflect    │     │
│   │ (reason) │    │ (tools)  │    │ (evaluate)  │     │
│   └─────────┘    └──────────┘    └─────────────┘     │
│        ▲                               │              │
│        └───────────────────────────────┘              │
│                  ReAct Loop                           │
└────┬──────────┬───────────┬───────────┬─────────────┘
     │          │           │           │
┌────▼────┐ ┌──▼─────┐ ┌───▼────┐ ┌────▼──────┐
│   RAG   │ │FinBERT │ │  Quant │ │  Market   │
│Retriever│ │Sentimnt│ │  Calc  │ │  Data API │
│ ~110ms  │ │ ~15ms  │ │  ~5ms  │ │  ~200ms   │
└─────────┘ └────────┘ └────────┘ └───────────┘
     │
┌────▼────────────────────────────┐
│   FAISS (HNSW) + BM25 + Redis  │
│   PostgreSQL (structured data)  │
└─────────────────────────────────┘
```

### 3.2 Agent ReAct Flow

```
User Query
    │
    ▼
[Understand] LLM parses intent, identifies required tools
    │
    ▼
[Plan] Select tools & execution order
    │
    ▼
[Execute] Call tools in parallel where possible
    │          ├── RAG: retrieve relevant docs
    │          ├── FinBERT: analyze sentiment
    │          ├── Calculator: compute metrics
    │          └── Market API: fetch live prices
    ▼
[Synthesize] LLM generates final answer from tool outputs
    │
    ▼
[Reflect] (optional) Verify answer quality, retry if needed
    │
    ▼
Stream Response to User
```

### 3.3 RAG Pipeline Detail

```
Query ──▶ Query Rewriter (LLM) ──▶ Parallel Search
                                        ├── Dense: FAISS HNSW (embed → ANN)
                                        └── Sparse: BM25 (tokenize → score)
                                              │
                                              ▼
                                    Reciprocal Rank Fusion (RRF)
                                              │
                                              ▼
                                    Cross-Encoder Reranker
                                              │
                                              ▼
                                    Top-K Context Assembly
```

**Data Sources:**
- SEC filings (10-K, 10-Q) — chunked by section
- Earnings call transcripts — chunked by speaker turn
- Financial news articles — chunked by paragraph

**Indexing Strategy:**
- HNSW for online serving (fast, in-memory)
- IVF_PQ for large-scale offline index (memory-efficient)
- Redis caches top queries with TTL-based invalidation

### 3.4 Model Strategy

| Model | Base | Fine-tuning | Use Case |
|-------|------|-------------|----------|
| Investment Advisor LLM | Qwen2.5-7B | QLoRA 4-bit on financial QA datasets (FinQA, TAT-QA, custom) | Intent understanding, planning, answer generation |
| Sentiment Analyzer | FinBERT | Full fine-tune on Financial PhraseBank + earnings call annotations | Sentiment classification (positive/negative/neutral) |
| Embedding Model | bge-large-en-v1.5 | None (pretrained) | Document & query embedding for RAG |
| Reranker | bge-reranker-v2-m3 | None (pretrained) | Cross-encoder reranking |

---

## 4. Project Structure

```
EZInvest/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application entry
│   │   ├── config.py               # Settings & environment config
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py             # Shared dependencies (DI)
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── chat.py         # POST /chat, GET /chat/stream
│   │   │       └── health.py       # GET /health
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── graph.py            # LangGraph state machine
│   │   │   ├── state.py            # Agent state definition
│   │   │   ├── prompts.py          # System & tool prompts
│   │   │   └── tools/
│   │   │       ├── __init__.py
│   │   │       ├── retriever.py    # RAG retrieval tool
│   │   │       ├── sentiment.py    # FinBERT sentiment tool
│   │   │       ├── calculator.py   # Quantitative analysis tool
│   │   │       └── market_data.py  # Live market data tool
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   ├── embedder.py         # Embedding generation
│   │   │   ├── indexer.py          # FAISS index builder
│   │   │   ├── retriever.py        # Hybrid retrieval (dense+sparse)
│   │   │   └── reranker.py         # Cross-encoder reranking
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── llm.py              # LLM client wrapper
│   │   │   └── finbert.py          # FinBERT inference wrapper
│   │   └── schemas/
│   │       ├── __init__.py
│   │       └── chat.py             # Pydantic request/response models
│   ├── scripts/
│   │   ├── finetune_qlora.py       # QLoRA fine-tuning script
│   │   ├── finetune_finbert.py     # FinBERT fine-tuning script
│   │   ├── build_index.py          # FAISS index construction
│   │   └── ingest_data.py          # Data ingestion pipeline
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_agent.py
│   │   ├── test_rag.py
│   │   ├── test_tools.py
│   │   └── test_api.py
│   ├── eval/
│   │   ├── run_finqa.py            # FinQA benchmark evaluation
│   │   ├── run_sentiment.py        # Sentiment F1 evaluation
│   │   └── run_latency.py          # End-to-end latency benchmark
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── chat/
│   │       └── page.tsx
│   ├── components/
│   │   ├── ChatWindow.tsx
│   │   ├── MessageBubble.tsx
│   │   ├── ToolCallCard.tsx
│   │   ├── SentimentBadge.tsx
│   │   └── StockChart.tsx
│   ├── lib/
│   │   ├── api.ts
│   │   └── store.ts
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── Dockerfile
├── data/
│   ├── raw/                        # Raw downloaded data
│   ├── processed/                  # Chunked & cleaned data
│   └── scrapers/
│       ├── sec_filings.py
│       └── earnings_transcripts.py
├── docker-compose.yml
├── .gitignore
├── .env.example
├── DEVELOPMENT.md
└── README.md
```

---

## 5. API Design

### 5.1 Chat Endpoint

```
POST /api/chat
```

**Request:**
```json
{
  "message": "英伟达最近财报表现如何？现在值得买入吗？",
  "session_id": "uuid-optional",
  "stream": true
}
```

**Response (SSE stream):**
```
event: tool_call
data: {"tool": "retriever", "status": "running", "query": "NVIDIA recent earnings report"}

event: tool_call
data: {"tool": "sentiment", "status": "done", "result": {"label": "positive", "score": 0.87}}

event: tool_call
data: {"tool": "calculator", "status": "done", "result": {"pe_ratio": 65.2, "yoy_revenue": "+122%"}}

event: token
data: {"content": "根据英伟达最新的"}

event: token
data: {"content": "10-Q财报..."}

event: done
data: {"session_id": "uuid", "total_latency_ms": 1850}
```

### 5.2 Health Check

```
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "components": {
    "llm": "ok",
    "faiss": "ok",
    "redis": "ok",
    "finbert": "ok"
  }
}
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

| Module | Focus | Framework |
|--------|-------|-----------|
| `agent/tools/calculator.py` | Deterministic financial calculations (PE, ROE, Sharpe) | pytest |
| `agent/tools/sentiment.py` | FinBERT wrapper input/output contract | pytest + mock |
| `agent/tools/retriever.py` | Query formatting, result parsing | pytest + mock |
| `rag/retriever.py` | Dense + sparse search, RRF fusion logic | pytest |
| `rag/reranker.py` | Score normalization, top-K selection | pytest |
| `schemas/chat.py` | Pydantic model validation | pytest |
| Frontend components | Rendering, user interactions | Vitest + Testing Library |

### 6.2 Integration Tests

| Test | Description | Setup |
|------|-------------|-------|
| Agent end-to-end | Full ReAct loop with mocked tools | pytest + LangGraph test harness |
| RAG pipeline | Index → retrieve → rerank on sample corpus | pytest + tmpdir FAISS index |
| API streaming | SSE stream correctness and format | pytest + httpx async client |
| Tool orchestration | Parallel tool execution, timeout handling | pytest + asyncio |

### 6.3 Evaluation Benchmarks

| Benchmark | Metric | Target |
|-----------|--------|--------|
| FinQA (financial QA) | Accuracy | ≥ 65% (base ~53%) |
| Financial PhraseBank (sentiment) | F1 Score | ≥ 0.90 |
| Custom earnings QA (50 questions) | Human rating (1-5) | ≥ 4.0 avg |
| End-to-end latency (p95) | Milliseconds | ≤ 2000ms |
| RAG retrieval latency (p95) | Milliseconds | ≤ 110ms |
| RAG Precision@5 | Precision | ≥ 0.80 |

### 6.4 Test Commands

```bash
# Backend unit & integration tests
cd backend && pytest tests/ -v --cov=app --cov-report=term-missing

# Run specific test module
pytest tests/test_tools.py -v

# Evaluation benchmarks
python eval/run_finqa.py --model-path models/qlora-7b
python eval/run_sentiment.py --model-path models/finbert-finetuned
python eval/run_latency.py --runs 100

# Frontend tests
cd frontend && npm run test
```

---

## 7. Development Phases

### Phase 1: Foundation (Week 1)
- [x] Project scaffolding & dependency setup
- [ ] FastAPI server with health check & chat stub
- [ ] Docker Compose (Redis, PostgreSQL)
- [ ] CI pipeline (lint + test)

### Phase 2: Agent Core (Week 2)
- [ ] LangGraph ReAct graph definition
- [ ] Tool interface abstraction
- [ ] Calculator tool (deterministic, fully testable)
- [ ] Stub implementations for all tools

### Phase 3: RAG Pipeline (Week 3)
- [ ] Data ingestion scripts (SEC filings, earnings calls)
- [ ] FAISS HNSW index builder
- [ ] BM25 index builder
- [ ] Hybrid retrieval + RRF fusion
- [ ] Cross-encoder reranking
- [ ] Redis caching layer

### Phase 4: Model Fine-tuning (Week 4)
- [ ] QLoRA fine-tuning script for Qwen2.5-7B
- [ ] FinBERT fine-tuning on Financial PhraseBank
- [ ] Evaluation benchmarks
- [ ] Model serving setup (vLLM or llama.cpp)

### Phase 5: Frontend (Week 5)
- [ ] Chat UI with streaming support
- [ ] Tool call visualization (show agent reasoning)
- [ ] Stock chart & sentiment display components
- [ ] Responsive design

### Phase 6: Integration & Polish (Week 6)
- [ ] End-to-end integration testing
- [ ] Latency optimization & profiling
- [ ] Error handling & graceful degradation
- [ ] README & demo recording
