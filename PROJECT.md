# EZInvest — 基于 ReAct 循环架构的自主金融投研智能体

## 项目概述

EZInvest 是一个端到端的 AI 金融投研助手。系统采用 **ReAct (Reasoning & Acting) 循环架构**，通过多轮推理-行动-观察迭代，自主完成从实时数据采集、多源信息检索到投研报告生成的完整工作流。相比传统的线性 RAG 问答系统，EZInvest 具备运行时自纠错、实体歧义消解和动态知识注入的能力。

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       Next.js 前端 (React 19)                    │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │ Zustand   │  │ SSE Stream   │  │ ReactMarkdown 研报渲染     │  │
│  │ 状态管理   │  │ 实时事件消费  │  │ (GFM 表格 / 代码块)       │  │
│  └──────────┘  └──────────────┘  └───────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ SSE (Server-Sent Events)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI 后端 (Async)                         │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              ReAct 推理循环 (graph.py)                      │  │
│  │                                                            │  │
│  │   ┌──────────┐    ┌───────────┐    ┌──────────────────┐   │  │
│  │   │ Reasoner │───▶│ Tool Node │───▶│ Observation Pool │   │  │
│  │   │ (LLM)    │◀───│ (动态调度) │    │  (状态积累)       │   │  │
│  │   └──────────┘    └───────────┘    └──────────────────┘   │  │
│  │        │                                                   │  │
│  │        ├── type: action  → 调用工具                        │  │
│  │        ├── type: clarification → 暂停,询问用户              │  │
│  │        └── type: finish  → 汇总输出报告                    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────── 工具集 (Tools) ────────────────────────────┐  │
│  │  market_data  │  web_scraper  │  retriever  │  calculator  │  │
│  │  (yfinance)   │  (DDGS+httpx) │  (Hybrid)   │  (确定性)    │  │
│  │               │               │             │              │  │
│  │  sentiment_analyzer (FinBERT)                              │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────── 混合检索管道 (RAG) ────────────────────────┐  │
│  │                                                            │  │
│  │  FAISS (HNSW)  ──┐                                        │  │
│  │                   ├── RRF 融合 ── Cross-Encoder Rerank     │  │
│  │  BM25 (稀疏)   ──┤                    │                    │  │
│  │                   │                    ▼                    │  │
│  │  pgvector (动态) ─┘              Top-K 精排结果             │  │
│  │                                                            │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
      ┌──────────┐ ┌──────────┐ ┌──────────┐
      │PostgreSQL│ │  Redis   │ │ DeepSeek │
      │+pgvector │ │  Cache   │ │ / OpenAI │
      └──────────┘ └──────────┘ └──────────┘
```

---

## 核心技术栈

| 层级 | 技术 | 用途 |
|:---|:---|:---|
| **推理引擎** | LangChain Core + 自研 ReAct 循环 | 多轮推理、动态工具调度、实体消歧 |
| **LLM** | DeepSeek-V3 / GPT-4-Turbo / Ollama (本地) | 可通过配置一键切换 Provider |
| **向量检索** | FAISS (HNSW) + BGE-large-en-v1.5 | 离线 SEC 文件 / 财报的稠密检索 |
| **稀疏检索** | rank-bm25 | 关键词精确匹配（如 Ticker、公司名） |
| **动态知识库** | PostgreSQL 16 + pgvector | 存储实时抓取的网页数据向量 |
| **结果融合** | Reciprocal Rank Fusion (RRF) | 合并多源检索结果并去重 |
| **精排模型** | BGE-Reranker-v2-m3 (Cross-Encoder) | 对融合后的候选文档做二次精排 |
| **情感分析** | FinBERT (ProsusAI/finbert) | 金融文本情感分类 (Positive/Negative/Neutral) |
| **实时行情** | yfinance (Yahoo Finance API) | 带重试、超时和熔断机制的行情获取 |
| **联网搜索** | DuckDuckGo Search + httpx + BeautifulSoup | 搜索 → 抓取 → 解析 → 分块 → 入库全自动化 |
| **缓存** | Redis 7 | 检索结果缓存，TTL 可配置 |
| **后端框架** | FastAPI (全异步) | SSE 流式传输 + RESTful API |
| **前端** | Next.js 15 + React 19 + Zustand + Tailwind CSS 4 | 实时流式渲染 + 全局状态管理 |
| **容器化** | Docker Compose (多 Profile) | 支持 vLLM (GPU) / Ollama (CPU) 按需启动 |

---

## 工程难点与解决方案

### 1. 从线性管道到循环图的架构演进

**问题**：传统的 `Plan → Execute → Summarize` 单向管道中，一旦规划阶段产生了错误的意图理解（如将已独立上市的公司误映射到旧母公司），后续所有工具调用都会基于错误前提执行，且无法在运行时修正。

**方案**：设计了基于 ReAct 的循环状态机架构。推理引擎（Reasoner）在每一轮迭代中：
- 综合分析所有已积累的 `observations`（工具返回结果）
- 动态决定下一步应调用哪个工具，或是否需要向用户确认
- 如果发现前一轮的数据与预期冲突，可以在下一轮自行修正

**关键实现**：`graph.py` 中的 `run_agent_stream()` 函数使用 `AsyncGenerator` 在最多 8 轮迭代中完成推理，每轮通过 JSON 协议与 LLM 交互，解析出 `action / clarification / finish` 三种决策类型。

```python
# 核心循环伪代码
for i in range(max_iterations):
    decision = await llm.reason(query, observations)
    if decision.type == "action":
        result = await execute_tool(decision.tool, decision.args)
        observations.append(result)  # 状态积累
    elif decision.type == "clarification":
        yield ask_user(decision.message)  # 暂停循环,等待用户
        return
    elif decision.type == "finish":
        yield summarize(observations)  # 生成报告
        return
