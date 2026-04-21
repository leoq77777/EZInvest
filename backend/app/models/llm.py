"""LLM client wrapper – talks to a vLLM / llama.cpp server via OpenAI-compatible API."""

import logging

from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)

_client = None


def get_llm_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
    return _client


async def generate(
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> str:
    """Generate a completion from the fine-tuned 7B model."""
    client = get_llm_client()
    settings = get_settings()

    response = await client.chat.completions.create(
        model=settings.llm_model_path,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


async def generate_stream(
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 2048,
):
    """Stream a completion token by token."""
    client = get_llm_client()
    settings = get_settings()

    stream = await client.chat.completions.create(
        model=settings.llm_model_path,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content
