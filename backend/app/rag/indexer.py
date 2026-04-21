"""FAISS index builder – HNSW for online serving, IVF_PQ for large-scale offline."""

import logging
import pickle
from pathlib import Path

import faiss
import numpy as np

from app.rag.embedder import embed_texts

logger = logging.getLogger(__name__)


class FAISSIndexBuilder:
    """Builds and saves FAISS indexes from document chunks."""

    def __init__(self, embedding_dim: int = 1024):
        self.embedding_dim = embedding_dim

    def build_hnsw(
        self,
        texts: list[str],
        metadata: list[dict],
        save_path: str,
        M: int = 32,
        ef_construction: int = 200,
    ) -> None:
        """Build HNSW index for fast online retrieval.

        HNSW provides excellent recall and low latency for moderate-scale
        datasets (up to ~1M vectors).
        """
        logger.info("Embedding %d texts...", len(texts))
        vectors = embed_texts(texts)

        index = faiss.IndexHNSWFlat(self.embedding_dim, M)
        index.hnsw.efConstruction = ef_construction
        index.hnsw.efSearch = 128
        index.add(vectors)

        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(path))

        meta_path = path.with_suffix(".meta.pkl")
        with open(meta_path, "wb") as f:
            pickle.dump({"texts": texts, "metadata": metadata}, f)

        logger.info(
            "HNSW index saved: %d vectors → %s", index.ntotal, save_path
        )

    def build_ivf_pq(
        self,
        texts: list[str],
        metadata: list[dict],
        save_path: str,
        nlist: int = 256,
        m_subquantizers: int = 64,
        nbits: int = 8,
    ) -> None:
        """Build IVF_PQ index for memory-efficient large-scale retrieval.

        Suitable for datasets exceeding 1M vectors where memory is constrained.
        Requires a training step on representative vectors.
        """
        logger.info("Embedding %d texts for IVF_PQ...", len(texts))
        vectors = embed_texts(texts)

        quantizer = faiss.IndexFlatIP(self.embedding_dim)
        index = faiss.IndexIVFPQ(
            quantizer, self.embedding_dim, nlist, m_subquantizers, nbits
        )

        logger.info("Training IVF_PQ index...")
        index.train(vectors)
        index.add(vectors)
        index.nprobe = 16

        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(path))

        meta_path = path.with_suffix(".meta.pkl")
        with open(meta_path, "wb") as f:
            pickle.dump({"texts": texts, "metadata": metadata}, f)

        logger.info(
            "IVF_PQ index saved: %d vectors → %s", index.ntotal, save_path
        )
