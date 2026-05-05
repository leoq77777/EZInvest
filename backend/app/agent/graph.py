import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.llm import get_llm
from app.agent.entity_resolution import (
    entity_grounding_observation,
    normalize_tool_call,
    resolve_entities,
)
from app.agent.prompts import (
    CHAT_DELTA_PROMPT,
    EXPAND_SEED_PROMPT,
    REPORT_MERGE_PROMPT,
    REASONER_PROMPT,
    SYSTEM_PROMPT,
)
from app.agent.tools.calculator import calculator_tool
from app.agent.tools.market_data import market_data_tool
from app.agent.tools.retriever import retriever_tool
from app.agent.tools.sentiment import sentiment_tool
from app.agent.tools.web_scraper import web_scraper_tool

logger = logging.getLogger(__name__)

# Cap tool payloads stored in observations / sent to the reasoner to avoid huge JSON
# breaking provider limits or stalling the event loop on tokenize.
_OBS_TEXT_CAP = 24_000


def _cap_obs_text(val: Any, max_len: int = _OBS_TEXT_CAP) -> str:
    s = str(val or "")
    if len(s) <= max_len:
        return s
    return s[: max_len - 40] + "\n...[truncated by backend]"


def _dbg_evt(t0: float, enabled: bool, phase: str, detail: str = "") -> Optional[dict]:
    """Structured SSE debug payload (only when debug_stream is on)."""
    if not enabled:
        return None
    return {
        "type": "debug",
        "data": {
            "phase": phase,
            "detail": detail,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
        },
    }


def _compose_system_prompt(
    memory_context: str,
    *,
    rag_core_context: str = "",
    session_context_block: str = "",
    agent_style_context: str = "",
) -> str:
    """Order: base rules → Layer3 RAG → Layer1 session → Layer2 style → user bullets."""
    parts: list[str] = [SYSTEM_PROMPT]
    if rag_core_context.strip():
        parts.append(
            "## 核心决策知识库（Layer 3 · RAG）\n"
            "以下片段来自向量检索：历史会话摘要、入库财经文档、网页抓取沉淀等。"
            "在**投资结论与一般事实陈述**上应**优先采信并引用**本段；"
            "若涉及**实时报价、精确财报数值**，必须以当轮工具（market_data、web_scraper 等）为准；"
            "两者冲突时的裁决：**行情与精确数字 → 工具；其余叙事与背景 → 本 RAG 段**。\n\n"
            + rag_core_context.strip()
        )
    if session_context_block.strip():
        parts.append(
            "## 当前会话上下文（Layer 1）\n" + session_context_block.strip()
        )
    if agent_style_context.strip():
        parts.append(
            "## 投资顾问风格与经验沉淀（Layer 2）\n" + agent_style_context.strip()
        )
    if memory_context.strip():
        parts.append(
            "## 用户显式长期记忆（偏好与经用户确认的补充事实）\n"
            "若与工具实时数值冲突以工具为准；与 RAG 背景冲突时按 Layer 3 说明裁定。\n\n"
            + memory_context.strip()
        )
    return "\n\n".join(parts)


TOOLS = {
    "market_data": market_data_tool,
    "web_scraper": web_scraper_tool,
    "retriever": retriever_tool,
    "calculator": calculator_tool,
    "sentiment_analyzer": sentiment_tool,
}


async def _execute_grounded_tool(
    user_message: str,
    name: str,
    args: Dict[str, Any],
) -> tuple[str, Dict[str, Any], str, Optional[str]]:
    """Normalize entity-sensitive tool calls before executing them."""
    tool_name, tool_args, note = normalize_tool_call(user_message, name, args)
    out = await execute_tool(tool_name, tool_args)
    return tool_name, tool_args, out, note


def _strip_json_fences(raw: str) -> str:
    return raw.replace("```json", "").replace("```", "").strip()


async def execute_tool(name: str, args: Dict[str, Any]) -> str:
    """Execute a LangChain tool by name with a single args dict."""
    if name not in TOOLS:
        return f"Error: Tool '{name}' not found."

    tool = TOOLS[name]
    try:
        out = await tool.ainvoke(args)
        return str(out)
    except Exception as e:
        logger.error("Error executing tool %s: %s", name, e)
        return f"Error executing tool: {str(e)}"


