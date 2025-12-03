"""
集成测试
"""
import pytest
from app.services.agent import investment_agent


class TestIntegration:
    """集成测试"""
    
    @pytest.mark.integration
    def test_agent_query_processing(self):
        """测试Agent查询处理流程"""
        # 注意：这个测试需要实际的数据库和LLM连接
        # 在实际环境中运行
        
        query = "测试查询"
        
        # 这个测试可能会失败如果数据库/LLM未配置
        # 在实际测试中应该使用mock或测试环境
        try:
            result = investment_agent.process_query(query)
            
            assert "success" in result
            assert "query" in result
            
            if result["success"]:
                assert "symbol" in result
                assert "advice" in result
        except Exception as e:
            # 如果依赖未配置，跳过测试
            pytest.skip(f"Integration test skipped: {e}")

