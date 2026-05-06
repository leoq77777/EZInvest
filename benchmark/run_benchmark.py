#!/usr/bin/env python3
"""
Aggregate lowest-cost benchmarks from repo root.

Today: invokes existing backend pytest subsets (tools / agent mocks) — no LLM billing.
Tomorrow: add benchmark/test_rag, test_agent_core, etc., and extend the list below.

Usage (from EZInvest repo root):

    python benchmark/run_benchmark.py
    python benchmark/run_benchmark.py --verbose
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    pytest = [sys.executable, "-m", "pytest"]
    targets = [
        BACKEND / "tests" / "test_tools.py",
        BACKEND / "tests" / "test_agent.py",
    ]
    common = [*pytest, *[str(t) for t in targets]]
    if args.verbose:
        common.append("-v")
    else:
        common.extend(["-q", "--tb=line"])

    print("[benchmark] cwd:", ROOT)
    print("[benchmark] pytest:", " ".join(common))
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND)
    proc = subprocess.run(common, cwd=BACKEND, env=env)
    if proc.returncode != 0:
        return proc.returncode

    mock_bench = [sys.executable, "eval/run_agent_benchmark.py", "--mode", "mock", "--runs", "50", "--quiet"]
    print("[benchmark] route mock:", " ".join(mock_bench))
    mb = subprocess.run(mock_bench, cwd=BACKEND, env=env)
    return mb.returncode


if __name__ == "__main__":
    raise SystemExit(main())
