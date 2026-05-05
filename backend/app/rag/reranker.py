"""Cross-encoder reranker for improving retrieval precision."""

import logging
import threading

logger = logging.getLogger(__name__)

_reranker = None
_reranker_lock = threading.Lock()


def _get_reranker():
    global _reranker
    if _reranker is not None:
        return _reranker
    with _reranker_lock:
        if _reranker is None:
            from sentence_transformers import CrossEncoder
            from app.config import get_settings

            settings = get_settings()
            logger.info("Loading reranker model: %s", settings.reranker_model)
            _reranker = CrossEncoder(settings.reranker_model, max_length=512)
    return _reranker


def rerank(query: str, documents: list[dict], top_k: int = 5) -> list[dict]:
    """Rerank documents using a cross-encoder model.

    Args:
        query: The user query.
        documents: List of dicts with at least a "text" field.
        top_k: Number of top documents to return.

    Returns:
        Top-k documents sorted by cross-encoder score, each with an
        added "rerank_score" field.
    """
    if not documents:
        return []

    reranker = _get_reranker()
    pairs = [(query, doc["text"]) for doc in documents]
    scores = reranker.predict(pairs)

    for doc, score in zip(documents, scores):
        doc["rerank_score"] = float(score)

    ranked = sorted(documents, key=lambda d: d["rerank_score"], reverse=True)
    return ranked[:top_k]
