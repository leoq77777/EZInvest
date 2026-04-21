"""Integration tests for the RAG pipeline components."""

import pytest
from unittest.mock import patch, MagicMock

from app.schemas.chat import ChatRequest


class TestChatSchema:
    def test_valid_request(self):
        req = ChatRequest(message="test query")
        assert req.message == "test query"
        assert req.stream is True
        assert req.session_id

    def test_empty_message_rejected(self):
        with pytest.raises(Exception):
            ChatRequest(message="")

    def test_custom_session(self):
        req = ChatRequest(message="test", session_id="my-session")
        assert req.session_id == "my-session"
