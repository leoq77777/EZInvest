"""LangChain chat model for the agent graph (lazy initialization)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_llm = None


def _build_chat_openai():
    import httpx
    from langchain_openai import ChatOpenAI
    from app.config import get_settings

    settings = get_settings()
    provider = (settings.llm_provider or "local").strip().lower()
    # Force direct outbound connections for model calls.
    # This avoids accidentally routing DeepSeek/OpenAI traffic through system proxy settings.
    transport_kwargs = {
        "http_client": httpx.Client(trust_env=False),
        "http_async_client": httpx.AsyncClient(trust_env=False),
    }

    if provider == "deepseek" and (settings.deepseek_api_key or "").strip():
        base = (settings.deepseek_base_url or "https://api.deepseek.com/v1").rstrip("/")
        logger.info(
            "LLM: DeepSeek (base_url=%s model=%s)",
            base,
            settings.deepseek_model,
        )
        return ChatOpenAI(
            base_url=base,
            api_key=settings.deepseek_api_key.strip(),
            model=settings.deepseek_model,
            temperature=0.1,
            max_tokens=2048,
            timeout=settings.llm_timeout_sec,
            **transport_kwargs,
        )

    if provider == "openai" and (settings.openai_api_key or "").strip():
        kwargs = dict(
            api_key=settings.openai_api_key.strip(),
            model=settings.openai_model,
            temperature=0.1,
            max_tokens=2048,
            timeout=settings.llm_timeout_sec,
            **transport_kwargs,
        )
        if (settings.openai_base_url or "").strip():
            kwargs["base_url"] = settings.openai_base_url.strip().rstrip("/")
        logger.info("LLM: OpenAI-compatible (model=%s)", settings.openai_model)
        return ChatOpenAI(**kwargs)

    if provider in ("deepseek", "openai"):
        logger.warning(
            "llm_provider=%s but API key is empty; using local OpenAI-compatible "
            "(LLM_BASE_URL / LLM_MODEL_PATH).",
            provider,
        )

    logger.info(
        "LLM: local OpenAI-compatible (base_url=%s model=%s)",
        settings.llm_base_url,
        settings.llm_model_path,
    )
    return ChatOpenAI(
        base_url=settings.llm_base_url.rstrip("/"),
        api_key=settings.llm_api_key,
        model=settings.llm_model_path,
        temperature=0.1,
        max_tokens=2048,
        timeout=settings.llm_timeout_sec,
        **transport_kwargs,
    )


def get_llm():
    """Chat model: honors LLM_PROVIDER (local | openai | deepseek)."""
    global _llm
    if _llm is None:
        _llm = _build_chat_openai()
    return _llm
