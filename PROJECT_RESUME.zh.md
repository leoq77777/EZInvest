# EZInvest — 推送说明 · 简历要点

面向「要写进简历 / 作品集」场景的**一页纸总结**。技术细节见仓库根目录 [PROJECT.md](./PROJECT.md)。

---

## 一、最近一次功能摘要（可追溯）

以下为近期合并进主线的代表性能力（含「显式保存再落库」等交互变更）：

- **会话落库模型**：`/api/chat/stream` 默认 `auto_persist_turn=false`，对话与报告不再随流自动写入数据库；用户在侧栏报告非空时点击 **保存**，调用 `POST /api/conversations/{id}/commit-turn` 单笔事务写入用户消息、助手消息、合并研报，并可选写入长期记忆。
- **会话标题与报告对齐**：保存时用报告正文截取 + `derive_conversation_title()`（标的/代码推断与 `crud._title_from_message` 一致）**覆盖更新** `Conversation.title`，侧栏会话名与报告中的金融标的一致。
- **前端**：面板文案「实时投研报告」、`LiveReportPanel` 条件展示「保存」、`streamChat` 显式 `autoPersistTurn: false`、`commitConversationTurn` API 封装、流结束后 `pendingTurnSave` 草稿态与刷新 hydrate。
- **兼容**：自动化或旧客户端若需流式过程自动持久化，请求体仍需传 **`"auto_persist_turn": true`**。

---

## 二、项目在简历里的一句话pitch（可选）

端到端 AI 金融投研助手：**ReAct 多轮推理 + 混合 RAG（稠密 / 稀疏 / 动态向量库）+ SSE 流式 UI**，配套 PostgreSQL 会话记忆、研报面板与可控落库——适合强调 **Agent、检索工程、全栈与生产化意识**。

---

## 三、中文简历 Bullet Points（直接粘贴后按需删改）

- 独立设计并实现 **端到端 AI 金融投研产品**：FastAPI 异步后端 + Next.js/React 前端，**SSE** 推送思考链、工具状态、令牌与研报事件，前端 **Zustand** 驱动的流式会话与研报面板。
- 实现基于 **LangChain Core** 的自研 **ReAct 循环**：推理—工具调度—观察回流，集成行情（yfinance）、混合检索（FAISS + BM25）、网页抓取 pipeline、可选 **FinBERT** 情感分类等工具，并通过配置切换 **DeepSeek / OpenAI / Ollama** 等推理后端。
- 搭建 **三级混合检索链路**：离线向量（FAISS）与稀疏检索（BM25）、**PostgreSQL pgvector** 动态入库**，**RRF 融合 + Cross-Encoder 重排序**，显著提升金融长文档场景的召回精度与可读引用。
- 负责 **会话与记忆持久化**：多表模型、Bootstrap/会话列表、`commit-turn` 显式入库、标题从研报正文 **确定性推导**，并接入后台会话摘要钩子；补齐 **Vitest / Pytest**，覆盖 API 与用户态关键路径。
- 关注 **可靠性**：SSE 超时与空闲保活策略、并行工具阶段的 async 语义（避免不当 cancel）、数据库就绪门控与环境变量驱动的诊断/会话库开关，降低联调与环境差异成本。

---

## 四、English resume bullets（optional）

- Built an **end-to-end AI equity research assistant** with an async **FastAPI** backend and **Next.js/React** UI, streaming multi-phase agent output (**SSE**) including reasoning, tool progress, tokens, and a live Markdown research report pane.
- Implemented a **ReAct-style agent loop** (reason → act → observe) with modular tools (**market data, hybrid retrieval, scraping, sentiment, calculator**), grounding/entity safeguards, and pluggable LLM backends.
- Delivered **hybrid retrieval + reranking**: FAISS dense search, BM25 sparse search, pgvector-backed dynamic corpora, **RRF fusion**, and cross-encoder **reranking** for production-grade RAG quality.
- Designed **PostgreSQL-backed persistence**: explicit “save-to-DB” commit for each turn aligned with merged report updates, deterministic **conversation titles** derived from report text, background session summarization hooks, and automated **pytest/vitest** coverage for critical APIs and client state.

---

## 五、面试时可展开的「证据链」（自行对照仓库）

| 话题 | 可指到的位置 |
|:-----|:-------------|
| Agent 拓扑与事件 | `backend/app/agent/graph.py`，SSE：`backend/app/api/routes/chat.py` |
| 混合检索 | `backend/app/rag/retriever.py`、`pgvector_store.py`、`reranker.py` |
| 显式落库与标题 | `backend/app/api/routes/conversations.py`，`backend/app/services/chat_persist.py`，`backend/app/agent/entity_resolution.py` |
| 前端流式与会话 UI | `frontend/src/components/ChatWindow.tsx`，`frontend/src/lib/api.ts` |

祝投递顺利。