```

### 2. 三路混合检索与 RRF 融合

**问题**：单一检索策略无法同时覆盖语义相关性（稠密）和关键词精确匹配（稀疏）。此外，实时抓取的网页内容需要与离线知识库无缝融合。

**方案**：实现了三路并行检索 + Reciprocal Rank Fusion (RRF) + Cross-Encoder 精排的完整管道：

1. **FAISS (HNSW)**：使用 BGE-large-en-v1.5 编码的 1024 维稠密向量，对 SEC 文件做语义检索
2. **BM25**：基于 TF-IDF 的稀疏检索，擅长精确匹配 Ticker 符号和专有名词
3. **pgvector (动态)**：存储 `web_scraper` 实时抓取并分块后的网页数据，确保最新信息可被检索

三路结果通过 RRF 公式融合去重：`RRF(d) = Σ 1/(k + rank(d))`，最终经 Cross-Encoder (BGE-Reranker-v2-m3) 做精排，输出 Top-K 高质量结果。

**容错设计**：pgvector 连接失败时自动降级为双路检索（FAISS + BM25），不阻塞主流程。Redis 缓存失效时透明回退到实时查询。

### 3. 实时联网检索的全链路自动化

**问题**：金融市场变化极快，静态知识库无法覆盖公司并购、拆分等突发事件（如 SanDisk 2025 年从 WDC 拆分独立上市）。

**方案**：设计了 `Search → Scrape → Parse → Chunk → Index → Retrieve` 的全自动化管道：

- **搜索**：通过 DuckDuckGo Search API 获取最新网页 URL
- **抓取**：使用 `httpx` 异步并发抓取多个 URL，通过 `asyncio.gather` 实现并行化
- **解析**：BeautifulSoup 提取正文，过滤 `<script>/<style>/<nav>` 等噪声标签
- **分块**：滑动窗口分块（chunk_size=1000, overlap=200），确保上下文连贯性
- **入库**：通过自封装的 `DynamicVectorStore` 将分块写入 pgvector
- **检索**：后续 `retriever_tool` 会自动从 pgvector 中搜索这些新入库的内容

整个流程对智能体透明，它只需调用 `web_scraper(query)` 即可完成从搜索到入库的全部操作。

### 4. SSE 流式传输与前端实时状态同步

**问题**：金融投研报告的生成通常需要 10-30 秒（多轮工具调用 + LLM 推理）。如果用户在此期间看不到任何反馈，体验极差。

**方案**：设计了基于 Server-Sent Events (SSE) 的全链路流式传输协议：

**后端事件协议**：
```
event: thought     → 推理过程（"正在查询 SNDK 实时行情..."）
event: plan        → 执行计划（步骤列表）
event: step_update → 步骤状态更新
event: token       → 最终报告的逐字输出
event: done        → 完成信号（含总延迟）
```

**前端状态管理**：通过 Zustand 实现了细粒度的状态更新。每个 `Message` 对象独立维护 `thought`、`plan`、`toolCalls`、`content` 等字段，确保 UI 的局部渲染不会触发全局重绘。

**关键优化**：开发环境下绕过 Next.js 的 `rewrites` 代理直连后端（`API_BASE = http://localhost:8080`），避免了 Next.js 开发服务器对 SSE 流的缓冲（Buffering）导致的响应卡顿。

### 5. 行情数据精度与盘中实时性

**问题**：`yfinance` 的 `history()` 接口返回的是历史收盘价，在盘中交易时段会与实时价格产生显著偏差（实测偏差可达 7%）。

**方案**：实现了三级价格回退策略：

```python
real_time_price = (
    info.get("currentPrice")           # 优先：实时报价
    or info.get("regularMarketPrice")   # 其次：盘中市场价
    or float(latest["Close"])           # 兜底：最近收盘价
)
```

同时从 `stock.info` 中提取 `regularMarketOpen/DayHigh/DayLow/Volume` 等盘中字段，确保所有数据维度都反映最新状态。增加了指数退避重试（最多 3 次）和请求级超时控制（10s），在 Yahoo Finance API 不稳定时优雅降级。

### 6. LLM 知识截止日期与实体歧义消解

