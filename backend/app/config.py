from __future__ import annotations

from typing import List

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_env: str = "development"
    app_port: int = 8080
    log_level: str = "INFO"
    # When true, all /api/chat/stream requests emit `debug` SSE unless client sends debug_stream=false only... (we OR with request)
    debug_stream: bool = False
    # While waiting on slow RAG / agent steps, emit SSE comment lines so proxies (Next/nginx) do not close the TCP idle connection.
    sse_keepalive_interval_sec: float = 5.0
    # Warm expensive local models/indexes during startup so the first user request
    # does not pay the embedding / FinBERT cold-start cost.
    enable_startup_warmup: bool = True
    enable_startup_finbert_warmup: bool = True
    # Bound research-mode ReAct loops. Chat mode does one LLM call and bypasses this.
    agent_max_iterations: int = 3
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

    # LLM Provider Selection
    llm_provider: str = "local"  # options: local, openai, deepseek
    # httpx read timeout per LLM call (LangChain ChatOpenAI); does not cancel browser stream by itself
    llm_timeout_sec: float = 180.0

    # LLM - Local (Ollama/vLLM)
    llm_model_path: str = "qwen3.5:9b"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "not-needed"

    # LLM - DeepSeek
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # LLM - OpenAI (Optional)
    openai_api_key: str = ""
    openai_model: str = "gpt-4-turbo"
    openai_base_url: str = ""  # empty = OpenAI default; set for Azure-compatible endpoints

    # FinBERT
    finbert_model_path: str = "ProsusAI/finbert"

    # Local sentence-transformers (NOT the chat LLM). Caches under HF_HOME / ~/.cache/huggingface.
    # Bundled FAISS index is built with bge-large (1024-d); keep this model unless you rebuild indexes.
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    # Cross-encoder reranker is a second heavy model; off by default for faster local dev.
    enable_rag_reranker: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600

    # PostgreSQL (chat history + long-term memory)
    database_url: str = "postgresql+asyncpg://ezinvest:ezinvest@localhost:5432/ezinvest"
    enable_persistence: bool = True

    # Three-layer memory: session excerpt, agent style, RAG core
    rag_core_top_k: int = 8
    session_context_messages: int = 16  # last N chat rows for current conversation
    agent_style_markdown: str = ""  # default Layer-2 when DB has no per-profile row

    # Summarize other sessions → long text + pgvector (Layer-3 corpus)
    # Off by default so dev/tests do not spawn summarization unless configured.
    enable_session_summary_job: bool = False
    session_summary_interval_sec: int = 900  # 15 minutes
    min_messages_to_summarize_session: int = 6
    session_summary_startup_delay_sec: int = 45

    # FAISS
    faiss_index_path: str = "data/indexes/faiss_hnsw.index"
    bm25_index_path: str = "data/indexes/bm25.pkl"

    # Market Data
    market_data_api_key: str = ""
    market_data_provider: str = "yfinance"
    market_data_timeout_sec: float = 4.0
    market_data_max_retries: int = 0

    model_config = {"env_file": ("../.env", ".env"), "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
