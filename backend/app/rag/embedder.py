"""Embedding generation via sentence-transformers (local HF weights).

Separate from the chat LLM (OpenAI/DeepSeek/Ollama): those API keys are not used here.
Weights download once into HF cache (HF_HOME or ~/.cache/huggingface) then load locally.
"""

import logging
import threading

import numpy as np

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
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
