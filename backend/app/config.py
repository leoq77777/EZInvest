from __future__ import annotations

from typing import List

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_env: str = "development"
    app_port: int = 8080
    log_level: str = "INFO"
    cors_origins: List[str] = ["http://localhost:3000"]

    # LLM Provider Selection
    llm_provider: str = "local"  # options: local, openai, deepseek

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

    # FinBERT
    finbert_model_path: str = "ProsusAI/finbert"

    # Embedding & Reranker
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://ezinvest:ezinvest@localhost:5432/ezinvest"

    # FAISS
    faiss_index_path: str = "data/indexes/faiss_hnsw.index"
    bm25_index_path: str = "data/indexes/bm25.pkl"

    # Market Data
    market_data_api_key: str = ""
    market_data_provider: str = "yfinance"

    model_config = {"env_file": ("../.env", ".env"), "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
