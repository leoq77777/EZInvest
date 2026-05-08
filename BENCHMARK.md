# EZInvest Benchmark Results

Last run: 2026-05-08

This document records the latest local end-to-end benchmark for EZInvest after adding the chat/research mode split and runtime warmup. The benchmark uses real `/api/chat` requests against the local dev stack; it does not rely on mocked LLM responses.

## Setup

- Backend: `http://127.0.0.1:8080`
- Frontend: `http://127.0.0.1:3001`
- Restart command: `./scripts/restart-dev.sh`
- LLM provider: DeepSeek via OpenAI-compatible API
- Measurement: wall-clock time from client request start to complete `/api/chat` JSON response
- Warmup: backend startup preloads the LLM client, RAG/embedding path, and FinBERT sentiment model

The final restart reached ready state in about 19.4 seconds with warmup enabled.

## Success Criteria

Chat mode is counted as successful when:

- HTTP status is `200`
- `answer` is non-empty
- `report_markdown` is empty, because chat mode should not generate reports

Research mode is counted as successful when:

- HTTP status is `200`
- `answer` is non-empty
- `report_markdown` is non-empty, meaning an end-to-end report was generated

## Results

| Mode | Runs | Success Rate | Avg Latency | P50 Latency | Report Generated |
|------|------|--------------|-------------|-------------|------------------|
| Chat | 3 | 100% | 2.64s | 2.18s | No |
| Research | 3 | 100% | 15.74s | 13.97s | Yes |

### Per-Run Latency

Chat mode:

- Run 1: 0.89s
- Run 2: 2.18s
- Run 3: 4.86s

Research mode:

- Run 1: 19.74s
- Run 2: 13.51s
- Run 3: 13.97s

## Interpretation

The mode split gives the product two distinct latency profiles:

- Chat mode is suitable for fast conversational answers and avoids RAG, tools, and report generation.
- Research mode keeps the full agent/report path and currently completes simple financial calculation reports in roughly 14-20 seconds after warmup.

The largest remaining cost in research mode is repeated LLM calls for planning, synthesis, and report drafting. Tool-call normalization now repairs common schema mistakes before execution, reducing wasted agent iterations for calculator, retriever/web scraper, and sentiment tool calls.

## Caveats

- Sample size is intentionally small (`n=3` per mode), so these numbers are directional rather than statistically rigorous.
- Results depend on external LLM latency and local model/cache state.
- Research prompts in this run were lightweight calculation/report tasks, not long multi-source market research requests.
- The benchmark was run against the local dev server, not a production deployment.
