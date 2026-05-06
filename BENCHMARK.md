# EZInvest — Benchmark 说明与记录

目标：用**尽量少的外部 LLM / 云 API 调用**得到可写进简历或 PR 的**可复现数字**，并区分「纯路由开销」与「真实 Agent 端到端」。

**分层能力点验（推荐主叙事）**：顶层目录 [benchmark/README.md](./benchmark/README.md) 描述「工具层 / RAG / 决策核心」低成本方案；`/api/chat` 的 mock 仅是**附录式路由基线**，两者目标不同。

---

## 0. 为何 live（真实 HTTP）会超时 / 断连？mock 设计不合理吗？

**不是。** 两类评测回答的是完全不同的问题：

| 类型 | 会卡在哪里 |
|------|------------|
| **mock（`eval/run_agent_benchmark.py --mode mock`）** | 不应依赖外网 LLM：对 `run_agent` 等打 patch，只量 FastAPI/Pydantic/JSON。**若 mock 变慢，多半是进程/GC 抖动，而非「方案错误」。** |
| **live HTTP `/api/chat`** | 走的是**完整 ReAct**：多轮 **LLM** + RAG/embed + 可选 yfinance / 爬虫等。**整体耗时常远大于** 客户端设的 120s/300s → `ReadTimeout`。**断连**常见原因包括：后端单 worker 在长推理时被代理/客户端闲置掐断、`LLM_HTTP` 报错导致连接异常关闭、本地 Ollama/vLLM 未就绪或过载、`LLM_TIMEOUT_SEC` 与客户端 timeout 不匹配、环境里 **HTTP/SOCKS 代理**干扰 `httpx` 等。 |

因此：**超时/断连反映的是「端到端链路长 + 环境不稳定」**，不是用来否定 mock。**要在有限预算下写简历数字，应主力采用 [benchmark/](benchmark/) 分层点验**，而不是强求「几条开放式研报 live 成功率/P50」。

---

## 1. 两种模式（务必分清）

| 模式 | 命令 | 外部 LLM HTTP 调用 | 测的是什么 |
|------|------|-------------------|------------|
| **mock**（推荐日常跑） | 见下节 | **0** | `POST /api/chat` 在 **patch 掉** `assemble_memory_layers`、`load_dialogue_and_report`、`run_agent` 后的耗时：FastAPI 路由 + Pydantic + JSON 序列化等**基线**，不含 RAG / 工具 / LLM。 |
| **live** | 见下节 | **每个 HTTP 请求 1 次**；**单次请求内部**仍会有 ReAct 多轮 **多次** chat-completions（无法从脚本精确计数，与迭代/工具数相关） | 真实端到端：会打满行情、检索、LLM 等；**费钱费时**，请把 `--max-queries` 设为 **1** 并加大 `--timeout`。 |

---

## 2. 如何运行

在仓库根目录或 `backend` 下均可；需已安装后端依赖（`backend/.venv`）。

```bash
cd backend
source .venv/bin/activate   # Windows: .venv\Scripts\activate
export PYTHONPATH=.

# 默认 mock：100 轮，无 LLM 费用
python eval/run_agent_benchmark.py --mode mock --runs 100 --quiet

# 真实端到端（慎用：消耗 LLM；建议只跑 1 条）
python eval/run_agent_benchmark.py --mode live --url http://127.0.0.1:8080 \
  --max-queries 1 --timeout 600 --quiet
```

历史脚本 `eval/run_latency.py` 仍可对**真实** `/api/chat` 做多条样例压测（**每条都会调 Agent**），默认 `timeout=30` 偏短，长任务请自行改大。

---

## 3. 已记录结果（mock，可复现）

**环境（一次典型本地运行）**

- 日期：**2026-05-06**
- 命令：`PYTHONPATH=. python eval/run_agent_benchmark.py --mode mock --runs 100 --quiet`
- 说明：**不访问** Redis / Postgres / 向量库 / LLM；仅进程内 ASGI。

**结果（毫秒）**

| 指标 | 数值 |
|------|------|
| n | 100 |
| mean | **1.065** |
| p50 | **0.868** |
| p95 | **1.307** |
| min | 0.784 |
| max | 15.314 |

**简历可写（示例句）**

- 「在无外部依赖的 mock 基线下，`POST /api/chat` 路由层 **P50 ≈ 0.87 ms / P95 ≈ 1.31 ms`（`n=100`，见仓库 `BENCHMARK.md`）。」

---

## 4. 真实端到端（live）探测备忘

在同一开发机上曾用 **3 条**问题、`httpx` **120s** 超时对 `http://127.0.0.1:8080/api/chat` 做快速探测：**1 条连接异常，2 条读超时**，故 **HTTP 成功率 0%**（不代表实现错误，多与当时 LLM 响应时间、代理、后端负载有关）。

**结论**：端到端 **P50 / 成功率** 请在你本机 LLM 稳定后，用 `--mode live --max-queries 1 --timeout 600` 重跑，把 JSON 输出贴回本节替换。

---

## 5. LLM「调用次数」怎么对外说

- **mock**：对外部 LLM **0 次**（无网络 chat 调用）。
- **live**：脚本只发起 **`max-queries` 次 HTTP**；每次 `/api/chat` 内部 = **多轮 ReAct × 每轮至少 1 次 LLM** + 工具侧可能触发的嵌入/重排（本地 HF，一般**不计入**云 LLM bill，但占 CPU/GPU）。简历里建议写：**「单次用户请求对应 1 次对话 API；内部多步推理」**，避免声称「只有 1 次 LLM」。

---

## 6. 维护

更新第三节表格时，请同时更新命令与日期，便于面试核对。
