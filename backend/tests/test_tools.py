"""Unit tests for all agent tools – external dependencies are fully mocked."""

import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
import pandas as pd
import numpy as np

from app.agent.tools.calculator import calculator_tool


# =============================================================================
# Calculator Tool (deterministic, no mocks needed)
# =============================================================================

class TestCalculatorTool:
    def test_pe_ratio(self):
        result = calculator_tool.invoke({"metric": "pe_ratio", "params": {"price": 130.0, "eps": 2.0}})
        data = json.loads(result)
        assert data["result"] == 65.0
        assert data["metric"] == "pe_ratio"

    def test_roe(self):
        result = calculator_tool.invoke({"metric": "roe", "params": {"net_income": 50_000, "equity": 200_000}})
        data = json.loads(result)
        assert data["result"] == 25.0

    def test_yoy_growth(self):
        result = calculator_tool.invoke({"metric": "yoy_growth", "params": {"current": 120, "previous": 100}})
        data = json.loads(result)
        assert data["result"] == 20.0

    def test_yoy_growth_negative(self):
        result = calculator_tool.invoke({"metric": "yoy_growth", "params": {"current": 80, "previous": 100}})
        data = json.loads(result)
        assert data["result"] == -20.0

    def test_sharpe_ratio(self):
        result = calculator_tool.invoke({
            "metric": "sharpe_ratio",
            "params": {"portfolio_return": 0.12, "risk_free_rate": 0.04, "std_dev": 0.15},
        })
        data = json.loads(result)
        assert abs(data["result"] - 0.5333) < 0.001

    def test_debt_to_equity(self):
        result = calculator_tool.invoke({"metric": "debt_to_equity", "params": {"total_debt": 500, "total_equity": 1000}})
        data = json.loads(result)
        assert data["result"] == 0.5

    def test_profit_margin(self):
        result = calculator_tool.invoke({"metric": "profit_margin", "params": {"net_income": 30, "revenue": 100}})
        data = json.loads(result)
        assert data["result"] == 30.0

    def test_unknown_metric(self):
        result = calculator_tool.invoke({"metric": "nonexistent", "params": {}})
        assert "Unknown metric" in result

    def test_missing_params(self):
        result = calculator_tool.invoke({"metric": "pe_ratio", "params": {"price": 100}})
        assert "Missing parameters" in result

    def test_division_by_zero(self):
        result = calculator_tool.invoke({"metric": "pe_ratio", "params": {"price": 100, "eps": 0}})
        assert "error" in result.lower()


# =============================================================================
# Market Data Tool (yfinance mocked)
# =============================================================================

class TestMarketDataTool:
    def _make_mock_hist(self):
        """Build a minimal DataFrame mimicking yfinance history output."""
        dates = pd.date_range("2025-01-01", periods=5, freq="D")
        return pd.DataFrame({
            "Open": [140.0, 141.0, 142.0, 143.0, 145.0],
            "High": [141.0, 142.0, 143.5, 144.0, 146.0],
            "Low": [139.0, 140.0, 141.0, 142.0, 144.0],
            "Close": [140.5, 141.5, 142.5, 143.5, 145.5],
            "Volume": [1_000_000] * 5,
        }, index=dates)

    @patch("app.agent.tools.market_data.yfinance" if False else "yfinance.Ticker")
    def test_successful_fetch(self, mock_ticker_cls):
        from app.agent.tools.market_data import market_data_tool

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = self._make_mock_hist()
        mock_ticker.info = {"marketCap": 3_000_000_000, "trailingPE": 35.5}
        mock_ticker_cls.return_value = mock_ticker

        result = market_data_tool.invoke({"ticker": "NVDA", "period": "5d"})
        data = json.loads(result)

        assert data["ticker"] == "NVDA"
        assert data["current_price"] == 145.5
        assert data["volume"] == 1_000_000
        assert "period_change_pct" in data
        assert data["marketCap"] == 3_000_000_000

    @patch("yfinance.Ticker")
    def test_empty_history_returns_error(self, mock_ticker_cls):
        from app.agent.tools.market_data import market_data_tool

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_cls.return_value = mock_ticker

        result = market_data_tool.invoke({"ticker": "INVALID"})
        data = json.loads(result)
        assert "error" in data

    @patch("yfinance.Ticker")
    def test_network_failure_returns_error(self, mock_ticker_cls):
        from app.agent.tools.market_data import market_data_tool

        mock_ticker_cls.side_effect = Exception("Network timeout")

        result = market_data_tool.invoke({"ticker": "AAPL"})
        data = json.loads(result)
        assert "error" in data


