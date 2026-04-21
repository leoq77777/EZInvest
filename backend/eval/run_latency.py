"""End-to-end latency benchmark for the agent pipeline.

Usage:
    python eval/run_latency.py --url http://localhost:8080 --runs 20
"""

import argparse
import asyncio
import statistics
import time

import httpx


SAMPLE_QUERIES = [
    "What was NVIDIA's revenue last quarter?",
    "Analyze the sentiment of Apple's latest earnings call",
    "Calculate the P/E ratio for MSFT at $420 with EPS of $12.5",
    "What's the current stock price of AAPL?",
    "Compare Tesla and BYD financial performance",
]


async def benchmark_single(client: httpx.AsyncClient, url: str, query: str) -> float:
    start = time.perf_counter()
    response = await client.post(
        f"{url}/api/chat",
        json={"message": query, "stream": False},
        timeout=30.0,
    )
    elapsed = (time.perf_counter() - start) * 1000
    response.raise_for_status()
    return elapsed


async def run_benchmark(url: str, runs: int):
    print(f"Benchmarking {url} with {runs} runs per query...\n")

    async with httpx.AsyncClient() as client:
        all_latencies = []

        for query in SAMPLE_QUERIES:
            latencies = []
            for _ in range(runs):
                try:
                    lat = await benchmark_single(client, url, query)
                    latencies.append(lat)
                except Exception as e:
                    print(f"  ERROR: {e}")

            if latencies:
                p50 = statistics.median(latencies)
                p95 = sorted(latencies)[int(len(latencies) * 0.95)]
                mean = statistics.mean(latencies)
                print(f"Query: {query[:50]}...")
                print(f"  Mean: {mean:.0f}ms | P50: {p50:.0f}ms | P95: {p95:.0f}ms | N={len(latencies)}")
                all_latencies.extend(latencies)

        if all_latencies:
            print(f"\n{'='*60}")
            print(f"OVERALL ({len(all_latencies)} requests)")
            print(f"  Mean: {statistics.mean(all_latencies):.0f}ms")
            print(f"  P50:  {statistics.median(all_latencies):.0f}ms")
            p95 = sorted(all_latencies)[int(len(all_latencies) * 0.95)]
            print(f"  P95:  {p95:.0f}ms")
            print(f"  Min:  {min(all_latencies):.0f}ms")
            print(f"  Max:  {max(all_latencies):.0f}ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Latency benchmark")
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.url, args.runs))
