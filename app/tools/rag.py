"""
RAG工具 - 向量数据库和检索
"""
import faiss
import numpy as np
from typing import List, Dict, Any, Optional
import os
import pickle
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# 延迟加载sentence-transformers
_SentenceTransformer = None

def _get_sentence_transformer():
    """延迟加载SentenceTransformer"""
    global _SentenceTransformer
    # 如果配置强制使用 fallback，则不尝试导入 heavy ML 库
    try:
        from app.config import settings as _settings_local
        if getattr(_settings_local, 'EMBEDDING_FALLBACK', False):
            logger.info("EMBEDDING_FALLBACK enabled: skipping sentence-transformers import")
            return None
    except Exception:
        pass

    if _SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer
            _SentenceTransformer = SentenceTransformer
        except Exception as e:
            logger.warning(f"SentenceTransformer not available or failed to import: {e}. Using fallback embeddings.")
            _SentenceTransformer = None
    return _SentenceTransformer


class RAGTool:
    """RAG检索工具"""
    
    def __init__(self):
        # 延迟加载嵌入模型
        self.embedding_model = None
        self.embedding_dim = None
        self._model_loaded = False
        self._use_fallback_embeddings = False
        
        # 初始化FAISS索引
        self.index_path = settings.FAISS_INDEX_PATH
        self._index: Optional[faiss.Index] = None
        self.metadata: List[Dict[str, Any]] = []
        
        # 确保目录存在
        os.makedirs(os.path.dirname(self.index_path) if os.path.dirname(self.index_path) else '.', exist_ok=True)
        
        # 延迟加载索引（不立即创建，避免阻塞导入和耗时的 TensorFlow 加载）
        self._index_initialized = False
    
    @property
    def index(self) -> Optional[faiss.Index]:
        """返回当前索引，首次访问时延迟初始化"""
        if not self._index_initialized:
            self._ensure_index_initialized()
        return self._index
    
    @index.setter
    def index(self, value: Optional[faiss.Index]) -> None:
        """设置索引"""
        self._index = value
    
    def _ensure_model_loaded(self):
        """确保嵌入模型已加载"""
        if not self._model_loaded:
            # Respect global configuration to force fallback embeddings
            if getattr(settings, 'EMBEDDING_FALLBACK', False):
                self._use_fallback_embeddings = True
                self.embedding_dim = 128
                self._model_loaded = True
                logger.info("Using fallback embedding model (hash-based) due to EMBEDDING_FALLBACK")
                return

            try:
                SentenceTransformer = _get_sentence_transformer()
                if SentenceTransformer is None:
                    self._use_fallback_embeddings = True
                    self.embedding_dim = 128
                    self._model_loaded = True
                    logger.info("Using fallback embedding model (hash-based)")
                else:
                    self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
                    self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
                    self._use_fallback_embeddings = False
                    self._model_loaded = True
                    logger.info("Embedding model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load embedding model, using fallback: {e}")
                self._use_fallback_embeddings = True
                self.embedding_dim = 128
                self._model_loaded = True
    
    def _ensure_index_initialized(self):
        """确保索引已初始化"""
        if not self._index_initialized:
            self._load_or_create_index()
            self._index_initialized = True
    
    def _load_or_create_index(self):
        """加载或创建FAISS索引"""
        index_file = f"{self.index_path}.index"
        metadata_file = f"{self.index_path}.metadata"
        
        if os.path.exists(index_file) and os.path.exists(metadata_file):
            try:
                # 加载现有索引
                self._index = faiss.read_index(index_file)
                with open(metadata_file, 'rb') as f:
                    self.metadata = pickle.load(f)
                logger.info(f"Loaded existing FAISS index with {len(self.metadata)} vectors")
            except Exception as e:
                logger.warning(f"Failed to load existing index: {e}, creating new one")
                self._create_new_index()
        else:
            self._create_new_index()
    
    def _create_new_index(self):
        """创建新的FAISS索引 - 使用混合HNSW+IVF_PQ索引"""
        # 延迟获取embedding_dim（只有在需要时才加载模型）
        if self.embedding_dim is None:
            # 尝试从已存在的索引获取维度
            index_file = f"{self.index_path}.index"
            if os.path.exists(index_file):
                try:
                    temp_index = faiss.read_index(index_file)
                    self.embedding_dim = temp_index.d
                    self._index = temp_index
                    metadata_file = f"{self.index_path}.metadata"
                    if os.path.exists(metadata_file):
                        with open(metadata_file, 'rb') as f:
                            self.metadata = pickle.load(f)
                    logger.info(f"Loaded existing index with dimension {self.embedding_dim}")
                    return
                except:
                    pass
            # 如果无法从现有索引获取，则加载模型
            self._ensure_model_loaded()
        
        # 使用混合索引：HNSW + IVF_PQ
        # 对于小数据集，使用HNSW；对于大数据集，使用IVF_PQ
        try:
            # 尝试创建混合索引
            # 首先创建量化器（IVF）
            nlist = min(100, max(10, self.embedding_dim // 10))  # 聚类中心数
            quantizer = faiss.IndexHNSWFlat(self.embedding_dim, 32)  # HNSW作为量化器
            
            # 创建IVF_PQ索引
            m = 8  # 子向量数
            bits = 8  # 每个子向量的量化位数
            self._index = faiss.IndexIVFPQ(quantizer, self.embedding_dim, nlist, m, bits)
            
            # 训练索引（需要先添加一些数据）
            self._needs_training = True
            logger.info(f"Created hybrid FAISS index (HNSW+IVF_PQ) with dimension {self.embedding_dim}")
        except Exception as e:
            logger.warning(f"Failed to create hybrid index, falling back to IndexFlatL2: {e}")
            # Fallback到简单索引
            self._index = faiss.IndexFlatL2(self.embedding_dim)
            self._needs_training = False
        
        self.metadata = []
        logger.info("Created new FAISS index")
    
    def _save_index(self):
        """保存索引到磁盘"""
        try:
            if self._index is None:
                return
            index_file = f"{self.index_path}.index"
            metadata_file = f"{self.index_path}.metadata"
            
            faiss.write_index(self._index, index_file)
            with open(metadata_file, 'wb') as f:
                pickle.dump(self.metadata, f)
            
            logger.info(f"Saved FAISS index with {len(self.metadata)} vectors")
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
    
    def add_documents(self, documents: List[Dict[str, Any]]):
        """
        添加文档到向量数据库
        
        Args:
            documents: 文档列表，每个文档包含 'text' 和可选的 'metadata'
        """
        if not documents:
            return
        
        # 确保索引和模型已初始化
        self._ensure_index_initialized()
        self._ensure_model_loaded()

        texts = [doc.get('text', '') for doc in documents]

        # 生成嵌入向量（支持 fallback）
        if getattr(self, '_use_fallback_embeddings', False):
            embeddings = self._compute_fallback_embeddings(texts)
        else:
            embeddings = self.embedding_model.encode(
                texts,
                show_progress_bar=len(texts) > 10,
                convert_to_numpy=True
            )
        
        # 添加到索引
        embeddings = embeddings.astype('float32')
        if self.index is None:
            self._ensure_index_initialized()
        self.index.add(embeddings)
        
        # 保存元数据
        for i, doc in enumerate(documents):
            metadata = {
                'id': len(self.metadata),
                'text': doc.get('text', ''),
                **doc.get('metadata', {})
            }
            self.metadata.append(metadata)
        
        # 保存索引
        self._save_index()
        
        logger.info(f"Added {len(documents)} documents to vector database")
    
    def search(self, query: str, top_k: int = 5, filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        搜索相似文档
        
        Args:
            query: 查询文本
            top_k: 返回前k个结果
            filter_dict: 可选的过滤条件（基于metadata）
        
        Returns:
            相似文档列表，包含文本、元数据和相似度分数
        """
        # 确保索引已初始化
        self._ensure_index_initialized()
        
        if self.index is None or (hasattr(self.index, 'ntotal') and self.index.ntotal == 0):
            logger.warning("Index is empty, returning empty results")
            return []
        
        # 确保模型已加载
        self._ensure_model_loaded()

        # 生成查询向量（支持 fallback）
        if getattr(self, '_use_fallback_embeddings', False):
            query_embedding = self._compute_fallback_embeddings([query]).astype('float32')
        else:
            query_embedding = self.embedding_model.encode(
                [query],
                convert_to_numpy=True
            ).astype('float32')
        
        # 搜索 - 如果有过滤条件，获取更多结果以确保过滤后仍有足够的结果
        search_k = min(self.index.ntotal, max(top_k * 3, 10) if filter_dict else top_k)
        distances, indices = self.index.search(query_embedding, search_k)
        
        # 构建结果
        results = []
        rank = 1
        for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
            if idx >= len(self.metadata):
                continue
            
            metadata = self.metadata[idx].copy()
            
            # 应用过滤条件
            if filter_dict:
                if not all(metadata.get(k) == v for k, v in filter_dict.items()):
                    continue
            
            results.append({
                'text': metadata.get('text', ''),
                'metadata': {k: v for k, v in metadata.items() if k != 'text'},
                'score': float(distance),
                'rank': rank
            })
            rank += 1
            
            # 达到所需的 top_k 数量后停止
            if len(results) >= top_k:
                break
        
        return results

    def _compute_fallback_embeddings(self, texts: List[str]):
        """为文本生成简单的哈希基础嵌入（确定性），用于无 heavy ML 依赖的 fallback。"""
        import hashlib
        vectors = []
        dim = self.embedding_dim or 128
        for t in texts:
            h = hashlib.sha256(t.encode('utf-8')).digest()
            # 将哈希字节重复扩展到足够长度
            repeated = (h * ((dim // len(h)) + 1))[:dim]
            arr = np.frombuffer(repeated, dtype='uint8').astype('float32')
            # 归一化
            norm = np.linalg.norm(arr)
            if norm == 0:
                vectors.append(np.zeros(dim, dtype='float32'))
            else:
                vectors.append(arr / norm)
        return np.stack(vectors)
    
    def search_by_symbol(self, symbol: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """根据股票代码搜索相关文档"""
        return self.search(query, top_k=top_k, filter_dict={'symbol': symbol})
    
    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        # 不强制初始化，只返回当前状态
        return {
            'total_vectors': self._index.ntotal if self._index else 0,
            'embedding_dim': self.embedding_dim,
            'index_path': self.index_path
        }


# 全局RAG工具实例（延迟初始化，避免导入时就加载模型）
# 全局RAG工具实例（在导入时创建，RAGTool 本身延迟加载模型与索引）
rag_tool = RAGTool()


def get_rag_tool():
    """获取RAG工具实例（已创建）"""
    return rag_tool

