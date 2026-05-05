"""RAG retrieval tool – hybrid dense (FAISS) + sparse (BM25) search with Redis caching."""

import logging

from langchain_core.tools import tool
from app.agent.entity_resolution import SANDISK_FACT, mentions_sandisk

logger = logging.getLogger(__name__)

_rag_pipeline = None


def _curated_fallback(query: str) -> str:
    """High-confidence corporate-action facts not yet present in vector indexes."""
    if not mentions_sandisk(query):
        return ""
    fact = SANDISK_FACT
    return (
        "[curated] (score=1.000, source=EZInvest corporate-actions override)\n"
        f"Entity: {fact['entity']}\n"
        f"Current ticker: {fact['ticker']}\n"
        f"Status: {fact['status']} since {fact['valid_from']}\n"
        f"Former parent ticker: {fact['former_parent_ticker']}\n"
        f"Grounding: {fact['summary']}\n"
        "Use SNDK for SanDisk market-data requests; do not use WDC unless the "
        "user explicitly asks about Western Digital or a comparison with WDC."
    )


def _get_rag_pipeline():
    global _rag_pipeline
    if _rag_pipeline is None:
        from app.rag.retriever import HybridRetriever

        _rag_pipeline = HybridRetriever()
    return _rag_pipeline


@tool
async def retriever_tool(query: str, top_k: int = 5) -> str:
    """Search SEC filings, earnings call transcripts, and financial news.

    Use this tool when the user asks about a company's financials, recent
    earnings reports, or specific financial events. Returns relevant document
    excerpts ranked by relevance.

    Args:
        query: The search query describing what financial information to find.
        top_k: Number of results to return (default 5).
    """
    pipeline = _get_rag_pipeline()
    try:
        results = await pipeline.retrieve(query, top_k=top_k)
    except Exception as e:
        logger.error("Retrieval failed: %s", e)
        return f"Retrieval error: {e}"

    fallback = _curated_fallback(query)
    if not results:
        if fallback:
            return fallback
        return "No relevant documents found for the given query."

    formatted = []
    for i, doc in enumerate(results, 1):
        source = doc.get("source", "unknown")
        text = doc.get("text", "")
        score = doc.get("score", 0.0)
        formatted.append(f"[{i}] (score={score:.3f}, source={source})\n{text}")

    if fallback:
        formatted.insert(0, fallback)

    return "\n\n".join(formatted)
