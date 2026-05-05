"""Persistence helpers for conversations, messages, and long-term memory."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.entity_resolution import derive_conversation_title
from app.db.models import (
    ChatMessage,
    Conversation,
    ConversationSummary,
    ProfileAgentStyle,
    UserMemory,
)


def _title_from_message(text: str, max_len: int = 80) -> str:
    return derive_conversation_title(text, max_len)


async def get_conversation(
    session: AsyncSession, conversation_id: uuid.UUID
) -> Optional[Conversation]:
    res = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    return res.scalar_one_or_none()


async def create_conversation(
    session: AsyncSession, profile_id: str, title: Optional[str] = None
) -> Conversation:
    conv = Conversation(profile_id=profile_id, title=title)
    session.add(conv)
    await session.flush()
    return conv


async def list_conversations(
    session: AsyncSession, profile_id: str, limit: int = 50
) -> List[Conversation]:
    res = await session.execute(
        select(Conversation)
        .where(Conversation.profile_id == profile_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def list_messages(
    session: AsyncSession, conversation_id: uuid.UUID
) -> List[ChatMessage]:
    res = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return list(res.scalars().all())


async def append_message(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    extra: Optional[dict[str, Any]] = None,
) -> ChatMessage:
    row = ChatMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        extra_json=json.dumps(extra, ensure_ascii=False) if extra else None,
    )
    session.add(row)
    await session.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(updated_at=datetime.now(timezone.utc))
    )
    await session.flush()
    return row


async def set_conversation_report(
    session: AsyncSession, conversation_id: uuid.UUID, report_markdown: str
) -> None:
    conv = await get_conversation(session, conversation_id)
    if conv is None:
        return
    conv.report_markdown = report_markdown.strip() or None
    await session.flush()


async def touch_conversation_title_if_empty(
    session: AsyncSession, conversation_id: uuid.UUID, first_user_text: str
) -> None:
    conv = await get_conversation(session, conversation_id)
    if conv and not conv.title:
        conv.title = _title_from_message(first_user_text)
        await session.flush()


async def set_conversation_title_from_source(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    source_text: str,
    *,
    max_title_len: int = 80,
) -> str:
    """Set title from report (or other) excerpt; returns stored title."""
    conv = await get_conversation(session, conversation_id)
    if conv is None:
        return ""
    derived = _title_from_message(source_text, max_title_len)
    conv.title = derived[:512]
    await session.flush()
    return conv.title or ""


async def list_memory_contents(
    session: AsyncSession, profile_id: str, limit: int = 40
) -> List[str]:
    res = await session.execute(
        select(UserMemory.content)
        .where(UserMemory.profile_id == profile_id)
        .order_by(UserMemory.created_at.desc())
        .limit(limit)
    )
    rows = list(res.scalars().all())
    # Return chronological order for prompt (oldest first among the slice)
    return list(reversed(rows))


async def add_memory(
    session: AsyncSession, profile_id: str, content: str
) -> UserMemory:
    row = UserMemory(profile_id=profile_id, content=content.strip())
    session.add(row)
    await session.flush()
    return row


async def delete_memory(
    session: AsyncSession, memory_id: uuid.UUID, profile_id: str
) -> bool:
    res = await session.execute(
        delete(UserMemory).where(
            UserMemory.id == memory_id,
            UserMemory.profile_id == profile_id,
        )
    )
    return (res.rowcount or 0) > 0


async def list_memories_full(
    session: AsyncSession, profile_id: str, limit: int = 100
) -> List[UserMemory]:
    res = await session.execute(
        select(UserMemory)
        .where(UserMemory.profile_id == profile_id)
        .order_by(UserMemory.created_at.desc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def get_conversation_summary(
    session: AsyncSession, conversation_id: uuid.UUID
) -> Optional[ConversationSummary]:
    res = await session.execute(
        select(ConversationSummary).where(
            ConversationSummary.conversation_id == conversation_id
        )
    )
    return res.scalar_one_or_none()


async def upsert_conversation_summary(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    profile_id: str,
    body: str,
    message_count: int,
) -> ConversationSummary:
    row = await get_conversation_summary(session, conversation_id)
    if row:
        row.body = body.strip()
        row.message_count = message_count
        await session.flush()
        return row
    row = ConversationSummary(
        conversation_id=conversation_id,
        profile_id=profile_id,
        body=body.strip(),
        message_count=message_count,
    )
    session.add(row)
    await session.flush()
    return row


async def get_profile_agent_style(
    session: AsyncSession, profile_id: str
) -> Optional[ProfileAgentStyle]:
    res = await session.execute(
        select(ProfileAgentStyle).where(ProfileAgentStyle.profile_id == profile_id)
    )
    return res.scalar_one_or_none()


async def upsert_profile_agent_style(
    session: AsyncSession, profile_id: str, style_markdown: str
) -> ProfileAgentStyle:
    row = await get_profile_agent_style(session, profile_id)
    if row:
        row.style_markdown = style_markdown.strip()
        await session.flush()
        return row
    row = ProfileAgentStyle(profile_id=profile_id, style_markdown=style_markdown.strip())
    session.add(row)
    await session.flush()
    return row


async def list_distinct_profile_ids(
    session: AsyncSession, limit: int = 200
) -> List[str]:
    res = await session.execute(
        select(Conversation.profile_id).distinct().limit(limit)
    )
    return [r[0] for r in res.all()]
