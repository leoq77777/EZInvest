"""Deterministic financial entity resolution and query grounding helpers."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


SANDISK_FACT = {
    "entity": "SanDisk",
    "ticker": "SNDK",
    "former_parent_ticker": "WDC",
    "status": "independently listed",
    "valid_from": "2025-02",
    "summary": (
        "SanDisk is treated as an independently listed company with ticker SNDK "
        "after its 2025 separation from Western Digital (WDC). Do not answer "
        "SanDisk price questions with WDC market data unless explicitly comparing "
        "the former parent."
    ),
    "source": "EZInvest curated corporate-actions override",
}


def mentions_sandisk(text: str) -> bool:
    """Return True when text likely refers to SanDisk."""
    return bool(re.search(r"\bsandisk\b|\bSNDK\b|闪迪", text or "", re.I))


def resolve_entities(text: str) -> List[dict[str, str]]:
    """Curated entity resolver for high-impact corporate-action edge cases."""
    if not mentions_sandisk(text):
        return []
    return [SANDISK_FACT.copy()]


def entity_grounding_observation(text: str) -> Optional[dict[str, Any]]:
    """Observation injected before LLM planning so stale model memory is overridden."""
    facts = resolve_entities(text)
    if not facts:
        return None
    return {
        "phase": "entity_resolution",
        "tool": "entity_resolver",
        "observation": json.dumps({"resolved_entities": facts}, ensure_ascii=False),
    }


def _sandisk_query_suffix() -> str:
    return " SanDisk SNDK independent listed stock ticker 2025 spinoff Western Digital WDC"


def normalize_tool_call(
    user_message: str,
    tool_name: str,
    tool_args: Dict[str, Any],
) -> Tuple[str, Dict[str, Any], Optional[str]]:
    """
    Enforce resolved entities before tools run.

    Returns (tool_name, normalized_args, note). The note should be added as an
    observation/thought so reports can explain that a stale ticker was corrected.
    """
    args = dict(tool_args or {})
    if not mentions_sandisk(user_message):
        return tool_name, args, None

    note: Optional[str] = None
    if tool_name == "market_data":
        ticker = str(args.get("ticker", "")).upper()
        if ticker in {"", "WDC", "WESTERN DIGITAL", "SANDISK"}:
            args["ticker"] = "SNDK"
            note = "Entity guard: SanDisk price request normalized to ticker SNDK, not WDC."

    elif tool_name in {"retriever", "web_scraper"}:
        # Models sometimes emit `url` instead of `query`; LangChain tool schema expects `query`.
        if not str(args.get("query", "")).strip() and args.get("url"):
            args["query"] = str(args.get("url", "")).strip()
        query = str(args.get("query", ""))
        suffix = _sandisk_query_suffix()
        if "SNDK" not in query.upper() or "WESTERN DIGITAL" not in query.upper():
            args["query"] = (query + suffix).strip()
            note = "Entity guard: expanded SanDisk query with SNDK and WDC spinoff terms."

    return tool_name, args, note


# Common English words matching [A-Z]{3,5} — avoid naming sessions after them.
_TICKER_STOP_WORDS = frozenset(
    {
        "THE",
        "AND",
        "FOR",
        "ARE",
        "BUT",
        "NOT",
        "YOU",
        "ALL",
        "CAN",
        "OUR",
        "OUT",
        "DAY",
        "GET",
        "HAS",
        "HOW",
        "ITS",
        "LET",
        "NEW",
        "NOW",
        "SEE",
        "WHO",
        "ANY",
        "MAY",
        "TRY",
        "THAN",
        "USD",
        "CNY",
        "HKD",
        "ETF",
        "IPO",
        "EPS",
        "PE",
        "YTD",
        "ATH",
        "CEO",
        "CFO",
        "GDP",
        "CPI",
        "SEC",
        "IRS",
        "IRA",
        "LLC",
        "INC",
        "USA",
        "NYSE",
        "NASDAQ",
        "FROM",
        "WITH",
        "THAT",
        "THIS",
        "WHAT",
        "WHEN",
        "HAVE",
        "BEEN",
        "WELL",
        "WILL",
        "YOUR",
        "HELP",
        "MORE",
        "SOME",
        "THAN",
        "VERY",
        "JUST",
        "ONLY",
        "LIKE",
        "INTO",
        "OVER",
        "AFTER",
        "ALSO",
    }
)


def derive_conversation_title(user_text: str, max_len: int = 80) -> str:
    """
    Name a conversation for a single-instrument-focused session.

    Uses curated entity resolver first ($ / curated facts), then heuristics
    (¥/US ticker patterns, mainland 6‑digit codes, isolated uppercase symbols).
    Falls back to a short excerpt of the user message when nothing matches.
    """
    text = (user_text or "").strip()
    if not text:
        return "未命名标的"

    resolved = resolve_entities(text)
    if resolved:
        f = resolved[0]
        entity = (f.get("entity") or "").strip() or f.get("ticker", "")
        tick = str(f.get("ticker") or "").strip().upper()
        if entity and tick:
            name = f"{entity} ({tick})"
        elif tick:
            name = tick
        else:
            name = entity or "标的"
        return name if len(name) <= max_len else name[: max_len - 1] + "…"

    # Cash-tagged US-style ticker: $AAPL
    m = re.search(r"\$([A-Za-z]{1,8})\b", text)
    if m:
        return m.group(1).upper()[:max_len]

    # Markdown / prose: 「苹果 (AAPL)」、(AAPL)
    paren = re.search(r"[（(]\s*([A-Za-z]{1,8})\s*[）)]", text)
    if paren:
        return paren.group(1).upper()[:max_len]

    # Mainland A-share: 6-digit code
    dm = re.search(r"\b(\d{6})\b", text)
    if dm:
        return dm.group(1)[:max_len]

    # Isolated uppercase run (likely ticker), 3–5 chars
    for wm in re.finditer(r"(?<![A-Za-z_])([A-Z]{3,5})(?![A-Za-z_])", text.upper()):
        t = wm.group(1)
        if t not in _TICKER_STOP_WORDS:
            return t[:max_len]

    condensed = " ".join(text.split())
    if len(condensed) > max_len:
        return condensed[: max_len - 1] + "…"
    return condensed
