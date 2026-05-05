"""Assemble three-layer memory for the agent: session excerpt, agent style, RAG core."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from app.config import get_settings
from app.db import crud
from app.db.session import async_session_maker
from app.services.chat_persist import load_memory_prompt_block

logger = logging.getLogger(__name__)


def _format_rag_hits(results: list[dict]) -> str:
    if not results:
        return "（本次检索暂无命中片段；请通过工具调用获取或验证数据。）"
    parts = []
    for i, d in enumerate(results, 1):
        src = d.get("source", "?")
        score = d.get("score", 0.0)
        text = (d.get("text") or "").strip()
        parts.append(f"[{i}] source={src} score={score:.4f}\n{text}")
    return "\n\n---\n\n".join(parts)


async def build_rag_core_block(query: str) -> str:
    """Layer 3: hybrid retrieval (FAISS + BM25 + pgvector) — decision-grade corpus."""
    try:
        from app.rag.retriever import HybridRetriever

        settings = get_settings()
        retriever = HybridRetriever()
        docs = await retriever.retrieve(query.strip(), top_k=settings.rag_core_top_k)
        return _format_rag_hits(docs)
    except Exception:
        logger.exception("build_rag_core_block failed")
        return "（RAG 检索暂时不可用。）"


async def build_session_context_block(
    profile_id: Optional[str], conversation_id: Optional[str]
) -> str:
    """Layer 1: recent turns in the active conversation (already persisted)."""
    if not profile_id or not conversation_id or async_session_maker is None:
        return ""
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError:
        return ""
    try:
        async with async_session_maker() as session:
            conv = await crud.get_conversation(session, cid)
            if conv is None or conv.profile_id != profile_id:
                return ""
            msgs = await crud.list_messages(session, cid)
        n = get_settings().session_context_messages
        tail = msgs[-n:] if len(msgs) > n else msgs
        if not tail:
            return "（当前会话尚无历史轮次。）"
        lines: list[str] = []
        for m in tail:
            label = "用户" if m.role == "user" else "助手"
            lines.append(f"{label}: {m.content}")
        return "\n".join(lines)
    except Exception:
        logger.exception("build_session_context_block failed")
        return ""


async def build_agent_style_block(profile_id: Optional[str]) -> str:
    """Layer 2: advisor tone / habits — DB override then env default."""
    text = (get_settings().agent_style_markdown or "").strip()
    if not profile_id or async_session_maker is None:
        return text
    try:
        async with async_session_maker() as session:
            row = await crud.get_profile_agent_style(session, profile_id)
        if row and row.style_markdown.strip():
            return row.style_markdown.strip()
    except Exception:
        logger.exception("build_agent_style_block failed")
    return text


@dataclass
class MemoryLayers:
    """Blocks appended to system prompt (ordering fixed in graph)."""

    rag_core_block: str
    session_context_block: str
    agent_style_block: str
    user_memory_block: str


async def assemble_memory_layers(
    profile_id: Optional[str],
    conversation_id: Optional[str],
    user_message: str,
) -> MemoryLayers:
    user_memory_block = await load_memory_prompt_block(profile_id)
    rag_c, sess_c, style_c = await asyncio.gather(
        build_rag_core_block(user_message),
        build_session_context_block(profile_id, conversation_id),
        build_agent_style_block(profile_id),
    )
    return MemoryLayers(
        rag_core_block=rag_c,
        session_context_block=sess_c,
        agent_style_block=style_c,
        user_memory_block=user_memory_block,
    )
