"""Load / persist chat turns and long-term memory (optional DB)."""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.db import crud
from app.db import session as db_session

logger = logging.getLogger(__name__)


class ConversationNotFoundForProfile(Exception):
    """Conversation missing or profile_id does not own it."""


async def load_memory_prompt_block(profile_id: str | None) -> str:
    """Return a bullet list of user memories for system prompt injection."""
    if not profile_id or db_session.async_session_maker is None:
        return ""
    try:
        async with db_session.async_session_maker() as session:
            lines = await crud.list_memory_contents(session, profile_id, limit=40)
        if not lines:
            return ""
        return "\n".join(f"- {ln}" for ln in lines)
    except Exception:
        logger.exception("load_memory_prompt_block failed")
        return ""


async def append_user_turn(
    profile_id: str, conversation_id: str, user_text: str
) -> None:
    if db_session.async_session_maker is None:
        return
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        return
    try:
        async with db_session.async_session_maker() as session:
            conv = await crud.get_conversation(session, cid)
            if conv is None or conv.profile_id != profile_id:
                return
            await crud.append_message(session, cid, "user", user_text)
            await crud.touch_conversation_title_if_empty(session, cid, user_text)
            await session.commit()
    except Exception:
        logger.exception("append_user_turn failed")


async def append_assistant_turn(
    profile_id: str,
    conversation_id: str,
    user_text: str,
    assistant_text: str,
    save_user_message_as_memory: bool,
    report_markdown: Optional[str] = None,
) -> None:
    if db_session.async_session_maker is None:
        return
    has_chat = bool(assistant_text.strip())
    has_report = bool((report_markdown or "").strip())
    if not has_chat and not has_report:
        return
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        return
    try:
        async with db_session.async_session_maker() as session:
            conv = await crud.get_conversation(session, cid)
            if conv is None or conv.profile_id != profile_id:
                return
            chat_body = (
                assistant_text.strip()
                if has_chat
                else "（本轮仅更新了投研报告，见右侧面板。）"
            )
            await crud.append_message(session, cid, "assistant", chat_body)
            if report_markdown and report_markdown.strip():
                await crud.set_conversation_report(session, cid, report_markdown)
            if save_user_message_as_memory and user_text.strip():
                await crud.add_memory(session, profile_id, user_text.strip())
            await session.commit()
    except Exception:
        logger.exception("append_assistant_turn failed")


async def persist_turn_via_save_button(
    profile_id: str,
    conversation_id: str,
    user_text: str,
    assistant_text: str,
    report_markdown: str,
    save_user_message_as_memory: bool,
) -> str:
    """
    Persist user + assistant + merged report in one transaction.
    Conversation title is overwritten from the report excerpt (derive_conversation_title).

    Raises ConversationNotFoundForProfile when the row is missing or not owned.
    """
    if db_session.async_session_maker is None:
        raise RuntimeError("async_session_maker not configured")
    report_md = (report_markdown or "").strip()
    if not report_md:
        raise ValueError("report_markdown must be non-empty")
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError as e:
        raise ConversationNotFoundForProfile from e

    title_source = report_md[:12000]

    async with db_session.async_session_maker() as session:
        conv = await crud.get_conversation(session, cid)
        if conv is None or conv.profile_id != profile_id:
            raise ConversationNotFoundForProfile()

        await crud.set_conversation_title_from_source(session, cid, title_source)

        await crud.append_message(session, cid, "user", user_text.strip())

        has_chat = bool((assistant_text or "").strip())
        chat_body = (
            assistant_text.strip()
            if has_chat
            else "（本轮仅更新了投研报告，见右侧面板。）"
        )
        await crud.append_message(session, cid, "assistant", chat_body)

        await crud.set_conversation_report(session, cid, report_md)

        if save_user_message_as_memory and user_text.strip():
            await crud.add_memory(session, profile_id, user_text.strip())

        await session.commit()
        await session.refresh(conv)
        return (conv.title or "").strip()
