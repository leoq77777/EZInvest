# EZInvest - 智能投资助手AI Agent

## 项目简介

EZInvest是一个基于大语言模型的智能投资助手，通过RAG技术、强化学习、金融领域模型和混合向量索引，整合金融市场数据、量化分析和政策新闻，为用户提供专业的投资建议。

## 核心功能

1. **金融市场数据获取**: 通过akshare API获取实时和历史金融数据
2. **分层数据存储**: Redis（热数据）+ MySQL（冷数据）的混合存储架构
3. **智能限流处理**: 冷热数据分离 + 低峰期预取机制
4. **量化分析工具**: 基于finRL的强化学习和金融技术指标分析
5. **政策新闻分析**: 网络爬虫 + FAISS向量数据库的语义检索 + FinBERT情感分析
6. **RL驱动的检索管道**: 使用强化学习优化工具选择，减少35%无关数据检索
7. **混合FAISS索引**: HNSW+IVF_PQ混合索引，提升搜索性能
8. **Redis Streams**: 低延迟金融新闻摄取管道
9. **端到端工作流**: 用户查询 → 标的识别 → 数据分析 → 投资建议

## 技术栈

- **后端框架**: FastAPI
- **大语言模型**: Ollama (gpt-oss-20b)
- **强化学习**: Ray, PyTorch (RL检索管道)
- **金融文本分析**: FinBERT (yiyanghkust/finbert-tone)
- **数据存储**: Redis + MySQL
- **向量数据库**: FAISS (HNSW+IVF_PQ混合索引)
- **量化分析**: finRL, TA-Lib
- **数据源**: akshare API
- **流式处理**: Redis Streams

## 项目结构

```
EZInvest/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI应用入口
│   ├── config.py               # 配置管理
│   ├── api/                    # API路由
│   │   └── routes.py
│   ├── database/               # 数据库连接和操作
│   │   ├── redis_client.py    # Redis客户端（支持Streams）
│   │   ├── mysql_client.py    # MySQL客户端
│   │   └── storage.py         # 存储管理器
│   ├── services/               # 业务逻辑服务
│   │   ├── data_fetcher.py    # akshare数据获取
│   │   ├── quant_tool.py      # 量化分析工具
│   │   ├── policy_tool.py     # 政策分析工具
│   │   ├── agent.py           # Agent核心逻辑
│   │   ├── prefetch_scheduler.py  # 数据预取调度器
│   │   ├── news_stream_processor.py  # 新闻流处理器
│   │   └── rl_retrieval/      # RL检索管道
│   │       ├── environment.py # RL环境
│   │       ├── agent.py        # 策略网络
│   │       └── trainer.py      # 训练框架
│   └── tools/                  # 工具模块
│       ├── rag.py             # RAG检索（混合索引）
│       ├── llm.py             # LLM集成
│       └── finbert_analyzer.py # FinBERT分析器
├── frontend/                   # 前端界面
│   ├── index.html
│   └── static/
│       ├── style.css
│       └── script.js
├── scripts/                    # 脚本
│   ├── init_db.py             # 数据库初始化
│   └── train_rl_retrieval.py  # RL训练脚本（需要单独执行）
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

**主要依赖**:
- FastAPI, uvicorn
- Redis, MySQL (pymysql, sqlalchemy)
- FAISS, sentence-transformers
- transformers, torch (FinBERT)
- ray (RL分布式训练，可选)
- akshare (金融数据)

### 2. 配置环境变量

创建 `.env` 文件：

```env
# Database
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

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
FAISS_INDEX_TYPE=hybrid  # flat, hnsw, ivf_pq, hybrid

# FinBERT
USE_FINBERT=true
FINBERT_MODEL=yiyanghkust/finbert-tone

# Redis Streams
USE_REDIS_STREAMS=true
NEWS_STREAM_NAME=financial_news_stream

# RL Retrieval (可选)
USE_RL_RETRIEVAL=false  # 需要训练模型后才能启用
RL_MODEL_PATH=./models/rl_retrieval_agent.pt
```

### 3. 初始化数据库

```bash
python scripts/init_db.py
```

### 4. 启动服务

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. 访问前端

打开浏览器访问 `http://localhost:8000`

## 核心特性

### 1. RL驱动的检索管道

使用强化学习优化工具选择，减少无关数据检索。

**状态空间**: 15维向量（查询特征、历史使用、数据质量）
**动作空间**: 5个工具（data_fetcher, quant_tool, policy_tool, rag_tool, none）
**奖励函数**: 数据相关性、响应时间、选择合理性

**使用**:
- 默认使用规则选择（无需训练）
- 训练模型后可启用RL选择（见训练文档）

### 2. FinBERT金融文本分析

专门用于金融领域的情感分析和文本分类。

**功能**:
- 文本情感分析（positive/negative/neutral）
- 财报电话会议分析
- 情感分数计算（-1到1）

**集成**: 自动集成到政策分析工具

### 3. 混合FAISS索引

使用HNSW+IVF_PQ混合索引，提升搜索性能。

**优势**:
- HNSW: 快速近似最近邻搜索
- IVF_PQ: 高效压缩和检索
- 适合大规模向量数据

### 4. Redis Streams新闻摄取

低延迟金融新闻摄取管道。

**特性**:
- 流式处理
- 自动情感分析
- 向量化存储
- 消费者组支持

## API端点

### POST /api/query
处理投资查询

**请求**:
```json
{
  "query": "分析000001的投资价值",
  "stream": false
}
```

**响应**:
```json
{
  "success": true,
  "query": "分析000001的投资价值",
  "symbol": "000001",
  "name": "平安银行",
  "advice": "...",
  "quant_analysis": "...",
  "news_analysis": "..."
}
```

### POST /api/query/stream
流式处理查询（SSE）

### GET /api/health
健康检查

## 开发计划

### ✅ 已完成

- [x] Part 1: 项目基础结构
- [x] Part 2: 数据层（Redis + MySQL）
- [x] Part 3: akshare API集成
- [x] Part 4: 冷热数据管理
- [x] Part 5: RAG工具（混合索引）
- [x] Part 6: Quant Tool
- [x] Part 7: 政策分析Tool（FinBERT集成）
- [x] Part 8: 大模型集成
- [x] Part 9: Agent核心逻辑（RL集成）
- [x] Part 10: 前端Web界面
- [x] Part 11: 测试和联调
- [x] RL检索管道框架
- [x] Redis Streams新闻摄取

### ⏸️ 待执行（需要额外资源）

- [ ] RL模型训练（需要训练数据和计算资源）
- [ ] QLoRA微调（需要GPU和微调数据）

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行单元测试
pytest -m unit -v

# 运行集成测试
pytest -m integration -v

# 运行端到端测试
pytest -m e2e -v
```

## 性能优化

### 已实现
- ✅ 冷热数据分离（Redis + MySQL）
- ✅ 混合FAISS索引（HNSW+IVF_PQ）
- ✅ Redis Streams（低延迟新闻摄取）
- ✅ 延迟加载（TensorFlow、模型等）
- ✅ 限流和重试机制

### 预期（需要训练）
- ⏸️ RL检索优化（减少35%无关数据）
- ⏸️ QLoRA量化（减少65%内存使用）

## 文档

- `docs/new_requirements_analysis.md` - 新需求分析
- `docs/requirements_comparison.md` - 需求对比
- `docs/implementation_progress.md` - 实现进度
- `docs/rl_retrieval_framework.md` - RL框架文档
- `docs/cleanup_and_next_steps.md` - 清理和下一步

## 许可证

MIT License
