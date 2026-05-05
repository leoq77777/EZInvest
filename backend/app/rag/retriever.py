"""Hybrid retriever – dense (FAISS) + sparse (BM25) + dynamic (pgvector) with RRF fusion and Redis caching."""

import asyncio
import hashlib
import json
import logging
import pickle
from pathlib import Path

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)


def _rrf_fuse(
    *result_lists: list[dict],
    k: int = 60,
) -> list[dict]:
    """Reciprocal Rank Fusion to merge N ranked result lists.

    RRF(d) = Σ 1 / (k + rank(d)) across all result lists.

    Uses the text content as dedup key so that the same passage from
    different sources (e.g. FAISS and pgvector) is merged correctly.
    """
    scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    for result_list in result_lists:
        for rank_pos, doc in enumerate(result_list):
            # Use a content-based key for deduplication across sources
            dedup_key = doc.get("text", "")[:200]
            scores[dedup_key] = scores.get(dedup_key, 0) + 1.0 / (k + rank_pos + 1)
            if dedup_key not in doc_map:
                doc_map[dedup_key] = doc

    sorted_keys = sorted(scores.keys(), key=lambda d: scores[d], reverse=True)
    fused = []
    for key in sorted_keys:
        doc = doc_map[key].copy()
        doc["score"] = round(scores[key], 6)
        fused.append(doc)

    return fused


class HybridRetriever:
    """Combines FAISS dense search + BM25 sparse search + pgvector dynamic search with Redis caching."""

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
        if int(query_vec.shape[1]) != int(self._faiss_index.d):
            logger.warning(
                "Embedding dim %s != FAISS index dim %s; dense search skipped. "
                "Use EMBEDDING_MODEL that matches the index (bundled index uses "
                "BAAI/bge-large-en-v1.5, 1024-d) or rebuild data/indexes with your model.",
                query_vec.shape[1],
                self._faiss_index.d,
            )
            return []
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

    async def _dynamic_search(self, query: str, top_k: int) -> list[dict]:
        """Search the dynamic pgvector store for web-scraped content."""
        try:
            from app.rag.pgvector_store import get_dynamic_store
            store = get_dynamic_store()
            return await store.similarity_search(query, k=top_k)
        except Exception as e:
            logger.warning("Dynamic pgvector search failed (this is OK if DB is not running): %s", e)
            return []

    async def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """Execute hybrid retrieval across FAISS + BM25 + pgvector with caching, fusion, and reranking."""
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

        # Offload CPU/sync HF work so the asyncio loop can still run (SSE keepalive in /chat/stream).
        dense_results, sparse_results = await asyncio.gather(
            asyncio.to_thread(self._dense_search, query, fetch_k),
            asyncio.to_thread(self._sparse_search, query, fetch_k),
        )
        dynamic_results = []
        try:
            # Add a safety check or short timeout if possible, 
            # though similarity_search is already async
            dynamic_results = await self._dynamic_search(query, top_k=fetch_k)
        except Exception as e:
            logger.error(f"Dynamic search failed or timed out: {e}")
            dynamic_results = []

        all_empty = not dense_results and not sparse_results and not dynamic_results
        if all_empty:
            return []

        fused = _rrf_fuse(dense_results, sparse_results, dynamic_results)
        candidates = fused[: top_k * 3]

        # Optional cross-encoder (second HF model). Chat LLM API keys do not apply here.
        if (
            self._settings.enable_rag_reranker
            and len(candidates) >= 2
        ):
            try:
                from app.rag.reranker import rerank

                reranked = await asyncio.to_thread(
                    rerank, query, candidates, top_k
                )
            except Exception as e:
                logger.warning("Reranker failed, returning fused results: %s", e)
                reranked = candidates[:top_k]
        else:
            reranked = candidates[:top_k]

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
