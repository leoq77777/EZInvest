import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    DoneEvent,
    ThoughtEvent,
    PlanEvent,
    PlanStepInfo,
    ReportEvent,
    StepUpdateEvent,
    SummarizingEvent,
    TokenEvent,
)
from app.agent.graph import run_agent, run_agent_stream
from app.services.chat_persist import append_assistant_turn, append_user_turn
from app.services.memory_layers import assemble_memory_layers
from app.services.session_summarizer import schedule_summarize_other_sessions
from app.services.turn_context import load_dialogue_and_report
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("")
async def chat(request: ChatRequest):
    """Non-streaming chat: returns full response after agent completes."""
    start = time.perf_counter()
    layers = await assemble_memory_layers(
        request.profile_id,
        request.conversation_id,
        request.message,
    )
    dialogue_block, previous_report = await load_dialogue_and_report(
        request.profile_id, request.conversation_id
    )
    try:
        result = await run_agent(
            request.message,
            request.session_id,
            layers.user_memory_block,
            rag_core_context=layers.rag_core_block,
            session_context_block=layers.session_context_block,
            agent_style_context=layers.agent_style_block,
            dialogue_context=dialogue_block,
            previous_report=previous_report,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    elapsed_ms = (time.perf_counter() - start) * 1000
    answer = result.get("answer") or result.get("content") or ""
    return ChatResponse(
        session_id=request.session_id,
        answer=answer,
        tool_calls=result.get("tool_calls", []),
        total_latency_ms=round(elapsed_ms, 1),
        report_markdown=result.get("report_markdown"),
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
):
    """Streaming chat with optional persistence + long-term memory injection."""

    async def _gen_core():
        start = time.perf_counter()
        assistant_chunks: list[str] = []
        last_report_holder: list = [None]
        settings = get_settings()
        stream_debug = bool(request.debug_stream or settings.debug_stream)
        logger.info(
            "chat stream: request.debug_stream=%s settings.debug_stream=%s effective=%s",
            request.debug_stream,
            settings.debug_stream,
            stream_debug,
        )
        if stream_debug:
            logger.info(
                "chat stream SSE debug enabled (event:debug); session=%s conv=%s",
                (request.session_id or "")[:12],
                request.conversation_id or "—",
            )

        def _dbg(phase: str, detail: str = "") -> str:
            return _sse_event(
                "debug",
                {
                    "phase": phase,
                    "detail": detail,
                    "elapsed_ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )

        # When diagnostic is on, emit debug *before* the first thought so the client always
        # has a chance to parse at least one `event: debug` even if the connection drops early.
        if stream_debug:
            yield _dbg(
                "route.handshake",
                "debug_stream active; first SSE frame (before first thought)",
            )
        # First chunk ASAP: do not await DB/RAG before returning StreamingResponse body,
        # otherwise the client hangs with no SSE until persistence + memory assembly finish.
        yield _sse_event(
            "thought",
            ThoughtEvent(content="已连接，开始处理本轮请求…").model_dump(),
        )
        if stream_debug:
            yield _dbg("route.enter", "past first thought chunk")

        if (
            request.auto_persist_turn
            and getattr(http_request.app.state, "db_ready", False)
            and request.profile_id
            and request.conversation_id
        ):
            yield _sse_event(
                "thought",
                ThoughtEvent(content="正在将本轮用户消息写入会话…").model_dump(),
            )
            if stream_debug:
                yield _dbg("route.before_append_user", "append_user_turn")
            await append_user_turn(
                request.profile_id, request.conversation_id, request.message
            )
            if stream_debug:
                yield _dbg("route.after_append_user", "user turn persisted")

        yield _sse_event(
            "thought",
            ThoughtEvent(
                content="正在加载记忆层、对话摘要与向量检索（RAG，可能需数秒）…"
            ).model_dump(),
        )
        if stream_debug:
            yield _dbg(
                "route.before_memory_gather",
                "assemble_memory_layers + load_dialogue_and_report",
            )

        async def _memory_gather():
            return await asyncio.gather(
                assemble_memory_layers(
                    request.profile_id,
                    request.conversation_id,
                    request.message,
                ),
                load_dialogue_and_report(
                    request.profile_id, request.conversation_id
                ),
            )

        ka_sec = max(0.0, float(settings.sse_keepalive_interval_sec))
        if ka_sec > 0:
            mem_task = asyncio.create_task(_memory_gather())
            while not mem_task.done():
                done_set, _ = await asyncio.wait(
                    {mem_task},
                    timeout=ka_sec,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if mem_task in done_set:
                    break
                yield ": sse-keepalive\n\n"
            layers, (dialogue_block, previous_report) = await mem_task
        else:
            layers, (dialogue_block, previous_report) = await _memory_gather()
        if stream_debug:
            yield _dbg("route.after_memory_gather", "memory + dialogue ready")
        yield _sse_event(
            "thought",
            ThoughtEvent(
                content="上下文已就绪，正在启动 Agent 推理…"
            ).model_dump(),
        )
        try:
            if stream_debug:
                yield _dbg("route.before_graph", "run_agent_stream")
            agen = run_agent_stream(
                request.message,
                request.session_id,
                layers.user_memory_block,
                rag_core_context=layers.rag_core_block,
                session_context_block=layers.session_context_block,
                agent_style_context=layers.agent_style_block,
                dialogue_context=dialogue_block,
                previous_report=previous_report,
                debug_stream=stream_debug,
            )
            ait = agen.__aiter__()
            # NEVER use asyncio.wait_for(ait.__anext__(), timeout=...): on timeout wait_for
            # *cancels* the __anext__ awaitable, which can close run_agent_stream mid-step
            # (e.g. during a long asyncio.gather for parallel tools) and drop the stream
            # without a normal done frame. Instead, keep one pending anext Task and use
            # asyncio.wait(..., timeout=) so timeouts do not cancel the generator.
            next_event_task: Optional[asyncio.Task] = None

            def _next_event_task() -> asyncio.Task:
                nonlocal next_event_task
                if next_event_task is None:
                    next_event_task = asyncio.create_task(ait.__anext__())
                return next_event_task

            while True:
                if ka_sec > 0:
                    pending = _next_event_task()
                    done_set, _ = await asyncio.wait(
                        {pending},
                        timeout=ka_sec,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if not done_set:
                        yield ": sse-keepalive\n\n"
                        # Some proxies buffer ':' comment lines; a tiny data frame helps flush.
                        yield _sse_event(
                            "token",
                            TokenEvent(content="").model_dump(),
                        )
                        continue
                    next_event_task = None
                    try:
                        event = pending.result()
                    except StopAsyncIteration:
                        break
                else:
                    try:
                        event = await ait.__anext__()
                    except StopAsyncIteration:
                        break

                etype = event["type"]

                if etype == "thought":
                    yield _sse_event(
                        "thought",
                        ThoughtEvent(content=event["data"]["content"]).model_dump(),
                    )

                elif etype == "plan":
                    yield _sse_event(
                        "plan",
                        PlanEvent(
                            steps=[
                                PlanStepInfo(**s) for s in event["data"]["steps"]
                            ]
                        ).model_dump(),
                    )

                elif etype == "step_update":
                    yield _sse_event(
                        "step_update",
                        StepUpdateEvent(**event["data"]).model_dump(mode="json"),
                    )

                elif etype == "summarizing":
                    yield _sse_event(
                        "summarizing",
                        SummarizingEvent().model_dump(),
                    )

                elif etype == "token":
                    chunk = event["data"]["content"]
                    if chunk:
                        assistant_chunks.append(chunk)
                    yield _sse_event(
                        "token",
                        TokenEvent(content=chunk).model_dump(),
                    )

                elif etype == "tool_call":
                    yield _sse_event("tool_call", event["data"])

                elif etype == "report":
                    md = (event.get("data") or {}).get("markdown", "")
                    last_report_holder[0] = md
                    yield _sse_event(
                        "report",
                        ReportEvent(markdown=md).model_dump(),
                    )

                elif etype == "debug":
                    yield _sse_event("debug", event.get("data") or {})

        except Exception as e:
            logger.exception("stream error: %s", e)
            yield _sse_event("error", {"detail": str(e)})
            err_elapsed_ms = (time.perf_counter() - start) * 1000
            yield _sse_event(
                "done",
                DoneEvent(
                    session_id=request.session_id,
                    total_latency_ms=round(err_elapsed_ms, 1),
                ).model_dump(),
            )
            return

        elapsed_ms = (time.perf_counter() - start) * 1000
        if stream_debug:
            yield _dbg("route.before_done", "stream finished agent loop")
        yield _sse_event(
            "done",
            DoneEvent(
                session_id=request.session_id,
                total_latency_ms=round(elapsed_ms, 1),
            ).model_dump(),
        )

        # Do NOT await DB persistence here: it can block for minutes (locks / slow PG).
        # Proxies and the frontend idle watchdog may then close the stream before the
        # client ever sees the buffered `done` frame. Persist in a background task instead.
        full_reply = "".join(assistant_chunks)
        report_md = (last_report_holder[0] or "").strip()
        has_assistant_text = bool(full_reply.strip())
        has_report = bool(report_md)
        # Must persist when there is a merged report even if chat delta was empty —
        # otherwise refresh shows no history (user row exists but UI feels "blank"
        # if only report mattered, and report panel also reloads empty).
        if (
            request.auto_persist_turn
            and getattr(http_request.app.state, "db_ready", False)
            and request.profile_id
            and request.conversation_id
            and (has_assistant_text or has_report)
        ):

            async def _persist_turn() -> None:
                try:
                    await append_assistant_turn(
                        request.profile_id,
                        request.conversation_id,
                        request.message,
                        full_reply,
                        request.save_message_as_memory,
                        report_markdown=last_report_holder[0],
                    )
                    await schedule_summarize_other_sessions(
                        request.profile_id,
                        request.conversation_id,
                    )
                except Exception:
                    logger.exception(
                        "append_assistant_turn failed (background); conversation_id=%s",
                        request.conversation_id,
                    )

            background_tasks.add_task(_persist_turn)

    async def event_generator():
        """Yield SSE; never let an uncaught exception become a bare HTTP 500 without a body."""
        try:
            async for chunk in _gen_core():
                yield chunk
        except Exception as e:
            logger.exception("chat stream fatal (outer): %s", e)
            yield _sse_event("error", {"detail": str(e)})
            yield _sse_event(
                "done",
                DoneEvent(
                    session_id=request.session_id,
                    total_latency_ms=0.0,
                ).model_dump(),
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, no-transform",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
