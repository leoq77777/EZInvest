"""Tests for entity resolution and conversation title derivation."""

from app.agent.entity_resolution import derive_conversation_title


def test_title_from_curated_entity_sandisk() -> None:
    t = derive_conversation_title("SanDisk SNDK valuation")
    assert "SanDisk" in t
    assert "SNDK" in t


def test_title_from_dollar_ticker() -> None:
    assert derive_conversation_title("How is $NVDA doing vs peers?") == "NVDA"


def test_title_from_parentheses_ticker() -> None:
    assert derive_conversation_title("苹果（AAPL）业绩") == "AAPL"


def test_title_from_six_digit_code() -> None:
    assert derive_conversation_title("分析 600519 的基本面") == "600519"


def test_title_isolated_caps_ticker() -> None:
    assert derive_conversation_title("Thoughts on TSLA for next quarter") == "TSLA"


def test_title_fallback_truncates_long_text() -> None:
    raw = "x" * 200
    out = derive_conversation_title(raw, max_len=40)
    assert len(out) <= 40
