"""Conversation + message history API."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.db import crud
from app.db import session as db_session
from app.schemas.persistence import (
    BootstrapRequest,
    BootstrapResponse,
    CommitTurnRequest,
    CommitTurnResponse,
    ConversationCreate,
    ConversationSummary,
    ServerMessage,
)
from app.services.chat_persist import (
    ConversationNotFoundForProfile,
    persist_turn_via_save_button,
)
from app.services.session_summarizer import schedule_summarize_other_sessions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _db() -> bool:
    return db_session.async_session_maker is not None


@router.post("/bootstrap", response_model=BootstrapResponse)
async def bootstrap(body: BootstrapRequest):
    """Return the latest conversation for this profile + messages, or create one."""
    if not _db():
        return BootstrapResponse(database_available=False)

    try:
        async with db_session.async_session_maker() as session:  # type: ignore[misc]
            existing = await crud.list_conversations(session, body.profile_id, limit=1)
            if existing:
                conv = existing[0]
                msgs = await crud.list_messages(session, conv.id)
                await session.commit()
                return BootstrapResponse(
                    database_available=True,
                    conversation_id=str(conv.id),
                    messages=[
                        ServerMessage(
                            id=m.id,
                            role=m.role,
                            content=m.content,
                            created_at=m.created_at,
                        )
                        for m in msgs
                    ],
                    report_markdown=conv.report_markdown,
                )
            conv = await crud.create_conversation(session, body.profile_id)
            await session.commit()
            return BootstrapResponse(
                database_available=True,
                conversation_id=str(conv.id),
                messages=[],
                report_markdown=None,
            )
    except Exception as e:
        logger.exception("bootstrap failed: %s", e)
        return BootstrapResponse(database_available=False)


@router.post("", response_model=ConversationSummary)
async def create_conversation(body: ConversationCreate):
    if not _db():
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        async with db_session.async_session_maker() as session:  # type: ignore[misc]
            conv = await crud.create_conversation(
                session, body.profile_id, title=body.title
            )
            await session.commit()
            await session.refresh(conv)
            return ConversationSummary(
                id=conv.id,
                profile_id=conv.profile_id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
    except Exception as e:
        logger.exception("create conversation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(profile_id: str, limit: int = 30):
    if not _db():
        raise HTTPException(status_code=503, detail="Database not available")
    if len(profile_id) < 8:
        raise HTTPException(status_code=400, detail="invalid profile_id")
    try:
        async with db_session.async_session_maker() as session:  # type: ignore[misc]
            rows = await crud.list_conversations(session, profile_id, limit=limit)
            await session.commit()
            return [
                ConversationSummary(
                    id=r.id,
                    profile_id=r.profile_id,
                    title=r.title,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in rows
            ]
    except Exception as e:
        logger.exception("list conversations failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{conversation_id}/commit-turn", response_model=CommitTurnResponse)
async def commit_turn(
    conversation_id: str,
    body: CommitTurnRequest,
    background_tasks: BackgroundTasks,
):
    """Persist the last streamed turn (user + assistant + report) and align title with the report."""
    if not _db():
        raise HTTPException(status_code=503, detail="Database not available")
    if len(body.profile_id) < 8:
        raise HTTPException(status_code=400, detail="invalid profile_id")
    try:
        uuid.UUID(conversation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid conversation_id") from e
    try:
        title = await persist_turn_via_save_button(
            body.profile_id,
            conversation_id,
            body.user_message,
            body.assistant_message,
            body.report_markdown,
            body.save_message_as_memory,
        )
    except ConversationNotFoundForProfile as e:
        raise HTTPException(status_code=404, detail="conversation not found") from e
    except Exception as e:
        logger.exception("commit_turn failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

    async def _after_commit() -> None:
        await schedule_summarize_other_sessions(body.profile_id, conversation_id)

    background_tasks.add_task(_after_commit)
    return CommitTurnResponse(ok=True, conversation_title=title or None)


@router.get("/{conversation_id}/research-report")
async def get_research_report(conversation_id: str, profile_id: str):
    """Latest merged markdown report for the conversation (live panel)."""
    if not _db():
        raise HTTPException(status_code=503, detail="Database not available")
    if len(profile_id) < 8:
        raise HTTPException(status_code=400, detail="invalid profile_id")
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid conversation_id") from e
    try:
        async with db_session.async_session_maker() as session:  # type: ignore[misc]
            conv = await crud.get_conversation(session, cid)
            if conv is None or conv.profile_id != profile_id:
                raise HTTPException(status_code=404, detail="conversation not found")
            await session.commit()
            return {"report_markdown": conv.report_markdown or ""}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get research report failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{conversation_id}/messages", response_model=list[ServerMessage])
async def get_messages(conversation_id: str, profile_id: str):
    if not _db():
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        cid = uuid.UUID(conversation_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid conversation_id") from e
    try:
        async with db_session.async_session_maker() as session:  # type: ignore[misc]
            conv = await crud.get_conversation(session, cid)
            if conv is None or conv.profile_id != profile_id:
                raise HTTPException(status_code=404, detail="conversation not found")
            msgs = await crud.list_messages(session, cid)
            await session.commit()
            return [
                ServerMessage(
                    id=m.id, role=m.role, content=m.content, created_at=m.created_at
                )
                for m in msgs
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get messages failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
