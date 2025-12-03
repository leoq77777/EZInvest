"""
RAG工具 - 向量数据库和检索
"""
import faiss
import numpy as np
from typing import List, Dict, Any, Optional
import os
import pickle
from sentence_transformers import SentenceTransformer
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class RAGTool:
    """RAG检索工具"""
    
    def __init__(self):
        # 加载嵌入模型
        self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        
        # 初始化FAISS索引
        self.index_path = settings.FAISS_INDEX_PATH
        self.index: Optional[faiss.Index] = None
        self.metadata: List[Dict[str, Any]] = []
        
        # 确保目录存在
        os.makedirs(os.path.dirname(self.index_path) if os.path.dirname(self.index_path) else '.', exist_ok=True)
        
        # 加载或创建索引
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        """加载或创建FAISS索引"""
        index_file = f"{self.index_path}.index"
        metadata_file = f"{self.index_path}.metadata"
        
        if os.path.exists(index_file) and os.path.exists(metadata_file):
            try:
                # 加载现有索引
                self.index = faiss.read_index(index_file)
                with open(metadata_file, 'rb') as f:
                    self.metadata = pickle.load(f)
                logger.info(f"Loaded existing FAISS index with {len(self.metadata)} vectors")
            except Exception as e:
                logger.warning(f"Failed to load existing index: {e}, creating new one")
                self._create_new_index()
        else:
            self._create_new_index()
    
    def _create_new_index(self):
        """创建新的FAISS索引"""
        # 使用L2距离的平面索引
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        self.metadata = []
        logger.info("Created new FAISS index")
    
    def _save_index(self):
        """保存索引到磁盘"""
        try:
            index_file = f"{self.index_path}.index"
            metadata_file = f"{self.index_path}.metadata"
            
            faiss.write_index(self.index, index_file)
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
        
        texts = [doc.get('text', '') for doc in documents]
        
        # 生成嵌入向量
        embeddings = self.embedding_model.encode(
            texts,
            show_progress_bar=len(texts) > 10,
            convert_to_numpy=True
        )
        
        # 添加到索引
        embeddings = embeddings.astype('float32')
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
        if self.index.ntotal == 0:
            logger.warning("Index is empty, returning empty results")
            return []
        
        # 生成查询向量
        query_embedding = self.embedding_model.encode(
            [query],
            convert_to_numpy=True
        ).astype('float32')
        
        # 搜索
        k = min(top_k, self.index.ntotal)
        distances, indices = self.index.search(query_embedding, k)
        
        # 构建结果
        results = []
        for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < len(self.metadata):
                metadata = self.metadata[idx].copy()
                
                # 应用过滤条件
                if filter_dict:
                    if all(metadata.get(k) == v for k, v in filter_dict.items()):
                        results.append({
                            'text': metadata.get('text', ''),
                            'metadata': {k: v for k, v in metadata.items() if k != 'text'},
                            'score': float(distance),
                            'rank': i + 1
                        })
                else:
                    results.append({
                        'text': metadata.get('text', ''),
                        'metadata': {k: v for k, v in metadata.items() if k != 'text'},
                        'score': float(distance),
                        'rank': i + 1
                    })
        
        return results
    
    def search_by_symbol(self, symbol: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """根据股票代码搜索相关文档"""
        return self.search(query, top_k=top_k, filter_dict={'symbol': symbol})
    
    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        return {
            'total_vectors': self.index.ntotal,
            'embedding_dim': self.embedding_dim,
            'index_path': self.index_path
        }


# 全局RAG工具实例
rag_tool = RAGTool()

