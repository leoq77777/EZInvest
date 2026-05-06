#!/usr/bin/env python3
"""Lightweight agent-route benchmark with optional **zero LLM API usage**.

Modes
-----
* mock (default): ASGI in-process + patches `assemble_memory_layers`,
  `load_dialogue_and_report`, and `run_agent`. Measures FastAPI handler +
  serialization overhead only. **External LLM calls: 0.**
* live: HTTP POST to a running server `/api/chat` (stream=false). **Each
  request triggers the full agent** (many internal LLM round-trips possible).
  Use ``--max-queries 1`` and a long ``--timeout`` to minimise spend.

Examples::

    cd backend && . .venv/bin/activate
    python eval/run_agent_benchmark.py --mode mock --runs 100

    # Live (costs real LLM); strip proxies if httpx complains about socksio
    python eval/run_agent_benchmark.py --mode live --url http://127.0.0.1:8080 \\
        --max-queries 1 --timeout 600
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import statistics
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import httpx
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.memory_layers import MemoryLayers


def _strip_proxy_env() -> None:
    for k in list(os.environ):
        if "PROXY" in k.upper():
            os.environ.pop(k, None)


def _stats_ms(samples: List[float]) -> Dict[str, float]:
    if not samples:
        return {}
    s = sorted(samples)
    n = len(s)
    p95_idx = min(n - 1, int(n * 0.95))
    return {
        "n": float(n),
        "mean_ms": round(statistics.mean(s), 3),
        "p50_ms": round(statistics.median(s), 3),
        "p95_ms": round(s[p95_idx], 3),
        "min_ms": round(s[0], 3),
        "max_ms": round(s[-1], 3),
    }


async def _run_mock(runs: int) -> Dict[str, Any]:
    empty_layers = MemoryLayers(
        rag_core_block="",
        session_context_block="",
        agent_style_block="",
        user_memory_block="",
    )
    fake_agent = {
        "answer": "benchmark stub answer",
        "tool_calls": [],
        "report_markdown": "# Stub\n\nok",
    }
    latencies: List[float] = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(runs):
            t0 = time.perf_counter()
            with (
                patch(
                    "app.api.routes.chat.assemble_memory_layers",
                    new_callable=AsyncMock,
                    return_value=empty_layers,
                ),
                patch(
                    "app.api.routes.chat.load_dialogue_and_report",
                    new_callable=AsyncMock,
                    return_value=("", None),
                ),
                patch(
                    "app.api.routes.chat.run_agent",
                    new_callable=AsyncMock,
                    return_value=fake_agent,
                ),
            ):
                r = await client.post(
                    "/api/chat",
                    json={"message": "benchmark ping", "stream": False},
                )
            latencies.append((time.perf_counter() - t0) * 1000)
            r.raise_for_status()
            body = r.json()
            assert body.get("answer")

    return {
        "mode": "mock",
        "runs": runs,
        "external_llm_http_calls": 0,
        "note": (
            "Patches agent + memory gather; measures routing/serialization only. "
            "Does not reflect real retrieval or LLM latency."
        ),
        "latency_ms": _stats_ms(latencies),
    }


async def _run_live(
    url: str,
    queries: List[str],
    timeout_sec: float,
) -> Dict[str, Any]:
    _strip_proxy_env()
    latencies: List[float] = []
    successes = 0
    errors: List[Dict[str, Any]] = []
    base = url.rstrip("/")
    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        for q in queries:
            t0 = time.perf_counter()
            try:
                r = await client.post(
                    f"{base}/api/chat",
                    json={"message": q, "stream": False},
                )
                dt = (time.perf_counter() - t0) * 1000
                latencies.append(dt)
                ok = r.status_code == 200 and bool((r.json().get("answer") or "").strip())
                if ok:
                    successes += 1
                else:
                    errors.append(
                        {
                            "query_preview": q[:60],
                            "status": r.status_code,
                            "answer_empty": r.status_code == 200,
                        }
                    )
            except Exception as e:
                dt = (time.perf_counter() - t0) * 1000
                latencies.append(dt)
                errors.append({"query_preview": q[:60], "error": repr(e)})

    n = len(queries)
    return {
        "mode": "live",
        "url": base,
        "queries": queries,
        "timeout_sec": timeout_sec,
        "external_llm_http_calls_note": (
            f"HTTP /api/chat requests: {n}. Each request may invoke multiple "
            "internal LLM completions (ReAct loop); not counted here."
        ),
        "success_count": successes,
        "success_rate_pct": round(100.0 * successes / n, 2) if n else 0.0,
        "latency_ms": _stats_ms(latencies),
        "errors": errors,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="EZInvest agent benchmark")
    p.add_argument("--mode", choices=("mock", "live"), default="mock")
    p.add_argument(
        "--quiet", action="store_true", help="Suppress httpx INFO logs (mock/live)"
    )
    p.add_argument("--runs", type=int, default=80, help="Iterations (mock mode)")
    p.add_argument("--url", default="http://127.0.0.1:8080", help="Backend base (live)")
    p.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Per-request timeout seconds (live)",
    )
    p.add_argument(
        "--max-queries",
        type=int,
        default=1,
        help="Number of live queries (keep small to save LLM quota)",
    )
    args = p.parse_args()
    if args.quiet:
        logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.mode == "mock":
        out = asyncio.run(_run_mock(max(1, args.runs)))
    else:
        queries = [
            "Calculate the P/E ratio for MSFT at $420 with EPS of $12.5",
            "What is current AAPL stock price?",
            "Summarize NVIDIA latest earnings in 3 bullets",
        ][: max(1, args.max_queries)]
        out = asyncio.run(_run_live(args.url, queries, args.timeout))

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
