from __future__ import annotations

from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, List
from uuid import uuid4


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    stream: bool = True
    # Persistence (optional): stable browser id + server-side conversation
    profile_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Stable client id (e.g. localStorage) for history + memory",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        max_length=36,
        description="UUID of conversation row; required to persist turns",
    )
    save_message_as_memory: bool = Field(
        default=False,
        description="If true, also store the user message in long-term memory after reply",
    )
    auto_persist_turn: bool = Field(
        default=False,
        description=(
            "If true, persist this turn during /stream (user row at start, assistant+report in background). "
            "If false (default), turns are saved only via POST .../commit-turn when the user clicks Save."
        ),
    )
    debug_stream: bool = Field(
        default=False,
        description=(
            "Request SSE event: debug (phase + elapsed_ms). "
            "Also enable via backend DEBUG_STREAM=true or frontend NEXT_PUBLIC_STREAM_DEBUG=1 at startup."
        ),
    )


# ---------------------------------------------------------------------------
# SSE event payloads
# ---------------------------------------------------------------------------

class ThoughtEvent(BaseModel):
    content: str

class ToolCallStatus(str, Enum):
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class ToolCallEvent(BaseModel):
    tool: str
    status: ToolCallStatus
    query: Optional[str] = None
    result: Optional[dict] = None
    latency_ms: Optional[float] = None


class TokenEvent(BaseModel):
    content: str


class DoneEvent(BaseModel):
    session_id: str
    total_latency_ms: float


class PlanStepInfo(BaseModel):
    id: str
    description: str
    tool: str


class PlanEvent(BaseModel):
    steps: List[PlanStepInfo]


class StepUpdateEvent(BaseModel):
    step_id: str
    status: str
    result: Optional[str] = None
    latency_ms: Optional[float] = None


class SummarizingEvent(BaseModel):
    pass


class ReportEvent(BaseModel):
    """Full incremental research report (markdown) for the live report panel."""

    markdown: str


# ---------------------------------------------------------------------------
# Non-streaming response
# ---------------------------------------------------------------------------

class ChatResponse(BaseModel):
    session_id: str
    answer: str
    tool_calls: List[ToolCallEvent] = []
    total_latency_ms: float
    report_markdown: Optional[str] = None
