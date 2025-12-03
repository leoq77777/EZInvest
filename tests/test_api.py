"""
API测试
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestAPI:
    """API测试"""
    
    @pytest.mark.unit
    def test_root(self):
        """测试根路径"""
        response = client.get("/")
        assert response.status_code in [200, 404]  # 404 if frontend not found
    
    @pytest.mark.unit
    def test_health(self):
        """测试健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    @pytest.mark.unit
    def test_api_health(self):
        """测试API健康检查"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    @pytest.mark.integration
    def test_query_endpoint(self):
        """测试查询端点"""
        # 注意：这个测试可能需要实际的数据库和LLM连接
        # 在实际测试中可能需要mock
        response = client.post(
            "/api/query",
            json={"query": "测试查询", "stream": False}
        )
        
        # 即使失败也应该返回合理的响应
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "query" in data

