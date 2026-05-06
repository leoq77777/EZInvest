# EZInvest — 分层 Benchmark（低成本路线图）

核心理念：**用确定性「能力点验」替代昂贵的开放式端到端研报评测**（与路由 mock 互不矛盾：mock 只管 HTTP 骨架延迟；本篇管「Agent 是否真的会用工具 / RAG 是否召回对」）。

与仓库根目录 [BENCHMARK.md](../BENCHMARK.md) 的关系：

| 文档 | 侧重点 |
|------|--------|
| `BENCHMARK.md` | HTTP **mock/live**、`eval/run_agent_benchmark.py`、已记录的 **路由基线毫秒数** |
| `benchmark/`（本目录） | **工具 / RAG / 决策核心** 分层评测的设计与扩展位 |

---

## 目录规划（逐步实现）

```text
benchmark/
├── README.md              # 本文件
├── run_benchmark.py       # 聚合运行「已实现」的子集（见脚本内说明）
├── fixtures/              # 固定语料、黄金查询、agent case yaml 等（待扩充）
├── test_tools/            # 可选：与 backend 分离的工具专项（当前可沿用 backend/tests）
├── test_rag/              # 可选：Recall@K / MRR 等（待 small corpus）
└── test_agent_core/       # 可选：只测 Reasoner JSON，阻断工具执行（待解耦钩子）
```

**当前已实现（零/cloud LLM 成本）：**  
`backend/tests/test_tools.py`（计算器 FinBERT Sentiment、`test_agent.py` 里部分工具链路）已通过本地 pytest，可作为**第一层工具层**的起点。

---

## 三层对照

### 第一层：工具层确定性（成本 ≈ 0）

- 计算器、结构化行情字段、FinBERT 例句标签等——**断言具体字段/数值区间**，不测「研报写得好不好」。  
- 实现位置：优先继续放在 `backend/tests/`，或通过 `fixtures/` + 本目录测试文件逐步迁移。

### 第二层：RAG 检索（成本 ≈ 0，不含生成）

- `fixtures/corpus/` 放短文 + `query ↔ 黄金 chunk id`；只跑 HybridRetriever → Recall@K / MRR，**不调 LLM**。

### 第三层：Agent 决策核心（成本可控）

- 对「下一轮该调哪个工具、参数是否合理」做单步 **JSON 断言**（需能从 `graph` 中单抽 **Reasoner/规划一步** 或 recording fixture）。  
- 用小而固定的 case  YAML（类似你文档里的 `agent_cases.yaml`），**每条 case  ideally 触发有限次 LLM 调用**（若暂无法阻断后续步，则用 mock LLM + 录制 golden）。

---

## 运行入口

```bash
# 从仓库根目录
python benchmark/run_benchmark.py

# 或照常只跑后端单测（工具层已实现部分）
cd backend && source .venv/bin/activate && PYTHONPATH=. pytest tests/test_tools.py tests/test_agent.py -q
```

扩展本目录测试后，把新路径加入 `run_benchmark.py` 的 subprocess 列表即可。