async def _finalize_chat_and_report(
    llm,
    system_text: str,
    dialogue_context: str,
    message: str,
    previous_report: str,
    obs_summary: str,
    *,
    debug_stream: bool = False,
    t0: float = 0.0,
) -> AsyncGenerator[dict, None]:
    """Short chat bubble + full merged markdown report."""
    ev = _dbg_evt(t0, debug_stream, "finalize.enter", "chat delta + report merge")
    if ev:
        yield ev
    yield {"type": "summarizing", "data": {}}

    chat_prompt = CHAT_DELTA_PROMPT.format(
        dialogue=dialogue_context.strip() or "（尚无历史对话。）",
        latest=message.strip(),
        step_results=obs_summary,
    )
    ev = _dbg_evt(t0, debug_stream, "finalize.chat_llm", "before ainvoke (CHAT_DELTA)")
    if ev:
        yield ev
    chat_resp = await llm.ainvoke(
        [SystemMessage(content=system_text), HumanMessage(content=chat_prompt)]
    )
    ev = _dbg_evt(t0, debug_stream, "finalize.chat_llm.done", "chat delta returned")
    if ev:
        yield ev
    chat_text = (getattr(chat_resp, "content", None) or "").strip()
    if chat_text:
        yield {"type": "token", "data": {"content": chat_text}}

    prev = (
        previous_report.strip()
        if previous_report.strip()
        else "（尚无投研成稿，请在本轮根据工具结果撰写首版。）"
    )
    report_prompt = REPORT_MERGE_PROMPT.format(
        dialogue=dialogue_context.strip() or "（尚无历史对话。）",
        latest=message.strip(),
        previous_report=prev,
        step_results=obs_summary,
    )
    ev = _dbg_evt(t0, debug_stream, "finalize.report_llm", "before ainvoke (REPORT_MERGE)")
    if ev:
        yield ev
    report_resp = await llm.ainvoke(
        [SystemMessage(content=system_text), HumanMessage(content=report_prompt)]
    )
    ev = _dbg_evt(t0, debug_stream, "finalize.report_llm.done", "report markdown returned")
    if ev:
        yield ev
    report_md = (getattr(report_resp, "content", None) or "").strip()
    yield {"type": "report", "data": {"markdown": report_md}}