class TestToolCallNormalization:
    def test_calculator_expression_is_converted_to_pe_ratio(self):
        from app.agent.entity_resolution import normalize_tool_call

        tool, args, note = normalize_tool_call(
            "calculate 420 / 12.5",
            "calculator",
            {"expression": "420/12.5"},
        )

        assert tool == "calculator"
        assert args == {"metric": "pe_ratio", "params": {"price": 420.0, "eps": 12.5}}
        assert note and "calculator expression" in note

    def test_sentiment_texts_are_merged(self):
        from app.agent.entity_resolution import normalize_tool_call

        tool, args, note = normalize_tool_call(
            "sentiment",
            "sentiment_analyzer",
            {"texts": ["Revenue grew", "Margins fell"]},
        )

        assert tool == "sentiment_analyzer"
        assert args["text"] == "Revenue grew\nMargins fell"
        assert note and "merged texts" in note

    def test_roe_expression_is_converted_to_roe_params(self):
        from app.agent.entity_resolution import normalize_tool_call

        tool, args, note = normalize_tool_call(
            "请计算净利润 120、股东权益 800 时的 ROE",
            "calculator",
            {"expression": "120 / 800 * 100"},
        )

        assert tool == "calculator"
        assert args == {"metric": "roe", "params": {"net_income": 120.0, "equity": 800.0}}
        assert note and "roe params" in note

    def test_yoy_expression_is_converted_to_yoy_growth_params(self):
        from app.agent.entity_resolution import normalize_tool_call

        tool, args, note = normalize_tool_call(
            "请计算收入从 100 增长到 128 的同比增速",
            "calculator",
            {"expression": "(128 - 100) / 100 * 100"},
        )

        assert tool == "calculator"
        assert args == {"metric": "yoy_growth", "params": {"current": 128.0, "previous": 100.0}}
        assert note and "yoy_growth params" in note


# =============================================================================
# Sentiment Tool (FinBERT model mocked)
# =============================================================================

class TestSentimentTool:
    @pytest.mark.asyncio
    async def test_sentiment_positive(self):
        import app.agent.tools.sentiment as sentiment_mod

        sentiment_mod._sentiment_model = None
        from app.agent.tools.sentiment import sentiment_tool

        mock_model = MagicMock()
        mock_model.predict.return_value = {
            "label": "positive",
            "score": 0.92,
            "scores": {"positive": 0.92, "negative": 0.03, "neutral": 0.05},
        }

        async def fake_to_thread(fn, /, *args, **kwargs):
            if args:
                return mock_model.predict(*args)
            return mock_model

        with patch.object(
            sentiment_mod.asyncio,
            "to_thread",
            new=AsyncMock(side_effect=fake_to_thread),
        ):
            result = await sentiment_tool.ainvoke(
                {"text": "Revenue exceeded expectations by 20%"}
            )

        assert "positive" in result.lower()
        assert "0.92" in result
        mock_model.predict.assert_called_once()

    @pytest.mark.asyncio
    async def test_sentiment_negative(self):
        import app.agent.tools.sentiment as sentiment_mod

        sentiment_mod._sentiment_model = None
        from app.agent.tools.sentiment import sentiment_tool

        mock_model = MagicMock()
        mock_model.predict.return_value = {
            "label": "negative",
            "score": 0.85,
            "scores": {"positive": 0.05, "negative": 0.85, "neutral": 0.10},
        }

        async def fake_to_thread(fn, /, *args, **kwargs):
            if args:
                return mock_model.predict(*args)
            return mock_model

        with patch.object(
            sentiment_mod.asyncio,
            "to_thread",
            new=AsyncMock(side_effect=fake_to_thread),
        ):
            result = await sentiment_tool.ainvoke(
                {"text": "The company reported significant losses this quarter"}
            )

        assert "negative" in result.lower()

    @pytest.mark.asyncio
    async def test_sentiment_model_error(self):
        import app.agent.tools.sentiment as sentiment_mod

        sentiment_mod._sentiment_model = None
        from app.agent.tools.sentiment import sentiment_tool

        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("Model OOM")

        async def fake_to_thread(fn, /, *args, **kwargs):
            if args:
                return mock_model.predict(*args)
            return mock_model

        with patch.object(
            sentiment_mod.asyncio,
            "to_thread",
            new=AsyncMock(side_effect=fake_to_thread),
        ):
            result = await sentiment_tool.ainvoke({"text": "test"})
        assert "error" in result.lower()


