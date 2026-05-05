import logging
from typing import List, Dict, Any
from urllib.parse import urlparse, urlunparse

from langchain_core.embeddings import Embeddings
from langchain_postgres import PGVector

from app.config import get_settings
from app.rag.embedder import embed_texts, embed_query

logger = logging.getLogger(__name__)

class BGEEmbeddings(Embeddings):
    """Wrapper for the local BGE model to match LangChain Embeddings interface."""
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # embed_texts returns shape (N, dim) as np.ndarray
        embeddings = embed_texts(texts)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        # embed_query returns shape (1, dim) as np.ndarray
        embedding = embed_query(text)
        return embedding[0].tolist()

class DynamicVectorStore:
    def __init__(self):
        settings = get_settings()
        # Convert postgresql+asyncpg:// to postgresql+psycopg:// for langchain-postgres
        parsed = urlparse(settings.database_url)
        new_scheme = parsed.scheme.replace("asyncpg", "psycopg")
        self.connection_string = urlunparse((new_scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        
        self.embeddings = BGEEmbeddings()
        self.collection_name = "dynamic_web_data"
        self._store = None

    def _get_store(self) -> PGVector:
        if self._store is None:
            self._store = PGVector(
                embeddings=self.embeddings,
                collection_name=self.collection_name,
                connection=self.connection_string,
                use_jsonb=True,
            )
        return self._store

    async def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]] = None):
        """Add texts with metadata to the pgvector store."""
        try:
            store = self._get_store()
            # PGVector's add_texts is synchronous or requires an async session. 
            # We will use the sync version but wrap it in an executor if needed, 
            # but langchain_postgres handles connection pooling.
            store.add_texts(texts=texts, metadatas=metadatas)
            logger.info(f"Successfully added {len(texts)} chunks to pgvector.")
        except Exception as e:
            logger.error(f"Failed to add texts to pgvector: {e}")

    async def similarity_search(self, query: str, k: int = 5) -> List[dict]:
        """Search the dynamic vector store."""
        try:
            store = self._get_store()
            docs = store.similarity_search_with_score(query, k=k)
            results = []
            for doc, score in docs:
                # PGVector returns L2 distance by default. Convert to similarity score if needed.
                # For consistency with existing retriever, we'll format similarly.
                results.append({
                    "doc_id": hash(doc.page_content), # Fake doc_id for RRF compatibility
                    "score": 1.0 / (1.0 + float(score)), # Convert distance to a similarity score [0, 1]
                    "text": doc.page_content,
                    "source": doc.metadata.get("source", "Dynamic Web Search"),
                })
            return results
        except Exception as e:
            logger.warning("pgvector search skipped: %s", e)
            return []

# Singleton instance
_dynamic_store = None

def get_dynamic_store() -> DynamicVectorStore:
    global _dynamic_store
    if _dynamic_store is None:
        _dynamic_store = DynamicVectorStore()
    return _dynamic_store
