# EZInvest — 全项目总结 · 简历要点

面向「要写进简历 / 作品集」的**一页纸**：覆盖**整条产品线**（Agent、检索、工具链、前端、持久化与运行保障），不单指某次迭代。深挖实现见 [PROJECT.md](./PROJECT.md)；**可复现 benchmark（含 0-LLM mock 基线）**见 [BENCHMARK.md](./BENCHMARK.md)。

---

## 一、项目是做什么的

**EZInvest** 是一套端到端的 **AI 金融投研助手**：用户用自然语言提问，系统在 **ReAct 式多轮推理** 中调度多种工具（行情、混合检索、联网抓取与入库、计算器、舆情等），把观察结果累积后再生成 **结构化研报（Markdown）**；前端通过 **SSE** 实时展示思考过程、执行计划、工具状态、正文 token 与侧栏研报。

与「单次问答 + 单向 RAG」不同，本产品强调：**循环纠错、实体/标歧义消解、动态知识入库与再检索**，以及工程上的 **异步全链路、降级与可观测性**。

---

## 二、系统架构（自顶向下）

| 层级 | 内容 |
|:-----|:-----|
| **前端** | Next.js 15、React 19、Tailwind 4；**Zustand** 管理会话与流式事件；Markdown / GFM 渲染消息与研报；支持计划进度、工具调用卡片、可选诊断 SSE、会话列表与「实时投研报告」面板。 |
| **API** | FastAPI 异步：**/api/chat**（非流 + **SSE 流式**）、**/api/conversations**（Bootstrap、会话 CRUD、消息、研报、`commit-turn`）、**/api/memories**、**/api/profile_agent**；**/api/health** 对外部依赖探活。 |
| **Agent** | **LangChain Core + 自研 ReAct 循环**（`graph.py`）：JSON 决策协议（行动 / 澄清 / 结束），异步生成器对流输出 `thought`、`plan`、`step_update`、`tool_call`、`token`、`report`、`done` 等事件；**LLM 工厂**统一 DeepSeek / OpenAI / Ollama 等。 |
| **工具链** | `market_data`（yfinance，重试与多级价格兜底）、`retriever`（混合检索封装）、`web_scraper`（搜索→抓取→解析→分块→**pgvector 入库**）、`calculator`（确定性计算）、`sentiment`（FinBERT）。 |
| **RAG** | **FAISS（HNSW）+ BM25 + pgvector** 三路检索 → **RRF 融合** → **Cross-Encoder 精排**；pgvector 不可用时降级双路；**Redis** 可缓存检索结果。 |
| **数据与记忆** | **PostgreSQL**（会话、消息、`report_markdown`、可选用户画像/风格占位等）；分层 **memory_layers / turn_context** 组装提示词；可选 **长期 UserMemory**；后台 **session summarizer** 节流摘要其它会话。 |
| **域名规则** | **entity_resolution**：重大公司行为（如拆分上市）等对工具参数与检索查询做纠偏；**derive_conversation_title** 用于会话命名与保存时与研报对齐。 |
| **运行与交付** | **Docker Compose** 多 Profile（含本地/推理服务端场景）；`.env` / pydantic-settings 集中配置；**pytest**（Agent/API/Tools）、**Vitest**（前端 store 等）。 |

---

## 三、会话与落库交互（产品线的一部分）

默认流式 **`auto_persist_turn=false`**：一轮对话不落库直至用户在侧栏报告非空时点击 **保存**，由 **`POST .../commit-turn`** 单笔写入用户/助手消息、合并研报，并按报告正文 **覆盖推导会话标题**；自动化集成可传 **`auto_persist_turn: true`** 恢复「边流边写」行为。

---

## 四、简历一句话 Pitch（中英文可选）

- **中文**：端到端 AI 投研产品：**ReAct Agent + 三路混合 RAG（FAISS / BM25 / pgvector）+ RRF 与 Cross-Encoder 重排 + SSE 流式全栈**，含行情/爬虫/记忆/健康检查与可配置 LLM。  
- **English**: End-to-end **streaming AI equity research** stack: **ReAct agent**, **hybrid RAG with RRF + reranking**, **live tooling** (market data, scraper→vector DB, sentiment), and **production-minded** async APIs + persistence.

---

## 五、中文简历 Bullet Points（覆盖全项目，按需删减）

