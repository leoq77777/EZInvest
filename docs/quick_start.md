# 快速启动指南

## 前置要求

1. **Python 3.8+**
2. **MySQL** 数据库服务
3. **Redis** 服务
4. **Ollama** 服务（已部署gpt-oss-20b模型）

## 安装步骤

### 1. 克隆项目（如果适用）
```bash
cd EZInvest
```

### 2. 安装Python依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量
复制`.env.example`为`.env`并修改配置：
```bash
cp .env.example .env
# 编辑.env文件，填入你的数据库和Ollama配置
```

### 4. 初始化数据库
```bash
python scripts/init_db.py
```

### 5. 启动服务
```bash
uvicorn app.main:app --reload --port 8000
```

### 6. 访问前端
打开浏览器访问：`http://localhost:8000`

## 验证安装

### 检查API
```bash
curl http://localhost:8000/health
```

### 检查数据库连接
确保MySQL和Redis服务正在运行：
```bash
# 检查Redis
redis-cli ping

# 检查MySQL
mysql -u root -p -e "SHOW DATABASES;"
```

### 检查Ollama
```bash
curl http://localhost:11434/api/tags
```

## 常见问题

### 1. 数据库连接失败
- 检查MySQL和Redis服务是否运行
- 验证`.env`中的连接信息是否正确
- 确认数据库用户有足够权限

### 2. Ollama连接失败
- 确认Ollama服务运行在配置的地址
- 检查模型是否已下载：`ollama list`
- 如果没有模型，运行：`ollama pull gpt-oss-20b`

### 3. 导入错误
- 确保所有依赖已安装：`pip install -r requirements.txt`
- 检查Python版本：`python --version`（需要3.8+）

### 4. 前端无法访问
- 检查FastAPI服务是否运行
- 确认端口8000未被占用
- 查看控制台错误信息

## 测试

运行测试套件：
```bash
pytest
```

运行特定测试：
```bash
pytest tests/test_storage.py -v
```

## 下一步

1. 阅读[开发总结](development_summary.md)了解项目结构
2. 查看各部分的详细文档（`docs/part*.md`）
3. 根据需求调整配置
4. 开始使用！

## 获取帮助

如有问题，请查看：
- 项目README.md
- 各部分的详细文档
- 代码注释

