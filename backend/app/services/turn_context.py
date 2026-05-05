"""Load multi-turn dialogue + persisted research report for one agent turn."""

from __future__ import annotations

import logging
import uuid
from typing import Optional, Tuple

from app.db import crud
from app.db.session import async_session_maker

logger = logging.getLogger(__name__)

# Longer than session_context_messages in memory_layers — used by reasoner.
MAX_DIALOGUE_MESSAGES = 40


async def load_dialogue_and_report(
    profile_id: Optional[str], conversation_id: Optional[str]
) -> Tuple[str, str]:
    """
    Returns (dialogue_block, previous_report_markdown).
    Dialogue includes the latest user message already persisted by append_user_turn.
    """
    if not profile_id or not conversation_id or async_session_maker is None:
        return "", ""
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        return "", ""
    try:
        async with async_session_maker() as session:
            conv = await crud.get_conversation(session, cid)
            if conv is None or conv.profile_id != profile_id:
                return "", ""
            report = (conv.report_markdown or "").strip()
            msgs = await crud.list_messages(session, cid)
        tail = msgs[-MAX_DIALOGUE_MESSAGES:] if len(msgs) > MAX_DIALOGUE_MESSAGES else msgs
        lines: list[str] = []
        for m in tail:
            label = "用户" if m.role == "user" else "助手"
            lines.append(f"{label}: {m.content}")
        return "\n".join(lines), report
    except Exception:
        logger.exception("load_dialogue_and_report failed")
        return "", ""