# =============================================================================
# Retriever Tool (RAG pipeline mocked)
# =============================================================================

class TestRetrieverTool:
    @patch("app.agent.tools.retriever._get_rag_pipeline")
    @pytest.mark.asyncio
    async def test_retriever_returns_results(self, mock_get_pipeline):
        from app.agent.tools.retriever import retriever_tool

        mock_pipeline = MagicMock()
        mock_pipeline.retrieve = AsyncMock(
            return_value=[
                {"text": "NVIDIA Q3 revenue was $18.1B", "source": "10-Q", "score": 0.95},
                {"text": "Data center segment grew 279%", "source": "earnings", "score": 0.88},
            ],
        )
        mock_get_pipeline.return_value = mock_pipeline

        result = await retriever_tool.ainvoke({"query": "NVIDIA revenue", "top_k": 2})

        assert "NVIDIA Q3 revenue" in result
        assert "10-Q" in result
        assert "[1]" in result and "[2]" in result

    @patch("app.agent.tools.retriever._get_rag_pipeline")
    @pytest.mark.asyncio
    async def test_retriever_no_results(self, mock_get_pipeline):
        from app.agent.tools.retriever import retriever_tool

        mock_pipeline = MagicMock()
        mock_pipeline.retrieve = AsyncMock(return_value=[])
        mock_get_pipeline.return_value = mock_pipeline

        result = await retriever_tool.ainvoke({"query": "nonexistent topic"})
        assert "No relevant documents" in result

    @patch("app.agent.tools.retriever._get_rag_pipeline")
    @pytest.mark.asyncio
    async def test_retriever_sandisk_curated_fallback(self, mock_get_pipeline):
        from app.agent.tools.retriever import retriever_tool

        mock_pipeline = MagicMock()
        mock_pipeline.retrieve = AsyncMock(return_value=[])
        mock_get_pipeline.return_value = mock_pipeline

        result = await retriever_tool.ainvoke({"query": "SanDisk stock price"})
        assert "SNDK" in result
        assert "WDC" in result
        assert "corporate-actions override" in result


# =============================================================================
# RRF Fusion (pure logic, no mocks needed)
# =============================================================================

class TestRRFFusion:
    """RRF fusion is pure logic — import only the function, not the heavy module."""

    def _get_rrf_fuse(self):
        """Import _rrf_fuse without triggering faiss/sentence_transformers."""
        import importlib
        import sys
        mod = importlib.import_module("app.rag.retriever")
        return mod._rrf_fuse

    def test_rrf_basic(self):
        _rrf_fuse = self._get_rrf_fuse()
        dense = [
            {"doc_id": 1, "score": 0.9, "text": "doc1", "source": "a"},
            {"doc_id": 2, "score": 0.7, "text": "doc2", "source": "b"},
        ]
        sparse = [
            {"doc_id": 2, "score": 5.0, "text": "doc2", "source": "b"},
            {"doc_id": 3, "score": 3.0, "text": "doc3", "source": "c"},
        ]
        fused = _rrf_fuse(dense, sparse)
        assert fused[0]["doc_id"] == 2
        assert len(fused) == 3

    def test_rrf_empty(self):
        _rrf_fuse = self._get_rrf_fuse()
        assert _rrf_fuse([], []) == []

    def test_rrf_no_overlap(self):
        _rrf_fuse = self._get_rrf_fuse()
        dense = [{"doc_id": 1, "score": 0.9, "text": "a", "source": "x"}]
        sparse = [{"doc_id": 2, "score": 3.0, "text": "b", "source": "y"}]
        fused = _rrf_fuse(dense, sparse)
        assert len(fused) == 2
        assert fused[0]["score"] == fused[1]["score"]
