# 测试运行指南

## 测试分类

### 单元测试 (Unit Tests)
标记: `@pytest.mark.unit`

包含的测试文件:
- `test_storage.py` - 存储层测试
- `test_quant_tool.py` - 量化工具测试
- `test_rag_tool.py` - RAG工具测试
- `test_api.py` (部分) - API基础测试

### 集成测试 (Integration Tests)
标记: `@pytest.mark.integration`

包含的测试文件:
- `test_integration.py` - Agent集成测试
- `test_api.py` (部分) - API查询测试

### 端到端测试 (E2E Tests)
标记: `@pytest.mark.e2e`

包含的测试文件:
- `test_e2e.py` - 完整工作流测试

## 前置要求

### 必需服务
1. **Redis** - 运行在 localhost:6379
2. **MySQL** - 运行在 localhost:3306，数据库名为 `ezinvest`
3. **Ollama** - 运行在 localhost:11434（仅E2E测试需要）

### 必需依赖
```bash
pip install -r requirements.txt
pip install httpx  # FastAPI TestClient需要
```

## 运行测试

### 运行所有单元测试
```bash
pytest -m unit -v
```

### 运行所有端到端测试
```bash
pytest -m e2e -v
```

### 运行所有集成测试
```bash
pytest -m integration -v
```

### 运行所有测试
```bash
pytest -v
```

### 运行特定测试文件
```bash
pytest tests/test_storage.py -v
```

### 跳过需要外部服务的测试
```bash
pytest -m "not integration and not e2e" -v
```

## 测试状态

### 当前状态
- ✅ 测试框架已配置
- ✅ 测试用例已编写
- ⚠️ 需要外部服务（Redis, MySQL, Ollama）才能完整运行
- ⚠️ 部分依赖需要安装（akshare, tf-keras等）

### 已知问题
1. Redis连接失败 - 需要启动Redis服务
2. MySQL连接失败 - 需要配置MySQL数据库
3. Ollama连接失败 - 需要启动Ollama服务
4. 缺少依赖包 - 需要安装requirements.txt中的所有包

## 建议

### 开发环境
1. 使用Docker Compose启动Redis和MySQL
2. 配置测试专用的数据库
3. 使用Mock来避免外部依赖

### CI/CD环境
1. 使用测试容器（testcontainers）
2. Mock外部服务
3. 使用独立的测试数据库

## 测试覆盖率

运行覆盖率报告：
```bash
pytest --cov=app --cov-report=html
```

查看报告：
```bash
# 在浏览器中打开
htmlcov/index.html
```

