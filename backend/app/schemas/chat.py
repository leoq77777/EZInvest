from __future__ import annotations

from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, List
from uuid import uuid4


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    stream: bool = True


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


# ---------------------------------------------------------------------------
# Non-streaming response
# ---------------------------------------------------------------------------

class ChatResponse(BaseModel):
    session_id: str
    answer: str
    tool_calls: List[ToolCallEvent] = []
    total_latency_ms: float
