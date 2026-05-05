from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProfileIdBody(BaseModel):
    profile_id: str = Field(..., min_length=8, max_length=128)


class BootstrapRequest(ProfileIdBody):
    pass


class ServerMessage(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime


class BootstrapResponse(BaseModel):
    database_available: bool
    conversation_id: Optional[str] = None
    messages: List[ServerMessage] = []
    report_markdown: Optional[str] = None


class ConversationCreate(BaseModel):
    profile_id: str = Field(..., min_length=8, max_length=128)
    title: Optional[str] = Field(default=None, max_length=512)


class ConversationSummary(BaseModel):
    id: UUID
    profile_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime


class MemoryCreate(BaseModel):
    profile_id: str = Field(..., min_length=8, max_length=128)
    content: str = Field(..., min_length=1, max_length=4000)


class MemoryRow(BaseModel):
    id: UUID
    profile_id: str
    content: str
    created_at: datetime


class CommitTurnRequest(ProfileIdBody):
    """Explicitly persist one turn after streaming (Save in live report panel)."""

    user_message: str = Field(..., min_length=1, max_length=4000)
    assistant_message: str = Field(default="", max_length=400_000)
    report_markdown: str = Field(..., min_length=1, max_length=2_000_000)
    save_message_as_memory: bool = False


class CommitTurnResponse(BaseModel):
    ok: bool = True
    conversation_title: Optional[str] = None
