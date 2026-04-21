"""Health check endpoint with per-component probing."""

import time
import logging

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


async def _check_redis() -> dict:
    try:
        import redis.asyncio as aioredis

        settings = get_settings()
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        start = time.perf_counter()
        await r.ping()
        latency = (time.perf_counter() - start) * 1000
        await r.aclose()
        return {"status": "ok", "latency_ms": round(latency, 1)}
    except Exception as e:
        return {"status": "down", "error": str(e)}


async def _check_llm() -> dict:
    """Probe the LLM server (vLLM/Ollama) with a /models list request."""
    try:
        import httpx

        settings = get_settings()
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.llm_base_url}/models")
            latency = (time.perf_counter() - start) * 1000
            if resp.status_code == 200:
                return {"status": "ok", "latency_ms": round(latency, 1)}
            return {"status": "degraded", "http_status": resp.status_code}
    except Exception as e:
        return {"status": "down", "error": str(e)}


async def _check_market_data() -> dict:
    from app.agent.tools.market_data import check_market_data_health

    return await check_market_data_health()


@router.get("/health")
async def health_check():
    """Deep health check: probes Redis, LLM server, and market data API."""
    components = {}
    components["api"] = {"status": "ok"}

    components["redis"] = await _check_redis()
    components["llm_server"] = await _check_llm()
    components["market_data"] = await _check_market_data()

    all_ok = all(c.get("status") == "ok" for c in components.values())
    any_down = any(c.get("status") == "down" for c in components.values())

    if all_ok:
        overall = "healthy"
    elif any_down:
        overall = "unhealthy"
    else:
        overall = "degraded"

    return {"status": overall, "components": components}


@router.get("/health/live")
async def liveness():
    """Lightweight liveness probe (no external calls)."""
    return {"status": "alive"}
