from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes import chat, conversations, health, memories, profile_agent

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.session import init_db, close_db
    from app.config import get_settings

    app.state.db_ready = await init_db()
    if not app.state.db_ready:
        logging.getLogger(__name__).warning(
            "Persistence unavailable (see database log above). "
            "API still runs; conversations/bootstrap will skip DB writes."
        )
    summary_task: asyncio.Task | None = None
    s = get_settings()
    if app.state.db_ready and s.enable_session_summary_job:
        from app.services.session_summarizer import periodic_summarize_all_profiles_loop

        summary_task = asyncio.create_task(periodic_summarize_all_profiles_loop())
    try:
        yield
    finally:
        if summary_task is not None:
            summary_task.cancel()
            try:
                await summary_task
            except asyncio.CancelledError:
                pass
        await close_db()


app = FastAPI(
    title="EZInvest API",
    description="AI Investment Consulting Assistant",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(memories.router, prefix="/api")
app.include_router(profile_agent.router, prefix="/api")
