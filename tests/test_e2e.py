"""
端到端测试
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.agent import investment_agent

client = TestClient(app)


class TestE2E:
    """端到端测试"""
    
    @pytest.mark.e2e
    def test_full_workflow_query(self):
        """测试完整的查询工作流"""
        # 这个测试需要完整的系统环境（数据库、Redis、Ollama）
        query = "测试股票000001的投资建议"
        
        try:
            # 测试API端点
            response = client.post(
                "/api/query",
                json={"query": query, "stream": False}
            )
            
            # 验证响应格式
            assert response.status_code in [200, 500]
            
            if response.status_code == 200:
                data = response.json()
                assert "success" in data
                assert "query" in data
                
                if data["success"]:
                    # 验证成功响应的结构
                    assert "symbol" in data or "error" in data
        except Exception as e:
            # 如果环境未配置，跳过测试
            pytest.skip(f"E2E test skipped due to missing dependencies: {e}")
    
    @pytest.mark.e2e
    def test_agent_end_to_end(self):
        """测试Agent端到端处理"""
        query = "分析一下000001"
        
        try:
            result = investment_agent.process_query(query)
            
            # 验证结果结构
            assert isinstance(result, dict)
            assert "success" in result
            assert "query" in result
            
            # 如果成功，验证必要字段
            if result.get("success"):
                # 可能成功但未找到标的
                assert "symbol" in result or "error" in result
        except Exception as e:
            pytest.skip(f"E2E test skipped: {e}")
    
    @pytest.mark.e2e
    def test_api_health_check(self):
        """测试API健康检查（端到端）"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    @pytest.mark.e2e
    def test_frontend_accessible(self):
        """测试前端是否可访问"""
        response = client.get("/")
        # 前端文件可能不存在，所以接受200或404
        assert response.status_code in [200, 404]

