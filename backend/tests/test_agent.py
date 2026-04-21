"""Agent pipeline tests – LLM and tools are mocked, no server needed."""

import json
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from langchain_core.messages import AIMessage


# =============================================================================
# Plan parser (pure logic, no LLM needed)
# =============================================================================

class TestParsePlan:
    def test_parses_valid_json_array(self):
        from app.agent.graph import _parse_plan
        raw = '[{"id":"s1","description":"fetch data","tool":"market_data","tool_args":{"ticker":"NVDA"}}]'
        plan = _parse_plan(raw)
        assert len(plan) == 1
        assert plan[0]["tool"] == "market_data"

    def test_extracts_json_from_markdown_block(self):
        from app.agent.graph import _parse_plan
        raw = '```json\n[{"id":"s1","description":"search","tool":"retriever","tool_args":{"query":"q"}}]\n```'
        plan = _parse_plan(raw)
        assert len(plan) == 1
        assert plan[0]["tool"] == "retriever"

    def test_extracts_json_from_surrounding_text(self):
        from app.agent.graph import _parse_plan
        raw = 'Here is my plan:\n[{"id":"s1","description":"d","tool":"calculator","tool_args":{}}]\nDone.'
        plan = _parse_plan(raw)
        assert len(plan) == 1

    def test_returns_empty_for_invalid_json(self):
        from app.agent.graph import _parse_plan
        assert _parse_plan("this is not json") == []

    def test_returns_empty_for_non_array(self):
        from app.agent.graph import _parse_plan
        assert _parse_plan('{"key": "value"}') == []

    def test_handles_empty_string(self):
        from app.agent.graph import _parse_plan
        assert _parse_plan("") == []


# =============================================================================
# Tool execution helper
# =============================================================================

class TestExecuteTool:
    @pytest.mark.asyncio
    @patch("app.agent.graph.calculator_tool")
    async def test_executes_known_tool(self, mock_calc):
        from app.agent.graph import _execute_tool
        mock_calc.ainvoke = AsyncMock(return_value='{"result": 42}')

        result = await _execute_tool("calculator", {"metric": "pe_ratio", "params": {"price": 100, "eps": 2}})
        assert "42" in result
        mock_calc.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_error_for_unknown_tool(self):
        from app.agent.graph import _execute_tool
        result = await _execute_tool("nonexistent", {})
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    @patch("app.agent.graph.market_data_tool")
    async def test_handles_tool_exception(self, mock_md):
        from app.agent.graph import _execute_tool
        mock_md.ainvoke = AsyncMock(side_effect=RuntimeError("API down"))

        result = await _execute_tool("market_data", {"ticker": "AAPL"})
        assert "failed" in result or "error" in result.lower()


# =============================================================================
# Full pipeline (LLM mocked via get_llm)
# =============================================================================

class TestRunAgentStream:
    @pytest.mark.asyncio
    @patch("app.agent.graph.get_llm")
    @patch("app.agent.graph.market_data_tool")
    async def test_emits_plan_step_update_and_tokens(self, mock_md, mock_get_llm):
        """Full pipeline emits plan, step_update, summarizing, and token events."""
        plan_json = json.dumps([
            {"id": "s1", "description": "Get AAPL price", "tool": "market_data", "tool_args": {"ticker": "AAPL"}}
        ])

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=plan_json))

        async def fake_stream(messages):
            for word in ["Buy ", "AAPL"]:
                chunk = MagicMock()
                chunk.content = word
                yield chunk

        mock_llm.astream = MagicMock(side_effect=fake_stream)
        mock_get_llm.return_value = mock_llm

        mock_md.ainvoke = AsyncMock(return_value='{"ticker":"AAPL","current_price":185}')

        events = []
        from app.agent.graph import run_agent_stream
        async for event in run_agent_stream("What is AAPL price?", "test-session"):
            events.append(event)

        types = [e["type"] for e in events]
        assert "plan" in types
        assert "step_update" in types
        assert "summarizing" in types
        assert "token" in types

        plan_event = next(e for e in events if e["type"] == "plan")
        assert len(plan_event["data"]["steps"]) == 1
        assert plan_event["data"]["steps"][0]["tool"] == "market_data"

        step_updates = [e for e in events if e["type"] == "step_update"]
        assert any(s["data"]["status"] == "running" for s in step_updates)
        assert any(s["data"]["status"] == "done" for s in step_updates)

    @pytest.mark.asyncio
    @patch("app.agent.graph.get_llm")
    @patch("app.agent.graph.retriever_tool")
    async def test_fallback_when_plan_parse_fails(self, mock_ret, mock_get_llm):
        """Falls back to a single retriever step when LLM output is not valid JSON."""
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="I cannot plan this"))

        async def fake_stream(messages):
            chunk = MagicMock()
            chunk.content = "Report"
            yield chunk

        mock_llm.astream = MagicMock(side_effect=fake_stream)
        mock_get_llm.return_value = mock_llm

        mock_ret.ainvoke = AsyncMock(return_value="No relevant documents found.")

        events = []
        from app.agent.graph import run_agent_stream
        async for event in run_agent_stream("test question", "s1"):
            events.append(event)

        plan_event = next(e for e in events if e["type"] == "plan")
        assert len(plan_event["data"]["steps"]) == 1
        assert plan_event["data"]["steps"][0]["tool"] == "retriever"


class TestRunAgent:
    @pytest.mark.asyncio
    @patch("app.agent.graph.get_llm")
    @patch("app.agent.graph.calculator_tool")
    async def test_returns_answer_and_tool_calls(self, mock_calc, mock_get_llm):
        plan_json = json.dumps([
            {"id": "s1", "description": "compute PE", "tool": "calculator",
             "tool_args": {"metric": "pe_ratio", "params": {"price": 100, "eps": 5}}}
        ])

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=plan_json))

        async def fake_stream(messages):
            chunk = MagicMock()
            chunk.content = "PE is 20"
            yield chunk

        mock_llm.astream = MagicMock(side_effect=fake_stream)
        mock_get_llm.return_value = mock_llm

        mock_calc.ainvoke = AsyncMock(return_value='{"metric":"pe_ratio","result":20}')

        from app.agent.graph import run_agent
        result = await run_agent("compute PE", "s1")
        assert "PE is 20" in result["answer"]
        assert len(result["tool_calls"]) == 1


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

        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {"input_ids": torch.tensor([[1, 2, 3]]), "attention_mask": torch.tensor([[1, 1, 1]])}
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_torch.softmax = torch.softmax
        mock_torch.argmax = torch.argmax

        from importlib import reload
        import app.models.finbert as finbert_module
        reload(finbert_module)

        model = finbert_module.FinBERTSentiment()
        result = model.predict("Revenue exceeded expectations")

        assert result["label"] in ("positive", "negative", "neutral")
        assert 0 <= result["score"] <= 1
        assert set(result["scores"].keys()) == {"positive", "negative", "neutral"}
        assert abs(sum(result["scores"].values()) - 1.0) < 0.01
