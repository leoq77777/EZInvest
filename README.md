# EZInvest - 智能投资助手AI Agent

## 项目简介

EZInvest是一个基于大语言模型的智能投资助手，通过RAG技术整合金融市场数据、量化分析和政策新闻，为用户提供专业的投资建议。

## 核心功能

1. **金融市场数据获取**: 通过akshare API获取实时和历史金融数据
2. **分层数据存储**: Redis（热数据）+ MySQL（冷数据）的混合存储架构
3. **智能限流处理**: 冷热数据分离 + 低峰期预取机制
4. **量化分析工具**: 基于finRL的强化学习和金融技术指标分析
5. **政策新闻分析**: 网络爬虫 + FAISS向量数据库的语义检索
6. **端到端工作流**: 用户查询 → 标的识别 → 数据分析 → 投资建议

## 技术栈

- **后端框架**: FastAPI
- **大语言模型**: Ollama (gpt-oss-20b)
- **数据存储**: Redis + MySQL
- **向量数据库**: FAISS
- **量化分析**: finRL, TA-Lib
- **数据源**: akshare API

## 项目结构

```
EZInvest/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI应用入口
│   ├── config.py               # 配置管理
│   ├── models/                 # 数据模型
│   ├── database/               # 数据库连接和操作
│   ├── services/               # 业务逻辑服务
│   │   ├── data_fetcher.py    # akshare数据获取
│   │   ├── storage.py         # 数据存储管理
│   │   ├── quant_tool.py      # 量化分析工具
│   │   ├── policy_tool.py     # 政策分析工具
│   │   └── agent.py           # Agent核心逻辑
│   ├── tools/                  # 工具模块
│   │   ├── rag.py             # RAG检索
│   │   └── llm.py             # LLM集成
│   └── api/                    # API路由
│       └── routes.py
├── frontend/                   # 前端界面
├── tests/                      # 测试文件
├── docs/                       # 文档
├── requirements.txt
└── README.md
```

## 安装和运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# Database
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=ezinvest

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gpt-oss-20b

# FAISS
FAISS_INDEX_PATH=./data/faiss_index
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

### 3. 初始化数据库

```bash
python scripts/init_db.py
```

### 4. 运行服务

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. 访问前端

打开浏览器访问 `http://localhost:8000`

## 开发计划

项目采用敏捷开发方式，分为以下部分：

- [x] Part 1: 项目基础结构
- [ ] Part 2: 数据层（Redis + MySQL）
- [ ] Part 3: akshare API集成
- [ ] Part 4: 冷热数据管理
- [ ] Part 5: RAG工具
- [ ] Part 6: Quant Tool
- [ ] Part 7: 政策分析Tool
- [ ] Part 8: 大模型集成
- [ ] Part 9: Agent核心逻辑
- [ ] Part 10: 前端Web界面
- [ ] Part 11: 测试和联调

## 测试

```bash
pytest tests/ -v
```

## 许可证

MIT License

