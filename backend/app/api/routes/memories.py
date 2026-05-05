"""Long-term user memory (facts / corrections) per profile_id."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException

from app.db import crud
from app.db.session import async_session_maker
from app.schemas.persistence import MemoryCreate, MemoryRow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["memories"])


def _db() -> bool:
    return async_session_maker is not None


@router.get("", response_model=list[MemoryRow])
async def list_memories(profile_id: str, limit: int = 100):
    if not _db():
        raise HTTPException(status_code=503, detail="Database not available")
    if len(profile_id) < 8:
        raise HTTPException(status_code=400, detail="invalid profile_id")
    try:
        async with async_session_maker() as session:  # type: ignore[misc]
            rows = await crud.list_memories_full(session, profile_id, limit=limit)
            await session.commit()
            return [
                MemoryRow(
                    id=r.id,
                    profile_id=r.profile_id,
                    content=r.content,
                    created_at=r.created_at,
                )
                for r in rows
            ]
    except Exception as e:
        logger.exception("list memories failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("", response_model=MemoryRow)
async def create_memory(body: MemoryCreate):
    if not _db():
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        async with async_session_maker() as session:  # type: ignore[misc]
            row = await crud.add_memory(session, body.profile_id, body.content)
            await session.commit()
            await session.refresh(row)
            return MemoryRow(
                id=row.id,
                profile_id=row.profile_id,
                content=row.content,
                created_at=row.created_at,
            )
    except Exception as e:
        logger.exception("create memory failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, profile_id: str):
    if not _db():
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        mid = uuid.UUID(memory_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="invalid memory_id") from e
    try:
        async with async_session_maker() as session:  # type: ignore[misc]
            ok = await crud.delete_memory(session, mid, profile_id)
            await session.commit()
            if not ok:
                raise HTTPException(status_code=404, detail="not found")
            return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("delete memory failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
