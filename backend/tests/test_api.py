"""API endpoint tests – agent is mocked so tests run without LLM/Redis."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.memory_layers import MemoryLayers


def _empty_layers() -> MemoryLayers:
    return MemoryLayers(
        rag_core_block="",
        session_context_block="",
        agent_style_block="",
        user_memory_block="",
    )


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# =============================================================================
# Health endpoints
# =============================================================================

@pytest.mark.asyncio
async def test_liveness(client):
    response = await client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


@pytest.mark.asyncio
@patch("app.api.routes.health._check_redis", new_callable=AsyncMock, return_value={"status": "ok", "latency_ms": 1.0})
@patch("app.api.routes.health._check_llm", new_callable=AsyncMock, return_value={"status": "ok", "latency_ms": 10.0})
@patch("app.api.routes.health._check_market_data", new_callable=AsyncMock, return_value={"status": "ok", "latency_ms": 200.0})
async def test_health_all_ok(mock_md, mock_llm, mock_redis, client):
    response = await client.get("/api/health")
    data = response.json()
    assert data["status"] == "healthy"
    assert data["components"]["redis"]["status"] == "ok"


@pytest.mark.asyncio
@patch("app.api.routes.health._check_redis", new_callable=AsyncMock, return_value={"status": "down", "error": "connection refused"})
@patch("app.api.routes.health._check_llm", new_callable=AsyncMock, return_value={"status": "ok", "latency_ms": 10.0})
@patch("app.api.routes.health._check_market_data", new_callable=AsyncMock, return_value={"status": "ok", "latency_ms": 200.0})
async def test_health_redis_down(mock_md, mock_llm, mock_redis, client):
    response = await client.get("/api/health")
    data = response.json()
    assert data["status"] == "unhealthy"


# =============================================================================
# Chat endpoint
# =============================================================================

@pytest.mark.asyncio
async def test_chat_validation_empty_message(client):
    """Pydantic rejects empty message."""
    response = await client.post("/api/chat", json={"message": "", "stream": False})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_validation_too_long(client):
    """Pydantic rejects messages over 2000 chars."""
    response = await client.post("/api/chat", json={"message": "x" * 2001})
    assert response.status_code == 422


@pytest.mark.asyncio
@patch("app.api.routes.chat.assemble_memory_layers", new_callable=AsyncMock)
@patch("app.api.routes.chat.run_agent", new_callable=AsyncMock)
async def test_chat_success(mock_run_agent, mock_assemble, client):
    """Non-streaming chat returns well-formed response when agent succeeds."""
    mock_assemble.return_value = _empty_layers()
    mock_run_agent.return_value = {
        "answer": "NVIDIA revenue was $18.1B last quarter.",
        "tool_calls": [],
    }

    response = await client.post(
        "/api/chat",
        json={"message": "What was NVIDIA's revenue?", "stream": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert "NVIDIA" in data["answer"]
    assert "session_id" in data
    assert data["total_latency_ms"] >= 0


@pytest.mark.asyncio
@patch("app.api.routes.chat.assemble_memory_layers", new_callable=AsyncMock)
@patch("app.api.routes.chat.run_agent", new_callable=AsyncMock)
async def test_chat_agent_error(mock_run_agent, mock_assemble, client):
    """Server returns 500 when agent raises."""
    mock_assemble.return_value = _empty_layers()
    mock_run_agent.side_effect = RuntimeError("LLM connection refused")

    response = await client.post(
        "/api/chat",
        json={"message": "test query"},
    )
    assert response.status_code == 500


# =============================================================================
# SSE Stream endpoint
# =============================================================================

@pytest.mark.asyncio
@patch("app.api.routes.chat.assemble_memory_layers", new_callable=AsyncMock)
@patch("app.api.routes.chat.run_agent_stream")
async def test_chat_stream_format(mock_stream, mock_assemble, client):
    """SSE stream produces plan, step_update, summarizing, token, and done events."""
    mock_assemble.return_value = _empty_layers()

    async def fake_stream(message, session_id, memory_context="", **kwargs):
        yield {"type": "plan", "data": {"steps": [{"id": "s1", "description": "Search", "tool": "retriever"}]}}
        yield {"type": "step_update", "data": {"step_id": "s1", "status": "running"}}
        yield {"type": "step_update", "data": {"step_id": "s1", "status": "done", "result": "found data", "latency_ms": 100.0}}
        yield {"type": "summarizing", "data": {}}
        yield {"type": "token", "data": {"content": "Hello"}}
        yield {"type": "token", "data": {"content": " world"}}

    mock_stream.return_value = fake_stream("", "")

    response = await client.post(
        "/api/chat/stream",
        json={"message": "test query"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    body = response.text
    assert "event: plan" in body
    assert "event: step_update" in body
    assert "event: summarizing" in body
    assert "event: token" in body
    assert "event: done" in body


@pytest.mark.asyncio
@patch("app.api.routes.chat.schedule_summarize_other_sessions", new_callable=AsyncMock)
@patch("app.api.routes.chat.append_assistant_turn", new_callable=AsyncMock)
@patch("app.api.routes.chat.append_user_turn", new_callable=AsyncMock)
@patch("app.api.routes.chat.assemble_memory_layers", new_callable=AsyncMock)
@patch("app.api.routes.chat.run_agent_stream")
async def test_chat_stream_persists_when_only_report_no_chat_tokens(
    mock_stream,
    mock_assemble,
    mock_append_user,
    mock_append_assistant,
    mock_sched_summ,
    client,
):
    """Regression: merged report alone must enqueue persist (refresh loads history/report)."""
    from app.main import app

    mock_assemble.return_value = _empty_layers()

    async def fake_stream(message, session_id, memory_context="", **kwargs):
        yield {"type": "report", "data": {"markdown": "# SNDK report body"}}

    mock_stream.return_value = fake_stream("", "")

    app.state.db_ready = True

    cid = "11111111-2222-4333-a444-aabbccddeeff"
    response = await client.post(
        "/api/chat/stream",
        json={
            "message": "SanDisk SNDK outlook",
            "profile_id": "prof-abcdef12",
            "conversation_id": cid,
            "stream": True,
            "auto_persist_turn": True,
        },
    )
    assert response.status_code == 200
    body = await response.aread()

    mock_append_user.assert_awaited_once()
    mock_append_assistant.assert_awaited_once()
    cargs, ckwargs = mock_append_assistant.await_args
    assert cargs[3] == ""  # assistant_text empty
    assert ckwargs.get("report_markdown") == "# SNDK report body"
    mock_sched_summ.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.api.routes.chat.schedule_summarize_other_sessions", new_callable=AsyncMock)
@patch("app.api.routes.chat.append_assistant_turn", new_callable=AsyncMock)
@patch("app.api.routes.chat.append_user_turn", new_callable=AsyncMock)
@patch("app.api.routes.chat.assemble_memory_layers", new_callable=AsyncMock)
@patch("app.api.routes.chat.run_agent_stream")
async def test_chat_stream_skips_auto_persist_by_default(
    mock_stream,
    mock_assemble,
    mock_append_user,
    mock_append_assistant,
    mock_sched_summ,
    client,
):
    """Default auto_persist_turn=false: streaming does not write turns to DB."""
    mock_assemble.return_value = _empty_layers()

    async def fake_stream(message, session_id, memory_context="", **kwargs):
        yield {"type": "report", "data": {"markdown": "# SNDK report"}}

    mock_stream.return_value = fake_stream("", "")

    app.state.db_ready = True

    cid = "11111111-2222-4333-a444-aabbccddeeff"
    response = await client.post(
        "/api/chat/stream",
        json={
            "message": "SanDisk SNDK outlook",
            "profile_id": "prof-abcdef12",
            "conversation_id": cid,
            "stream": True,
        },
    )
    assert response.status_code == 200
    await response.aread()

    mock_append_user.assert_not_awaited()
    mock_append_assistant.assert_not_awaited()
    mock_sched_summ.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.api.routes.conversations._db", MagicMock(return_value=True))
@patch(
    "app.api.routes.conversations.schedule_summarize_other_sessions",
    new_callable=AsyncMock,
)
@patch(
    "app.api.routes.conversations.persist_turn_via_save_button",
    new_callable=AsyncMock,
    return_value="NVDA",
)
async def test_commit_turn_endpoint(mock_persist, mock_sched, client):
    """Save button path enqueues commit-turn and returns derived title."""
    cid = "11111111-2222-4333-a444-aabbccddeeff"
    response = await client.post(
        f"/api/conversations/{cid}/commit-turn",
        json={
            "profile_id": "prof-abcdef12",
            "user_message": "NVDA outlook?",
            "assistant_message": "Summary here.",
            "report_markdown": "# NVDA\n\nDetails",
            "save_message_as_memory": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["conversation_title"] == "NVDA"
    mock_persist.assert_awaited_once()