**问题**：LLM 的训练数据存在截止日期。当市场发生重大变动（如 SanDisk 2025 年独立上市，代码 SNDK 重新激活），模型可能基于过时知识将 SanDisk 映射到 WDC，导致返回完全错误的数据。

**方案**：多层防线：

1. **Prompt 层**：在 `SYSTEM_PROMPT` 中注入时间上下文和重大市场变动事实，覆盖模型的过期记忆
2. **Reasoner 层**：`REASONER_PROMPT` 明确禁止基于历史记忆进行 Ticker 替换，强制要求通过工具验证
3. **工具层**：`market_data_tool` 在 Ticker 查询失败时返回结构化的错误信息（含 `is_defunct_possible` 标记），引导模型重新推理
4. **交互层**：Reasoner 可输出 `type: "clarification"` 类型的决策，暂停执行并向用户确认实体指向

### 7. 异步工具调度与事件循环安全

**问题**：工具集中混合了同步函数（如 `yfinance` 的网络请求、`calculator` 的纯计算）和异步函数（如 `web_scraper` 的并发抓取）。在 FastAPI 的异步事件循环中直接调用同步阻塞函数会导致整个服务器挂起。

**方案**：在 `execute_tool()` 中实现了自动检测和调度：

```python
if asyncio.iscoroutinefunction(tool_func):
    return await tool_func(**args)          # 原生异步
else:
    return await asyncio.to_thread(tool_func, **args)  # 同步→线程池
```

通过 `asyncio.to_thread` 将同步工具（如 `market_data_tool`、`calculator_tool`）卸载到线程池执行，避免阻塞事件循环，同时保持了统一的 `async/await` 调用接口。

---

## 项目结构

```
EZInvest/
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── graph.py          # ReAct 循环引擎（核心）
│   │   │   ├── prompts.py        # System / Reasoner / Summarize 提示词
│   │   │   ├── state.py          # Agent 状态定义
│   │   │   ├── llm.py            # LLM Provider 工厂（DeepSeek/OpenAI/Ollama）
│   │   │   └── tools/
│   │   │       ├── market_data.py   # yfinance 实时行情（重试+降级）
│   │   │       ├── web_scraper.py   # 联网搜索→抓取→分块→入库
│   │   │       ├── retriever.py     # 混合检索工具封装
│   │   │       ├── calculator.py    # 确定性金融计算器
│   │   │       └── sentiment.py     # FinBERT 情感分析
│   │   ├── rag/
│   │   │   ├── retriever.py      # 三路混合检索 + RRF + Rerank
│   │   │   ├── embedder.py       # BGE-large 向量编码
│   │   │   ├── reranker.py       # Cross-Encoder 精排
│   │   │   ├── pgvector_store.py # 动态向量存储（联网数据）
│   │   │   └── indexer.py        # 离线索引构建
│   │   ├── api/routes/
│   │   │   ├── chat.py           # SSE 流式 + REST 聊天接口
│   │   │   └── health.py         # 健康检查（含外部依赖探针）
│   │   ├── models/
│   │   │   └── finbert.py        # FinBERT 推理封装
│   │   ├── schemas/chat.py       # Pydantic 事件模型
│   │   ├── config.py             # 全局配置（pydantic-settings）
│   │   └── main.py               # FastAPI 应用入口
│   ├── scripts/
│   │   └── manage_config.py      # CLI 配置管理工具
│   ├── tests/                    # pytest 测试套件
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx    # 主聊天界面 + SSE 事件处理
│   │   │   ├── MessageBubble.tsx # 消息气泡（Markdown 渲染）
│   │   │   ├── PlanProgressView.tsx  # 执行计划进度条
│   │   │   ├── ToolCallCard.tsx  # 工具调用状态卡片
│   │   │   └── SentimentBadge.tsx    # 情感分析徽章
│   │   ├── lib/
│   │   │   ├── api.ts            # SSE 客户端 + 事件解析
│   │   │   └── store.ts          # Zustand 全局状态
│   │   └── app/                  # Next.js App Router
│   └── package.json
├── docker-compose.yml            # 多服务编排（含 vLLM/Ollama Profile）
├── data/indexes/                 # 预构建的 FAISS + BM25 索引
└── .env                          # 环境变量
```

---

## 未来演进方向

1. **引入 LangGraph 正式版**：将当前手写的 `while` 循环迁移至 LangGraph 的 `StateGraph`，获得原生的断点恢复、并行分支和可视化调试能力
2. **QLoRA 微调**：基于财报 Q&A 数据集对 Qwen2.5-7B 进行 LoRA 微调，提升模型在金融领域的专业性
3. **多 Agent 协作**：拆分为 Research Agent（调研）和 Analyst Agent（分析），通过消息总线协作
4. **会话记忆**：接入 Redis 或数据库实现跨会话记忆，支持用户追问和上下文关联

---

## 简历 / 投递一页纸

投递与面试话术、**全项目**总结与中英简历 bullet 见 [PROJECT_RESUME.zh.md](./PROJECT_RESUME.zh.md)。
