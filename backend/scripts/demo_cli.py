#!/usr/bin/env python3
"""EZInvest CLI — Interactive demo client with plan-execute-summarize display.

Connects to the FastAPI backend via SSE streaming, showing:
  1. The research plan (decomposed steps)
  2. Real-time step execution progress
  3. Streaming investment report

Usage:
    python scripts/demo_cli.py
    python scripts/demo_cli.py --url http://localhost:8080
    python scripts/demo_cli.py --query "Analyze NVIDIA as an investment"
"""

import argparse
import json
import sys
import time

import httpx

TOOL_ICONS = {
    "retriever": "\U0001f50d",
    "sentiment_analyzer": "\U0001f4ca",
    "calculator": "\U0001f9ee",
    "market_data": "\U0001f4c8",
}

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
RESET = "\033[0m"


def print_banner():
    print(f"""
{BOLD}{CYAN}\u2554{'═'*42}\u2557
\u2551         EZInvest CLI Demo                \u2551
\u2551    AI Investment Consulting Assistant    \u2551
\u255a{'═'*42}\u255d{RESET}
""")


def stream_chat(url: str, message: str):
    """Send a message and stream the Plan-Execute-Summarize response."""
    print(f"{DIM}Sending to {url}/api/chat/stream ...{RESET}\n")
    start = time.time()
    plan_steps = {}  # step_id -> {description, tool}
    step_count = 0
    token_started = False

    with httpx.stream(
        "POST",
        f"{url}/api/chat/stream",
        json={"message": message, "stream": True},
        timeout=300.0,
    ) as response:
        if response.status_code != 200:
            print(f"{BOLD}Error: HTTP {response.status_code}{RESET}")
            return

        current_event = ""

        for line in response.iter_lines():
            if line.startswith("event: "):
                current_event = line[7:].strip()
            elif line.startswith("data: ") and current_event:
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                if current_event == "plan":
                    steps = data.get("steps", [])
                    elapsed = time.time() - start
                    print(f"{BOLD}{CYAN}\u2501 Research Plan{RESET} {DIM}(generated in {elapsed:.1f}s){RESET}")
                    print(f"{CYAN}\u2500{'─'*49}{RESET}")
                    for i, s in enumerate(steps, 1):
                        sid = s.get("id", f"step_{i}")
                        desc = s.get("description", "")
                        tool = s.get("tool", "")
                        icon = TOOL_ICONS.get(tool, "\u2699\ufe0f")
                        plan_steps[sid] = {"description": desc, "tool": tool}
                        print(f"  {DIM}[{i}]{RESET} {icon} {desc}")
                    print(f"{CYAN}\u2500{'─'*49}{RESET}\n")

                elif current_event == "step_update":
                    step_id = data.get("step_id", "")
                    status = data.get("status", "")
                    step_info = plan_steps.get(step_id, {})
                    tool = step_info.get("tool", data.get("tool", ""))
                    icon = TOOL_ICONS.get(tool, "\u2699\ufe0f")

                    if status == "running":
                        step_count += 1
                        desc = step_info.get("description", step_id)
                        print(f"  {icon} {YELLOW}\u25b6{RESET} {desc}", end="", flush=True)

                    elif status == "done":
                        latency = data.get("latency_ms", 0)
                        print(f" {GREEN}\u2713{RESET} {DIM}({latency/1000:.1f}s){RESET}")

                    elif status == "error":
                        print(f" {MAGENTA}\u2717 error{RESET}")

                elif current_event == "summarizing":
                    print(f"\n{'─'*50}")
                    print(f"{BOLD}{CYAN}\U0001f4cb Investment Report{RESET}")
                    print(f"{'─'*50}\n")

                elif current_event == "token":
                    content = data.get("content", "")
                    if not token_started:
                        token_started = True
                    sys.stdout.write(content)
                    sys.stdout.flush()

                elif current_event == "tool_call":
                    tool = data.get("tool", "unknown")
                    status = data.get("status", "")
                    icon = TOOL_ICONS.get(tool, "\u2699\ufe0f")
                    if status == "running":
                        step_count += 1
                        query = data.get("query", "")
                        print(f"  {icon} {YELLOW}[Tool {step_count}]{RESET} {BOLD}{tool}{RESET}", end="")
                        if query:
                            print(f" {DIM}\u2014 {query[:80]}{RESET}")
                        else:
                            print()
                    elif status == "done":
                        result = data.get("result", "")
                        if isinstance(result, str) and len(result) > 120:
                            result = result[:120] + "..."
                        print(f"       {GREEN}\u2713 done{RESET} {DIM}{result}{RESET}")

                elif current_event == "done":
                    latency = data.get("total_latency_ms", 0)
                    print(f"\n\n{'─'*50}")
                    print(f"{DIM}Total latency: {latency/1000:.1f}s | Steps executed: {step_count}{RESET}")

                elif current_event == "error":
                    print(f"\n{BOLD}{MAGENTA}Error: {data.get('detail', 'unknown')}{RESET}")

                current_event = ""


def non_stream_chat(url: str, message: str):
    """Fallback: non-streaming request."""
    print(f"{DIM}Sending to {url}/api/chat ...{RESET}\n")

    response = httpx.post(
        f"{url}/api/chat",
        json={"message": message, "stream": False},
        timeout=300.0,
    )
    if response.status_code != 200:
        print(f"{BOLD}Error: HTTP {response.status_code}{RESET}")
        print(response.text)
        return

    data = response.json()

    tool_calls = data.get("tool_calls", [])
    if tool_calls:
        print(f"{BOLD}Tools Called:{RESET}")
        for tc in tool_calls:
            icon = TOOL_ICONS.get(tc.get("tool", ""), "\u2699\ufe0f")
            print(f"  {icon} {tc.get('tool', 'unknown')} \u2014 {tc.get('status', '')}")
        print()

    print(f"{'─'*50}")
    print(f"{BOLD}{CYAN}\U0001f4cb Investment Report{RESET}")
    print(f"{'─'*50}\n")
    print(data.get("answer", "(no answer)"))
    print(f"\n{'─'*50}")
    print(f"{DIM}Session: {data.get('session_id', 'N/A')}")
    print(f"Total latency: {data.get('total_latency_ms', 0)/1000:.1f}s{RESET}")


def interactive_loop(url: str, use_stream: bool):
    """Run an interactive chat loop."""
    print(f"{DIM}Type your investment question, or 'quit' to exit.{RESET}")
    print(f"{DIM}Examples:{RESET}")
    print(f"  \u2022 Analyze NVIDIA as an investment opportunity")
    print(f"  \u2022 What's the current AAPL stock price and PE ratio?")
    print(f"  \u2022 Compare Tesla's revenue growth to last year")
    print()

    while True:
        try:
            query = input(f"{BOLD}{GREEN}You \u25b6{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{DIM}Goodbye!{RESET}")
            break

        if not query or query.lower() in ("quit", "exit", "q"):
            print(f"{DIM}Goodbye!{RESET}")
            break

        print()
        if use_stream:
            stream_chat(url, query)
        else:
            non_stream_chat(url, query)
        print()


def main():
    parser = argparse.ArgumentParser(description="EZInvest CLI Demo")
    parser.add_argument("--url", default="http://localhost:8080", help="Backend URL")
    parser.add_argument("--query", type=str, default=None, help="Single query (non-interactive)")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming")
    args = parser.parse_args()

    print_banner()

    if args.query:
        if args.no_stream:
            non_stream_chat(args.url, args.query)
        else:
            stream_chat(args.url, args.query)
    else:
        interactive_loop(args.url, use_stream=not args.no_stream)


if __name__ == "__main__":
    main()
