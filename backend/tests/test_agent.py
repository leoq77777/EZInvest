"""Agent graph tests – LLM is mocked via get_llm(), no server needed."""

import json
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from langchain_core.messages import AIMessage


# =============================================================================
# Tool execution
# =============================================================================

class TestExecuteTool:
    @pytest.mark.asyncio
    async def test_executes_calculator_tool(self):
        from app.agent.graph import execute_tool

        result = await execute_tool(
            "calculator", {"metric": "pe_ratio", "params": {"price": 100, "eps": 2}}
        )
        assert "50" in result

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        from app.agent.graph import execute_tool

        result = await execute_tool("nonexistent", {})
        assert "not found" in result.lower()


# =============================================================================
# ReAct stream (mocked LLM)
# =============================================================================

class TestRunAgentStream:
    @pytest.mark.asyncio
    @patch("app.agent.graph.get_llm")
    async def test_finish_emits_thought_and_token(self, mock_get_llm):
        """finish branch produces a final token with summary text."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            side_effect=[
                AIMessage(
                    content=json.dumps(
                        {
                            "expanded_intent": "test",
                            "tickers": [],
                            "parallel_calls": [],
                        }
                    )
                ),
                AIMessage(
                    content=json.dumps(
                        {"type": "finish", "thought": "Research complete."}
                    )
                ),
                AIMessage(content="本轮已更新要点。"),
                AIMessage(content="## NVDA\n- 简要结论\n"),
            ]
        )
        mock_get_llm.return_value = mock_llm

        events = []
        from app.agent.graph import run_agent_stream

        async for event in run_agent_stream("test?", "sid", memory_context=""):
            events.append(event)

        types = [e["type"] for e in events]
        assert "thought" in types
        assert "token" in types
        token_text = "".join(
            e["data"]["content"] for e in events if e["type"] == "token"
        )
        assert "要点" in token_text or "更新" in token_text
        reports = [e for e in events if e["type"] == "report"]
        assert reports
        assert "NVDA" in reports[-1]["data"]["markdown"]

    @pytest.mark.asyncio
    @patch("app.agent.graph.execute_tool", new_callable=AsyncMock)
    @patch("app.agent.graph.get_llm")
    async def test_sandisk_grounding_forces_sndk(self, mock_get_llm, mock_execute_tool):
        """SanDisk requests must not let stale LLM planning fetch WDC as the price."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            side_effect=[
                AIMessage(
                    content=json.dumps(
                        {
                            "expanded_intent": "check SanDisk stock price",
                            "tickers": ["WDC"],
                            "parallel_calls": [
                                {
                                    "tool": "market_data",
                                    "tool_args": {"ticker": "WDC", "period": "1mo"},
                                }
                            ],
                        }
                    )
                ),
                AIMessage(content=json.dumps({"type": "finish", "thought": "ok"})),
                AIMessage(content="SanDisk 应使用 SNDK 查询。"),
                AIMessage(content="## SNDK\n- 使用 SNDK，不是 WDC。\n"),
            ]
        )
        mock_get_llm.return_value = mock_llm
        mock_execute_tool.return_value = '{"ticker":"SNDK","current_price":1}'

        from app.agent.graph import run_agent_stream

        events = []
        async for event in run_agent_stream("sandisk 的股价是多少？", "sid"):
            events.append(event)

        assert mock_execute_tool.call_args_list
        assert mock_execute_tool.call_args_list[0].args[0] == "market_data"
        assert mock_execute_tool.call_args_list[0].args[1]["ticker"] == "SNDK"
        assert any(
            e["type"] == "thought" and "SanDisk→SNDK" in e["data"]["content"]
            for e in events
        )


class TestRunAgent:
    @pytest.mark.asyncio
    @patch("app.agent.graph.get_llm")
    async def test_returns_answer(self, mock_get_llm):
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            side_effect=[
                AIMessage(
                    content=json.dumps(
                        {
                            "expanded_intent": "x",
                            "tickers": [],
                            "parallel_calls": [],
                        }
                    )
                ),
                AIMessage(content=json.dumps({"type": "finish", "thought": "ok"})),
                AIMessage(content="Chat."),
                AIMessage(content="# R\nBody"),
            ]
        )
        mock_get_llm.return_value = mock_llm

        from app.agent.graph import run_agent

        result = await run_agent("q", "s1")
        assert "Chat" in result["answer"]
        assert result.get("report_markdown") and "Body" in result["report_markdown"]


# =============================================================================
# FinBERT model wrapper (mocking transformers)
# =============================================================================

torch = pytest.importorskip("torch", reason="torch not installed, skipping FinBERT tests")


class TestFinBERTWrapper:
    @patch("app.models.finbert.AutoModelForSequenceClassification")
    @patch("app.models.finbert.AutoTokenizer")
    @patch("app.models.finbert.torch")
    def test_predict_returns_correct_format(self, mock_torch, mock_tokenizer_cls, mock_model_cls):
        """FinBERT wrapper correctly processes model outputs into labeled predictions."""
        import torch
        mock_torch.device.return_value = torch.device("cpu")
        mock_torch.cuda.is_available.return_value = False
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        fake_logits = torch.tensor([[2.5, -1.0, 0.3]])
        mock_outputs = MagicMock()
        mock_outputs.logits = fake_logits

        mock_model = MagicMock()
        mock_model.return_value = mock_outputs
        mock_model_cls.from_pretrained.return_value = mock_model

        inner = MagicMock()
        inner.to.return_value = {
            "input_ids": torch.tensor([[1, 2, 3]]),
            "attention_mask": torch.tensor([[1, 1, 1]]),
        }
        mock_tokenizer = MagicMock(return_value=inner)
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_torch.softmax = torch.softmax
        mock_torch.argmax = torch.argmax

        # Do not reload finbert here: reload drops @patch bindings and triggers real HF hub.
        import app.models.finbert as finbert_module

        model = finbert_module.FinBERTSentiment()
        result = model.predict("Revenue exceeded expectations")

        assert result["label"] in ("positive", "negative", "neutral")
        assert 0 <= result["score"] <= 1
        assert set(result["scores"].keys()) == {"positive", "negative", "neutral"}
        assert abs(sum(result["scores"].values()) - 1.0) < 0.01
