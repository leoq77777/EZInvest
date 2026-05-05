"""Periodically summarize non-active conversations and ingest into pgvector (Layer 3)."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from langchain_core.messages import HumanMessage

from app.agent.llm import get_llm
from app.config import get_settings
from app.db import crud
from app.db.session import async_session_maker

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = """你是金融投研助理的归档模块。下面是一组多轮对话文字稿（含用户与助手）。
请输出一份**中性、可复用**的中文摘要，要求：
1. 提取行业、标的、关键论断、用户偏好与曾出现的重要数字（若可能过时请标注「待核验」）。
2. 不要重复寒暄；不要编造稿中不存在的内容。
3. 控制在约 900 汉字以内，使用条目式。

---对话---
{transcript}
---
只输出摘要正文。"""

_throttle_mono: dict[str, float] = {}
_THROTTLE_SEC = 90.0


async def _llm_summarize(transcript: str) -> str:
    if len(transcript) > 28000:
        transcript = transcript[:28000] + "\n...[截断]..."
    llm = get_llm()
    prompt = SUMMARY_PROMPT.format(transcript=transcript)
    resp = await llm.ainvoke([HumanMessage(content=prompt)])
    return (getattr(resp, "content", None) or "").strip()


async def _ingest_summary_vector(
    profile_id: str, conversation_id: uuid.UUID, body: str
) -> None:
    try:
        from app.rag.pgvector_store import get_dynamic_store

        store = get_dynamic_store()
        tag = (
            f"[historical_session_summary profile={profile_id} "
            f"conversation={conversation_id}]\n"
        )
        await store.add_texts(
            [tag + body],
            metadatas=[
                {
                    "source": "historical_session_summary",
                    "profile_id": profile_id,
                    "conversation_id": str(conversation_id),
                }
            ],
        )
    except Exception:
        logger.warning("pgvector ingest for session summary failed", exc_info=True)


async def summarize_conversation_if_due(
    conversation_id: uuid.UUID,
    profile_id: str,
    *,
    skip_if_updated_within: timedelta | None = None,
) -> bool:
    """
    If conversation has enough messages and summary is stale, rewrite summary + RAG ingest.
    Returns True when a summary row was (re)written.
    """
    if async_session_maker is None or not get_settings().enable_persistence:
        return False
    settings = get_settings()
    min_m = settings.min_messages_to_summarize_session

    async with async_session_maker() as session:
        conv = await crud.get_conversation(session, conversation_id)
        if conv is None or conv.profile_id != profile_id:
            return False
        if skip_if_updated_within and conv.updated_at:
            boundary = datetime.now(timezone.utc) - skip_if_updated_within
            if conv.updated_at > boundary:
                return False
        msgs = await crud.list_messages(session, conversation_id)
        if len(msgs) < min_m:
            return False
        prev = await crud.get_conversation_summary(session, conversation_id)
        if prev is not None:
            if len(msgs) <= prev.message_count + 2:
                return False
        transcript = "\n".join(f"{m.role}: {m.content}" for m in msgs)

    body = await _llm_summarize(transcript)
    if not body:
        return False

    async with async_session_maker() as session:
        await crud.upsert_conversation_summary(
            session,
            conversation_id,
            profile_id,
            body,
            len(msgs),
        )
        await session.commit()

    await _ingest_summary_vector(profile_id, conversation_id, body)
    logger.info(
        "conversation summary upserted conv=%s profile=%s msgs=%s",
        conversation_id,
        profile_id,
        len(msgs),
    )
    return True


async def summarize_other_sessions_for_profile(
    profile_id: str,
    current_conversation_id: Optional[str],
) -> int:
    """Summarize peer sessions (excluding current). Returns number of conversations updated."""
    if async_session_maker is None:
        return 0
    if not get_settings().enable_persistence:
        return 0

    async with async_session_maker() as session:
        convs = await crud.list_conversations(session, profile_id, limit=40)

    updated = 0
    for c in convs:
        if current_conversation_id and str(c.id) == current_conversation_id:
            continue
        try:
            if await summarize_conversation_if_due(c.id, profile_id):
                updated += 1
        except Exception:
            logger.exception("summarize failed conv=%s", c.id)
    return updated


async def schedule_summarize_other_sessions(
    profile_id: Optional[str], current_conversation_id: Optional[str]
) -> None:
    """Throttled fire-and-forget hook after a chat turn."""
    if not profile_id:
        return
    now = time.monotonic()
    if _throttle_mono.get(profile_id, 0) + _THROTTLE_SEC > now:
        return
    _throttle_mono[profile_id] = now
    try:
        await summarize_other_sessions_for_profile(profile_id, current_conversation_id)
    except Exception:
        logger.exception("schedule_summarize_other_sessions failed")


async def periodic_summarize_all_profiles_loop() -> None:
    """Background loop: stale conversations across profiles."""
    delay = max(5, get_settings().session_summary_startup_delay_sec)
    await asyncio.sleep(delay)
    while True:
        interval = 60
        try:
            settings = get_settings()
            if not settings.enable_session_summary_job or async_session_maker is None:
                await asyncio.sleep(60)
                continue
            interval = max(60, settings.session_summary_interval_sec)
            async with async_session_maker() as session:
                pids = await crud.list_distinct_profile_ids(session, limit=300)
            stale = timedelta(minutes=12)
            for pid in pids:
                async with async_session_maker() as session:
                    convs = await crud.list_conversations(session, pid, limit=40)
                for c in convs:
                    try:
                        await summarize_conversation_if_due(
                            c.id, pid, skip_if_updated_within=stale
                        )
                    except Exception:
                        logger.exception("periodic summarize conv=%s", c.id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("periodic_summarize_all_profiles_loop tick failed")
            interval = max(60, get_settings().session_summary_interval_sec)
        await asyncio.sleep(interval)
