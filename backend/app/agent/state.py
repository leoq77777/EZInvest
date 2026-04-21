"""Agent state definition for the Plan-Execute-Summarize pipeline."""

from __future__ import annotations

from typing import Annotated, Optional, List
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class PlanStep(TypedDict, total=False):
    id: str
    description: str
    tool: str
    tool_args: dict
    status: str  # "pending" | "running" | "done" | "error"


class StepResult(TypedDict, total=False):
    step_id: str
    tool: str
    output: str
    error: Optional[str]


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    session_id: str
    plan: List[PlanStep]
    step_results: List[StepResult]
    original_query: str
