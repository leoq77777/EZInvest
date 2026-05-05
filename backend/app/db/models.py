"""ORM models for chat persistence and long-term user memory."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # Incremental research report (markdown); chat bubbles stay concise.
    report_markdown: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class ChatMessage(Base):
    """One row per user or assistant turn (assistant = final reply text)."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text())
    extra_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class UserMemory(Base):
    """Long-term facts / corrections per anonymous profile_id (browser-stable)."""

    __tablename__ = "user_memories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[str] = mapped_column(String(128), index=True)
    content: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ConversationSummary(Base):
    """LLM digest of a conversation; ingested into vector store for Layer-3 RAG."""

    __tablename__ = "conversation_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    profile_id: Mapped[str] = mapped_column(String(128), index=True)
    body: Mapped[str] = mapped_column(Text())
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ProfileAgentStyle(Base):
    """Per-profile Layer-2: advisor tone, habits, self-notes (markdown)."""

    __tablename__ = "profile_agent_styles"

    profile_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    style_markdown: Mapped[str] = mapped_column(Text())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
