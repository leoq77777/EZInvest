"""Plan-Execute-Summarize agent pipeline.

Three-phase architecture that replaces the ReAct loop:
  1. Plan   — LLM decomposes the user query into 2-5 tool-call steps (1 LLM call)
  2. Execute — Tools are called directly with no LLM involvement (0 LLM calls)
  3. Summarize — LLM synthesizes all results into a report (1 LLM call, streamed)

The LLM client is lazily initialized so tests can mock it without a running server.
"""

import json
import logging
import re
import time
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.prompts import SYSTEM_PROMPT, PLAN_PROMPT, SUMMARIZE_PROMPT
from app.agent.tools import (
    retriever_tool,
    sentiment_tool,
    calculator_tool,
    market_data_tool,
)

logger = logging.getLogger(__name__)

def _get_tool_map() -> dict:
    """Build tool map at call time so tests can patch individual tools."""
    return {
        "retriever": retriever_tool,
        "sentiment_analyzer": sentiment_tool,
        "calculator": calculator_tool,
        "market_data": market_data_tool,
    }

_llm = None


def get_llm():
    """Lazy-init the LLM client (no tool binding — used for plan & summarize).

    Connection flow:
        EZInvest backend
              │  OpenAI-compatible HTTP API
              ▼
        Local Model Server (Ollama / vLLM / llama.cpp)
    """
    global _llm
    if _llm is None:
        from langchain_openai import ChatOpenAI
        from app.config import get_settings

        settings = get_settings()
        _llm = ChatOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model_path,
            temperature=0.1,
            max_tokens=4096,
        )
        logger.info(
            "LLM client initialized: base_url=%s model=%s",
            settings.llm_base_url,
            settings.llm_model_path,
        )
    return _llm


# ---------------------------------------------------------------------------
# Phase 1 helpers
# ---------------------------------------------------------------------------

def _parse_plan(raw: str) -> list:
    """Best-effort extraction of a JSON step array from LLM output."""
    text = raw.strip()

    try:
        plan = json.loads(text)
        if isinstance(plan, list):
            return plan
    except json.JSONDecodeError:
        pass

    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        try:
            plan = json.loads(m.group(1))
            if isinstance(plan, list):
                return plan
        except json.JSONDecodeError:
            pass

    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            plan = json.loads(text[start : end + 1])
            if isinstance(plan, list):
                return plan
        except json.JSONDecodeError:
            pass

    return []


# ---------------------------------------------------------------------------
# Phase 2 helpers
# ---------------------------------------------------------------------------

async def _execute_tool(tool_name: str, tool_args: dict) -> str:
    """Dispatch a single tool call by name. Returns the string result."""
    tool_fn = _get_tool_map().get(tool_name)
    if tool_fn is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        result = await tool_fn.ainvoke(tool_args)
        return str(result)
    except Exception as e:
        logger.error("Tool %s failed: %s", tool_name, e)
        return json.dumps({"error": f"{tool_name} failed: {e}"})


# ---------------------------------------------------------------------------
# Main streaming pipeline
# ---------------------------------------------------------------------------

async def run_agent_stream(
    message: str, session_id: str
) -> AsyncGenerator[dict, None]:
    """Stream SSE events through Plan -> Execute -> Summarize."""
    llm = get_llm()

    # ── Phase 1: Plan ──────────────────────────────────────────────────
    plan_prompt = PLAN_PROMPT.format(query=message)
    plan_response = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=plan_prompt),
    ])

    steps = _parse_plan(plan_response.content)

    if not steps:
        steps = [
            {
                "id": "step_1",
                "description": message,
                "tool": "retriever",
                "tool_args": {"query": message, "top_k": 5},
            }
        ]

    for i, step in enumerate(steps):
        step.setdefault("id", f"step_{i + 1}")
        step.setdefault("status", "pending")
        step.setdefault("tool_args", {})

    yield {
        "type": "plan",
        "data": {
            "steps": [
                {
                    "id": s["id"],
                    "description": s.get("description", ""),
                    "tool": s.get("tool", ""),
                }
                for s in steps
            ]
        },
    }

    # ── Phase 2: Execute ───────────────────────────────────────────────
    step_results = []

    for step in steps:
        step_id = step["id"]
        tool_name = step.get("tool", "retriever")
        tool_args = step.get("tool_args", {})

        yield {
            "type": "step_update",
            "data": {"step_id": step_id, "status": "running"},
        }

        t0 = time.perf_counter()
        try:
            result = await _execute_tool(tool_name, tool_args)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            status = "done"
        except Exception as e:
            result = str(e)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            status = "error"

        step_results.append(
            {
                "step_id": step_id,
                "tool": tool_name,
                "description": step.get("description", ""),
                "output": result,
            }
        )

        preview = result[:200] + "..." if len(result) > 200 else result
        yield {
            "type": "step_update",
            "data": {
                "step_id": step_id,
                "status": status,
                "result": preview,
                "latency_ms": round(elapsed_ms, 1),
            },
        }

    # ── Phase 3: Summarize ─────────────────────────────────────────────
    yield {"type": "summarizing", "data": {}}

    results_text = "\n".join(
        f"### Step: {sr['description']}\nTool: {sr['tool']}\nResult:\n{sr['output']}\n"
        for sr in step_results
    )

    summarize_prompt = SUMMARIZE_PROMPT.format(
        query=message,
        step_results=results_text,
    )

    async for chunk in llm.astream([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=summarize_prompt),
    ]):
        if chunk.content:
            yield {"type": "token", "data": chunk.content}


async def run_agent(message: str, session_id: str) -> dict:
    """Non-streaming convenience wrapper — runs the full pipeline."""
    tokens = []
    tool_calls = []

    async for event in run_agent_stream(message, session_id):
        if event["type"] == "token":
            tokens.append(event["data"])
        elif event["type"] == "step_update" and event["data"].get("status") == "done":
            tool_calls.append({
                "tool": event["data"].get("tool", ""),
                "status": "done",
            })

    return {"answer": "".join(tokens), "tool_calls": tool_calls}
