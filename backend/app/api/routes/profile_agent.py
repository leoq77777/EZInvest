"""Per-profile advisor style (Layer 2)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import crud
from app.db.session import async_session_maker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


class AgentStyleUpsert(BaseModel):
    profile_id: str = Field(..., min_length=8, max_length=128)
    style_markdown: str = Field(..., min_length=0, max_length=16000)


@router.post("/agent-style", summary="Upsert Layer-2 advisor style for a profile")
async def upsert_agent_style(body: AgentStyleUpsert):
    if async_session_maker is None:
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        async with async_session_maker() as session:
            await crud.upsert_profile_agent_style(
                session, body.profile_id, body.style_markdown
            )
            await session.commit()
        return {"ok": True, "profile_id": body.profile_id}
    except Exception as e:
        logger.exception("upsert_agent_style failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
