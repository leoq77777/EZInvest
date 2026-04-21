import json
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    DoneEvent,
    PlanEvent,
    PlanStepInfo,
    StepUpdateEvent,
    SummarizingEvent,
    TokenEvent,
    ToolCallEvent,
    ToolCallStatus,
)
from app.agent.graph import run_agent, run_agent_stream

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("")
async def chat(request: ChatRequest):
    """Non-streaming chat: returns full response after agent completes."""
    start = time.perf_counter()
    try:
        result = await run_agent(request.message, request.session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    elapsed_ms = (time.perf_counter() - start) * 1000
    return ChatResponse(
        session_id=request.session_id,
        answer=result["answer"],
        tool_calls=result.get("tool_calls", []),
        total_latency_ms=round(elapsed_ms, 1),
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat: Plan -> Execute -> Summarize via SSE."""

    async def event_generator():
        start = time.perf_counter()
        try:
            async for event in run_agent_stream(
                request.message, request.session_id
            ):
                etype = event["type"]

                if etype == "plan":
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
                        StepUpdateEvent(**event["data"]).model_dump(),
                    )

                elif etype == "summarizing":
                    yield _sse_event(
                        "summarizing",
                        SummarizingEvent().model_dump(),
                    )

                elif etype == "token":
                    yield _sse_event(
                        "token",
                        TokenEvent(content=event["data"]).model_dump(),
                    )

                elif etype == "tool_call":
                    yield _sse_event("tool_call", event["data"])

        except Exception as e:
            yield _sse_event("error", {"detail": str(e)})
            return

        elapsed_ms = (time.perf_counter() - start) * 1000
        yield _sse_event(
            "done",
            DoneEvent(
                session_id=request.session_id,
                total_latency_ms=round(elapsed_ms, 1),
            ).model_dump(),
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
