"""
RAG工具测试
"""
import pytest
import os
import shutil
from app.tools.rag import rag_tool
from app.config import settings


@pytest.fixture(autouse=True)
def reset_rag_tool():
    """在每个测试前重置 RAG 工具，确保测试隔离"""
    # 清除索引和元数据
    rag_tool._index = None
    rag_tool.metadata = []
    rag_tool._index_initialized = False
    rag_tool.embedding_dim = None
    rag_tool._model_loaded = False
    
    # 删除磁盘上的索引文件，避免跨测试污染
    index_dir = os.path.dirname(settings.FAISS_INDEX_PATH)
    if index_dir and os.path.exists(index_dir):
        for file in os.listdir(index_dir):
            if file.startswith(os.path.basename(settings.FAISS_INDEX_PATH)):
                try:
                    filepath = os.path.join(index_dir, file)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                except:
                    pass
    
    yield
    
    # 测试后也清理
    rag_tool._index = None
    rag_tool.metadata = []
    rag_tool._index_initialized = False
    rag_tool.embedding_dim = None
    rag_tool._model_loaded = False
    
    # 清除索引文件
    if index_dir and os.path.exists(index_dir):
        for file in os.listdir(index_dir):
            if file.startswith(os.path.basename(settings.FAISS_INDEX_PATH)):
                try:
                    filepath = os.path.join(index_dir, file)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                except:
                    pass


class TestRAGTool:
    """RAG工具测试"""
    
    @pytest.mark.unit
    def test_add_documents(self):
        """测试添加文档"""
        documents = [
            {
                'text': '这是一条测试文档',
                'metadata': {
                    'symbol': 'TEST001',
                    'source': 'test'
                }
            },
            {
                'text': '这是另一条测试文档',
                'metadata': {
                    'symbol': 'TEST002',
                    'source': 'test'
                }
            }
        ]
        
        initial_count = rag_tool.index.ntotal
        rag_tool.add_documents(documents)
        
        assert rag_tool.index.ntotal == initial_count + 2
    
    @pytest.mark.unit
    def test_search(self):
        """测试搜索"""
        # 先添加一些文档
        documents = [
            {
                'text': '苹果公司发布了新的iPhone产品',
                'metadata': {'symbol': 'AAPL', 'type': 'news'}
            },
            {
                'text': '腾讯公司公布了季度财报',
                'metadata': {'symbol': '00700', 'type': 'news'}
            }
        ]
        rag_tool.add_documents(documents)
        
        # 搜索
        results = rag_tool.search('苹果 iPhone', top_k=2)
        
        assert len(results) > 0
        assert 'text' in results[0]
        assert 'metadata' in results[0]
        assert 'score' in results[0]
    
    @pytest.mark.unit
    def test_search_by_symbol(self):
        """测试按股票代码搜索"""
        # 添加文档
        documents = [
            {
                'text': 'AAPL股票价格上涨',
                'metadata': {'symbol': 'AAPL'}
            },
            {
                'text': '腾讯股票分析',
                'metadata': {'symbol': '00700'}
            }
        ]
        rag_tool.add_documents(documents)
        
        # 搜索
        results = rag_tool.search_by_symbol('AAPL', '股票价格', top_k=1)
        
        assert len(results) > 0
        assert results[0]['metadata']['symbol'] == 'AAPL'
    
    @pytest.mark.unit
    def test_get_stats(self):
        """测试获取统计信息"""
        stats = rag_tool.get_stats()
        
        assert 'total_vectors' in stats
        assert 'embedding_dim' in stats
        assert 'index_path' in stats
        assert isinstance(stats['total_vectors'], int)

