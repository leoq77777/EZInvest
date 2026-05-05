#!/usr/bin/env python3
"""Smoke-test chat stream via Playwright (Chromium). Run dev on :3001 / backend :8080 first.

  .venv/bin/pip install playwright
  .venv/bin/playwright install chromium
  BASE_URL=http://127.0.0.1:3001 .venv/bin/python scripts/browser_smoke_stream.py

  若需验证控制台 “[EZInvest] stream POST ok…”，请先用 NEXT_PUBLIC_STREAM_DEBUG=1 启动前端
  （例如 `npm run dev:debug`），诊断不再通过页面勾选。
"""

from __future__ import annotations

import os
import sys

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:3001").rstrip("/")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Missing playwright. Run:\n"
            "  .venv/bin/pip install playwright\n"
            "  .venv/bin/playwright install chromium",
            file=sys.stderr,
        )
        return 2

    console_lines: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        def _on_console(msg) -> None:
            t = msg.type
            txt = msg.text
            line = f"[console.{t}] {txt}"
            console_lines.append(line)
            print(line, flush=True)

        page.on("console", _on_console)
        page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_load_state("networkidle", timeout=120_000)

        # Wait until chat textarea is usable (bootstrap done).
        page.wait_for_selector("textarea:not([disabled])", timeout=120_000)

        page.fill("textarea", "ping stream diagnostic")
        page.locator("form button[type=submit]").click()

        # Wait for either our client log or an assistant bubble / error text.
        page.wait_for_timeout(15_000)

        out = "/Users/leo/code/EZInvest/frontend/browser_smoke.png"
        page.screenshot(path=out, full_page=True)
        print(f"Screenshot: {out}", flush=True)

        body = page.locator("body").inner_text()
        ok_log = any("EZInvest] stream POST ok" in c for c in console_lines)
        print(f"console_has_stream_ok_log={ok_log}", flush=True)
        if "后端诊断" in body or "思考过程" in body or "ping stream" in body.lower():
            print("page_contains_expected_chat_ui=True", flush=True)
        else:
            print("page_contains_expected_chat_ui=False", flush=True)

        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
