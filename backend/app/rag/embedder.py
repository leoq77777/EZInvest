"""Embedding generation using sentence-transformers (BGE-large)."""

import logging
from functools import lru_cache

import numpy as np

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        from app.config import get_settings

        settings = get_settings()
        logger.info("Loading embedding model: %s", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_texts(texts: list[str], batch_size: int = 64) -> np.ndarray:
    """Encode a list of texts into dense vectors.

    Returns:
        numpy array of shape (len(texts), embedding_dim)
    """
    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=len(texts) > 100,
        normalize_embeddings=True,
    )
    return np.array(embeddings, dtype=np.float32)


def embed_query(query: str) -> np.ndarray:
    """Encode a single query into a dense vector."""
    model = _get_model()
    embedding = model.encode(
        query,
        normalize_embeddings=True,
    )
    return np.array(embedding, dtype=np.float32).reshape(1, -1)
