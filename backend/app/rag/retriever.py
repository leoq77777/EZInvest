"""Hybrid retriever – dense (FAISS) + sparse (BM25) with RRF fusion and Redis caching."""

import hashlib
import json
import logging
import pickle
from pathlib import Path

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)


def _rrf_fuse(
    dense_results: list[dict],
    sparse_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """Reciprocal Rank Fusion to merge dense and sparse result lists.

    RRF(d) = Σ 1 / (k + rank(d)) across all result lists.
    """
    scores: dict[int, float] = {}
    doc_map: dict[int, dict] = {}

    for rank_pos, doc in enumerate(dense_results):
        doc_id = doc["doc_id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank_pos + 1)
        doc_map[doc_id] = doc

    for rank_pos, doc in enumerate(sparse_results):
        doc_id = doc["doc_id"]
        scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank_pos + 1)
        doc_map[doc_id] = doc

    sorted_ids = sorted(scores.keys(), key=lambda d: scores[d], reverse=True)
    fused = []
    for doc_id in sorted_ids:
        doc = doc_map[doc_id].copy()
        doc["score"] = round(scores[doc_id], 6)
        fused.append(doc)

    return fused


class HybridRetriever:
    """Combines FAISS dense search + BM25 sparse search with Redis caching."""

    def __init__(self):
        settings = get_settings()
        self._faiss_index = None
        self._faiss_meta = None
        self._bm25 = None
        self._bm25_corpus = None
        self._redis = None
        self._settings = settings

    def _load_faiss(self):
        if self._faiss_index is not None:
            return
        path = Path(self._settings.faiss_index_path)
        if not path.exists():
            logger.warning("FAISS index not found at %s", path)
            return
        import faiss
        self._faiss_index = faiss.read_index(str(path))
        meta_path = path.with_suffix(".meta.pkl")
        if meta_path.exists():
            with open(meta_path, "rb") as f:
                self._faiss_meta = pickle.load(f)
        logger.info("FAISS index loaded: %d vectors", self._faiss_index.ntotal)

    def _load_bm25(self):
        if self._bm25 is not None:
            return
        path = Path(self._settings.bm25_index_path)
        if not path.exists():
            logger.warning("BM25 index not found at %s", path)
            return
        with open(path, "rb") as f:
            data = pickle.load(f)
        self._bm25 = data["bm25"]
        self._bm25_corpus = data["corpus"]
        logger.info("BM25 index loaded: %d documents", len(self._bm25_corpus))

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(
                    self._settings.redis_url, decode_responses=True
                )
            except Exception as e:
                logger.warning("Redis unavailable, caching disabled: %s", e)
        return self._redis

    def _cache_key(self, query: str, top_k: int) -> str:
        h = hashlib.md5(f"{query}:{top_k}".encode()).hexdigest()
        return f"rag:cache:{h}"

    def _dense_search(self, query: str, top_k: int) -> list[dict]:
        self._load_faiss()
        if self._faiss_index is None:
            return []

        from app.rag.embedder import embed_query
        query_vec = embed_query(query)
        scores, indices = self._faiss_index.search(query_vec, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            doc = {
                "doc_id": int(idx),
                "score": float(score),
                "text": self._faiss_meta["texts"][idx] if self._faiss_meta else "",
                "source": (
                    self._faiss_meta["metadata"][idx].get("source", "")
                    if self._faiss_meta
                    else ""
                ),
            }
            results.append(doc)
        return results

    def _sparse_search(self, query: str, top_k: int) -> list[dict]:
        self._load_bm25()
        if self._bm25 is None:
            return []

        tokens = query.lower().split()
        scores = self._bm25.get_scores(tokens)
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] <= 0:
                continue
            corpus_entry = self._bm25_corpus[idx]
            doc = {
                "doc_id": int(idx),
                "score": float(scores[idx]),
                "text": corpus_entry["text"],
                "source": corpus_entry.get("source", ""),
            }
            results.append(doc)
        return results

    async def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """Execute hybrid retrieval with caching, fusion, and reranking."""
        redis = await self._get_redis()
        cache_key = self._cache_key(query, top_k)

        if redis:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    logger.debug("Cache hit for query: %s", query[:50])
                    return json.loads(cached)
            except Exception:
                pass

        fetch_k = top_k * 4

        dense_results = self._dense_search(query, fetch_k)
        sparse_results = self._sparse_search(query, fetch_k)

        if not dense_results and not sparse_results:
            return []

        fused = _rrf_fuse(dense_results, sparse_results)
        candidates = fused[: top_k * 3]

        from app.rag.reranker import rerank
        reranked = rerank(query, candidates, top_k=top_k)

        if redis:
            try:
                await redis.setex(
                    cache_key,
                    self._settings.redis_cache_ttl,
                    json.dumps(reranked, ensure_ascii=False),
                )
            except Exception:
                pass

        return reranked
