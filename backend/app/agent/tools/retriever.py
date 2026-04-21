"""RAG retrieval tool – hybrid dense (FAISS) + sparse (BM25) search with Redis caching."""

import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_rag_pipeline = None


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

    if not results:
        return "No relevant documents found for the given query."

    formatted = []
    for i, doc in enumerate(results, 1):
        source = doc.get("source", "unknown")
        text = doc.get("text", "")
        score = doc.get("score", 0.0)
        formatted.append(f"[{i}] (score={score:.3f}, source={source})\n{text}")

    return "\n\n".join(formatted)