1. 独立交付 **全栈 AI 金融投研应用**：**FastAPI 异步后端** + **Next.js 15 / React 19** 前端，基于 **SSE** 推送思考链、计划、步骤、工具调用、正文 token 与侧栏 **Markdown 研报**，**Zustand** 细粒度更新避免整页重绘。  
2. 实现 **ReAct 循环 Agent**（`graph.py`）：多轮 **推理—行动—观察** 状态积累，JSON 决策驱动工具调度与可选 **clarification**；**AsyncGenerator** 对流输出事件，并与 **LangChain Core**、可切换的 **DeepSeek / OpenAI / Ollama** 等 LLM 后端集成。  
3. 设计 **三路混合检索管线**：**FAISS（BGE 向量）+ BM25 + PostgreSQL pgvector（动态网页块）**，**RRF 融合去重** 与 **BGE Cross-Encoder 精排**；实现 **pgvector 故障降级**、**Redis 检索缓存** 与可配置超时/索引路径。  
4. 落地 **联网投研数据闭环**：**DuckDuckGo 搜索 + httpx 并发抓取 + BeautifulSoup 清洗 + 滑动窗口分块**，写入 **DynamicVectorStore**，供后续 `retriever` 无感检索；与离线 SEC/财报索引协同。  
5. 工程化 **行情与工具执行**：`yfinance` **多级价格兜底**（盘中价优先）、重试与超时；在 `execute_tool` 中对同步工具使用 **`asyncio.to_thread`**，避免阻塞事件循环；封装 **FinBERT** 金融情感与确定性 **calculator**。  
6. 构建 **领域鲁棒性**：**SYSTEM/REASONER 提示词** 约束幻觉与过时标的；**entity_resolution** 对重大公司行为做工具层纠偏；市场工具失败时 **结构化错误** 引导再推理。  
7. 负责 **数据与记忆层**：PostgreSQL **会话/消息/研报**、Bootstrap 与列表 API、**显式 commit-turn 落库**、**分层记忆注入**、可选 **UserMemory**、后台 **其它会话摘要** 节流任务；**Vitest + Pytest** 覆盖 API、Agent 流与工具关键路径。  
8. 关注 **可运维与联调**：**Health 路由** 探活 Redis/LLM/行情等；SSE **保活/超时/诊断事件**；环境变量驱动 **会话库、记忆、流式诊断**；Docker Compose **多 Profile** 编排。

---

## 六、English Resume Bullets (full project)

1. Shipped a **full-stack AI equity research assistant**: async **FastAPI** + **Next.js/React** UI with **SSE** streaming (thoughts, plans, tool calls, tokens, live Markdown report) and **Zustand** state management.  
2. Built a **ReAct-style agent loop** with **LangChain Core**, streaming **AsyncGenerator** events, JSON tool decisions, and **pluggable LLM providers** (DeepSeek/OpenAI/Ollama).  
3. Implemented **hybrid RAG**: **FAISS + BM25 + pgvector**, **RRF fusion**, **cross-encoder reranking**, **Redis caching**, and **graceful fallback** when dynamic vector DB is unavailable.  
4. Automated a **web research pipeline**: search → fetch → parse → chunk → **pgvector indexing** for fresh corpora alongside offline financial indexes.  
5. Hardened **market data + tool execution**: **intraday price fallbacks**, retries/timeouts, and **async/thread offloading** for blocking tools; added **FinBERT sentiment** and a deterministic **calculator** tool.  
6. Added **domain safeguards**: prompt-level grounding, **entity-resolution** guardrails, and structured tool errors to drive self-correction.  
7. Delivered **persistence & memory**: PostgreSQL conversations/messages/reports, layered prompt context, optional long-term memories, **explicit save/commit** API, background summarization hooks, and **pytest/vitest** coverage.  
8. Improved **operability**: dependency **health checks**, SSE keepalive/diagnostics, env-driven feature flags, and **Docker Compose** profiles for local inference stacks.

---

## 七、面试「按图索骥」

| 话题 | 代码入口 |
|:-----|:---------|
| ReAct 与流式事件 | `backend/app/agent/graph.py` |
| LLM 工厂 | `backend/app/agent/llm.py` |
| 提示词与实体 | `backend/app/agent/prompts.py`，`backend/app/agent/entity_resolution.py` |
| 混合 RAG | `backend/app/rag/retriever.py`，`pgvector_store.py`，`reranker.py` |
| SSE 与持久化策略 | `backend/app/api/routes/chat.py`，`conversations.py` |
| 记忆与会话摘要 | `backend/app/services/memory_layers.py`，`turn_context.py`，`session_summarizer.py`，`chat_persist.py` |
| 前端流式与 UI | `frontend/src/components/ChatWindow.tsx`，`frontend/src/lib/api.ts`，`store.ts` |
| 健康检查 | `backend/app/api/routes/health.py` |

祝投递顺利。
