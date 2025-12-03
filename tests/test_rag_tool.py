"""
RAG工具测试
"""
import pytest
from app.tools.rag import rag_tool


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