async def run_agent_stream(
    message: str,
    session_id: str,
    memory_context: str = "",
    *,
    rag_core_context: str = "",
    session_context_block: str = "",
    agent_style_context: str = "",
    dialogue_context: str = "",
    previous_report: str = "",
    debug_stream: bool = False,
) -> AsyncGenerator[dict, None]:
    """Multi-turn ReAct + optional parallel tools; chat delta vs. merged report."""
    t0 = time.perf_counter()
    ev = _dbg_evt(t0, debug_stream, "graph.enter", "run_agent_stream start")
    if ev:
        yield ev
    llm = get_llm()
    ev = _dbg_evt(t0, debug_stream, "graph.llm.ready", "get_llm() returned client")
    if ev:
        yield ev
    observations: list[dict[str, Any]] = []
    max_iterations = 8

    system_text = _compose_system_prompt(
        memory_context,
        rag_core_context=rag_core_context,
        session_context_block=session_context_block,
        agent_style_context=agent_style_context,
    )
    ev = _dbg_evt(t0, debug_stream, "graph.system.ready", "system prompt composed")
    if ev:
        yield ev

    resolved = resolve_entities(message)
    grounding = entity_grounding_observation(message)
    if grounding:
        observations.append(grounding)
        names = ", ".join(f"{x['entity']}→{x['ticker']}" for x in resolved)
        yield {
            "type": "thought",
            "data": {"content": f"已完成实体解析：{names}，后续工具调用将以解析后的 ticker 为准。"},
        }

    yield {
        "type": "thought",
        "data": {"content": "正在扩写意图、识别标的并发起首批并行检索…"},
    }

    if message.strip():
        try:
            ex_prompt = EXPAND_SEED_PROMPT.format(
                dialogue=dialogue_context.strip() or "（尚无历史对话。）",
                latest=message.strip(),
            )
            ev = _dbg_evt(t0, debug_stream, "graph.expand.llm", "before seed expansion ainvoke")
            if ev:
                yield ev
            ex_resp = await llm.ainvoke(
                [SystemMessage(content=system_text), HumanMessage(content=ex_prompt)]
            )
            seed_data = json.loads(_strip_json_fences(str(ex_resp.content)))
            ev = _dbg_evt(
                t0,
                debug_stream,
                "graph.expand.llm.done",
                f"parallel_calls={len((seed_data.get('parallel_calls') or []))}",
            )
            if ev:
                yield ev
            pcs = (seed_data.get("parallel_calls") or [])[:4]
            if resolved and not any(
                str(c.get("tool")) == "market_data"
                and str((c.get("tool_args") or {}).get("ticker", "")).upper() == "SNDK"
                for c in pcs
            ):
                pcs.insert(0, {"tool": "market_data", "tool_args": {"ticker": "SNDK", "period": "1mo"}})
                pcs.insert(
                    1,
                    {
                        "tool": "web_scraper",
                        "tool_args": {
                            "query": "SanDisk SNDK stock price independent listed 2025 spinoff Western Digital WDC",
                            "max_urls": 3,
                        },
                    },
                )
                pcs = pcs[:4]
            if pcs:
                plan_steps = [
                    {
                        "id": f"seed-{idx}",
                        "description": f"{c.get('tool')} {c.get('tool_args', {})}",
                        "tool": str(c.get("tool", "")),
                    }
                    for idx, c in enumerate(pcs)
                ]
                yield {"type": "plan", "data": {"steps": plan_steps}}

                async def _run_seed_call(call: dict[str, Any]) -> tuple[str, str, str, Optional[str]]:
                    tname = str(call.get("tool", ""))
                    targs = call.get("tool_args") or {}
                    return await _execute_grounded_tool(message, tname, targs)

                ev = _dbg_evt(
                    t0,
                    debug_stream,
                    "graph.seed.tools",
                    f"asyncio.gather {len(pcs)} seed tool(s)",
                )
                if ev:
                    yield ev
                for idx in range(len(pcs)):
                    yield {
                        "type": "step_update",
                        "data": {"step_id": f"seed-{idx}", "status": "running"},
                    }
                # Yield to the event loop so proxies / browsers can flush SSE before a long gather.
                await asyncio.sleep(0)
                # return_exceptions: one bad tool must not abort the whole seed phase after plan was shown.
                results = await asyncio.gather(
                    *[_run_seed_call(c) for c in pcs],
                    return_exceptions=True,
                )
                ev = _dbg_evt(t0, debug_stream, "graph.seed.tools.done", "seed tools finished")
                if ev:
                    yield ev
                await asyncio.sleep(0)
                for idx, r in enumerate(results):
                    sid = f"seed-{idx}"
                    call = pcs[idx]
                    tool_name_guess = str(call.get("tool", ""))
                    targs_guess = call.get("tool_args") or {}
                    if isinstance(r, BaseException):
                        logger.error(
                            "Seed tool failed step=%s tool=%s",
                            sid,
                            tool_name_guess,
                            exc_info=r,
                        )
                        err_txt = str(r)[:2000]
                        yield {
                            "type": "step_update",
                            "data": {
                                "step_id": sid,
                                "status": "error",
                                "result": err_txt,
                            },
                        }
                        await asyncio.sleep(0)
                        observations.append(
                            {
                                "phase": "seed",
                                "step": idx + 1,
                                "tool": tool_name_guess,
                                "tool_args": targs_guess,
                                "guard_note": None,
                                "observation": _cap_obs_text(f"Error: {err_txt}"),
                            }
                        )
                        continue
                    tool_name, tool_args, out, note = r
                    yield {
                        "type": "step_update",
                        "data": {
                            "step_id": sid,
                            "status": "done",
                            "result": out[:2000] if out else "",
                        },
                    }
                    await asyncio.sleep(0)
                    observations.append(
                        {
                            "phase": "seed",
                            "step": idx + 1,
                            "tool": tool_name,
                            "tool_args": tool_args,
                            "guard_note": note,
                            "observation": _cap_obs_text(out),
                        }
                    )
        except Exception:
            logger.warning("expand/seed phase skipped or failed", exc_info=True)

    yield {
        "type": "thought",
        "data": {"content": "正在启动投研智能体，进行多轮工具调研…"},
    }

    report_section = (
        previous_report.strip()
        if previous_report.strip()
        else "（尚无投研成稿。）"
    )

    for i in range(max_iterations):
        obs_summary = json.dumps(observations, ensure_ascii=False)
        reasoning_prompt = REASONER_PROMPT.format(
            dialogue=dialogue_context.strip() or "（尚无历史对话。）",
            report_section=report_section,
            latest_user=message.strip(),
            observations=obs_summary,
        )

        logger.info("Iteration %s: Reasoning...", i + 1)
        ev = _dbg_evt(
            t0,
            debug_stream,
            f"graph.reason.iter_{i + 1}",
            "before reasoner llm.ainvoke",
        )
        if ev:
            yield ev

        response = None
        try:
            response = await llm.ainvoke(
                [
                    SystemMessage(content=system_text),
                    HumanMessage(content=reasoning_prompt),
                ]
            )
            content = _strip_json_fences(str(response.content))
            data = json.loads(content)
            if not isinstance(data, dict):
                logger.warning(
                    "Reasoner JSON root is not an object: %s",
                    type(data).__name__,
                )
                data = {
                    "type": "finish",
                    "thought": "Reasoner returned a non-object JSON root; finalizing.",
                }
            ev = _dbg_evt(
                t0,
                debug_stream,
                f"graph.reason.parsed_{i + 1}",
                f"type={data.get('type')!r}",
            )
            if ev:
                yield ev
        except Exception as e:
            raw = getattr(response, "content", "") if response is not None else ""
            logger.error("Reasoning parse error: %s. Content: %s", e, raw)
            yield {
                "type": "thought",
                "data": {"content": "推理过程解析异常，正在尝试自我修正…"},
            }
            data = {"type": "finish", "thought": "Parse error; finalizing with partial data."}

        if data.get("type") == "clarification":
            yield {
                "type": "token",
                "data": {
                    "content": f"⚠️ **需进一步确认**：\n\n{data.get('message')}"
                },
            }
            return

        if data.get("type") == "finish":
            yield {
                "type": "thought",
                "data": {"content": "调研节点已完成，正在生成本轮对话摘要与投研总稿…"},
            }
            async for fev in _finalize_chat_and_report(
                llm,
                system_text,
                dialogue_context,
                message,
                previous_report,
                obs_summary,
                debug_stream=debug_stream,
                t0=t0,
            ):
                yield fev
            return

        if data.get("type") == "parallel":
            thought = data.get("thought", "并行拉取数据…")
            yield {"type": "thought", "data": {"content": f"第 {i + 1} 步：{thought}"}}
            calls = data.get("calls") or []
            calls = calls[:5]
            if calls:
                plan_steps = [
                    {
                        "id": f"p{idx}",
                        "description": f"{c.get('tool')} {c.get('tool_args', {})}",
                        "tool": str(c.get("tool", "")),
                    }
                    for idx, c in enumerate(calls)
                ]
                yield {"type": "plan", "data": {"steps": plan_steps}}

                async def _run_one(call: dict[str, Any]) -> tuple[str, Dict[str, Any], str, Optional[str]]:
                    tname = str(call.get("tool", ""))
                    targs = call.get("tool_args") or {}
                    return await _execute_grounded_tool(message, tname, targs)

                ev = _dbg_evt(
                    t0,
                    debug_stream,
                    f"graph.parallel_{i + 1}",
                    f"gather {len(calls)} tool call(s)",
                )
                if ev:
                    yield ev
                for idx in range(len(calls)):
                    yield {
                        "type": "step_update",
                        "data": {"step_id": f"p{idx}", "status": "running"},
                    }
                await asyncio.sleep(0)
                pairs = await asyncio.gather(
                    *[_run_one(c) for c in calls],
                    return_exceptions=True,
                )
                ev = _dbg_evt(t0, debug_stream, f"graph.parallel_{i + 1}.done", "tools returned")
                if ev:
                    yield ev
                await asyncio.sleep(0)
                for j, r in enumerate(pairs):
                    sid = f"p{j}"
                    call = calls[j]
                    tool_guess = str(call.get("tool", ""))
                    targs_guess = call.get("tool_args") or {}
                    if isinstance(r, BaseException):
                        logger.error(
                            "Parallel tool failed step=%s tool=%s",
                            sid,
                            tool_guess,
                            exc_info=r,
                        )
                        err_txt = str(r)[:2000]
                        yield {
                            "type": "step_update",
                            "data": {
                                "step_id": sid,
                                "status": "error",
                                "result": err_txt,
                            },
                        }
                        await asyncio.sleep(0)
                        observations.append(
                            {
                                "step": i + 1,
                                "tool": tool_guess,
                                "tool_args": targs_guess,
                                "guard_note": None,
                                "thought": thought,
                                "observation": _cap_obs_text(f"Error: {err_txt}"),
                            }
                        )
                        continue
                    tool_name, tool_args, out, note = r
                    yield {
                        "type": "step_update",
                        "data": {
                            "step_id": sid,
                            "status": "done",
                            "result": out[:2000] if out else "",
                        },
                    }
                    await asyncio.sleep(0)
                    observations.append(
                        {
                            "step": i + 1,
                            "tool": tool_name,
                            "tool_args": tool_args,
                            "guard_note": note,
                            "thought": thought,
                            "observation": _cap_obs_text(out),
                        }
                    )
            continue

        if data.get("type") == "action":
            tool_name = data.get("tool")
            tool_args = data.get("tool_args", {})
            thought = data.get("thought", "执行下一步调研…")
            yield {"type": "thought", "data": {"content": f"第 {i + 1} 步：{thought}"}}
            yield {
                "type": "thought",
                "data": {"content": f"正在使用 {tool_name} 获取数据…"},
            }
            ev = _dbg_evt(
                t0,
                debug_stream,
                f"graph.action_{i + 1}",
                f"before execute_tool {tool_name}",
            )
            if ev:
                yield ev
            tool_name, tool_args, result, note = await _execute_grounded_tool(
                message, str(tool_name), tool_args
            )
            ev = _dbg_evt(t0, debug_stream, f"graph.action_{i + 1}.done", f"tool {tool_name} returned")
            if ev:
                yield ev
            observations.append(
                {
                    "step": i + 1,
                    "tool": tool_name,
                    "tool_args": tool_args,
                    "guard_note": note,
                    "thought": thought,
                    "observation": _cap_obs_text(result),
                }
            )
            logger.info("Iteration %s: Action %s completed.", i + 1, tool_name)
            continue

        # Avoid silently burning max_iterations when the model returns an unexpected schema.
        logger.warning(
            "Reasoner JSON type not handled: %r (keys=%s)",
            data.get("type"),
            list(data.keys())[:15],
        )
        yield {
            "type": "thought",
            "data": {
                "content": f"模型返回了无法继续推理的格式（type={data.get('type')!r}），"
                "将根据已有结果生成本轮回复。"
            },
        }
        obs_summary = json.dumps(observations, ensure_ascii=False)
        async for fev in _finalize_chat_and_report(
            llm,
            system_text,
            dialogue_context,
            message,
            previous_report,
            obs_summary,
            debug_stream=debug_stream,
            t0=t0,
        ):
            yield fev
        return

    obs_summary = json.dumps(observations, ensure_ascii=False)
    yield {
        "type": "thought",
        "data": {"content": "已达到最大循环次数，正在根据已有结果生成本轮输出…"},
    }
    async for fev in _finalize_chat_and_report(
        llm,
        system_text,
        dialogue_context,
        message,
        previous_report,
        obs_summary,
        debug_stream=debug_stream,
        t0=t0,
    ):
        yield fev


async def run_agent(
    message: str,
    session_id: str,
    memory_context: str = "",
    *,
    rag_core_context: str = "",
    session_context_block: str = "",
    agent_style_context: str = "",
    dialogue_context: str = "",
    previous_report: str = "",
) -> dict:
    """Sync wrapper: chat answer + merged report markdown."""
    full_chat = ""
    last_report: Optional[str] = None
    async for event in run_agent_stream(
        message,
        session_id,
        memory_context,
        rag_core_context=rag_core_context,
        session_context_block=session_context_block,
        agent_style_context=agent_style_context,
        dialogue_context=dialogue_context,
        previous_report=previous_report,
    ):
        if event["type"] == "token":
            full_chat += event["data"].get("content", "")
        elif event["type"] == "report":
            last_report = event["data"].get("markdown")
    return {"answer": full_chat, "report_markdown": last_report, "tool_calls": []}
