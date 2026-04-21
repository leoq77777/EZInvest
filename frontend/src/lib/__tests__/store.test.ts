/**
 * Zustand store unit tests – runs in pure Node.js, no browser needed.
 *
 * Tests the entire message lifecycle: add → stream → tool calls → finalize.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useChatStore } from "../store";

// Polyfill for Node.js
if (typeof crypto === "undefined") {
  Object.defineProperty(globalThis, "crypto", {
    value: { randomUUID: () => "test-uuid-" + Math.random().toString(36).slice(2) },
  });
}

describe("ChatStore", () => {
  beforeEach(() => {
    useChatStore.getState().clearMessages();
  });

  it("starts with empty messages", () => {
    const { messages } = useChatStore.getState();
    expect(messages).toHaveLength(0);
  });

  it("adds a user message", () => {
    useChatStore.getState().addUserMessage("What is AAPL price?");
    const { messages } = useChatStore.getState();

    expect(messages).toHaveLength(1);
    expect(messages[0].role).toBe("user");
    expect(messages[0].content).toBe("What is AAPL price?");
    expect(messages[0].id).toBeTruthy();
    expect(messages[0].timestamp).toBeGreaterThan(0);
  });

  it("starts an assistant message and returns its id", () => {
    const msgId = useChatStore.getState().startAssistantMessage();
    const { messages } = useChatStore.getState();

    expect(msgId).toBeTruthy();
    expect(messages).toHaveLength(1);
    expect(messages[0].role).toBe("assistant");
    expect(messages[0].content).toBe("");
    expect(messages[0].toolCalls).toEqual([]);
  });

  it("appends tokens to an assistant message", () => {
    const msgId = useChatStore.getState().startAssistantMessage();
    useChatStore.getState().appendToken(msgId, "Hello");
    useChatStore.getState().appendToken(msgId, " world");

    const msg = useChatStore.getState().messages[0];
    expect(msg.content).toBe("Hello world");
  });

  it("does not modify other messages when appending", () => {
    useChatStore.getState().addUserMessage("question");
    const msgId = useChatStore.getState().startAssistantMessage();
    useChatStore.getState().appendToken(msgId, "answer");

    const { messages } = useChatStore.getState();
    expect(messages[0].content).toBe("question");
    expect(messages[1].content).toBe("answer");
  });

  it("adds and updates tool calls", () => {
    const msgId = useChatStore.getState().startAssistantMessage();

    useChatStore.getState().addToolCall(msgId, {
      tool: "retriever",
      status: "running",
      query: "NVDA earnings",
    });

    let msg = useChatStore.getState().messages[0];
    expect(msg.toolCalls).toHaveLength(1);
    expect(msg.toolCalls![0].status).toBe("running");

    useChatStore.getState().updateToolCall(msgId, "retriever", {
      status: "done",
      result: { text: "revenue was $18B" },
    });

    msg = useChatStore.getState().messages[0];
    expect(msg.toolCalls![0].status).toBe("done");
    expect(msg.toolCalls![0].result).toEqual({ text: "revenue was $18B" });
  });

  it("finalizes a message with latency", () => {
    useChatStore.getState().setStreaming(true);
    const msgId = useChatStore.getState().startAssistantMessage();

    useChatStore.getState().finalizeMessage(msgId, 1234.5);

    const { messages, isStreaming } = useChatStore.getState();
    expect(messages[0].latencyMs).toBe(1234.5);
    expect(isStreaming).toBe(false);
  });

  it("clearMessages resets state with new session", () => {
    useChatStore.getState().addUserMessage("test");
    const oldSession = useChatStore.getState().sessionId;

    useChatStore.getState().clearMessages();

    const { messages, sessionId } = useChatStore.getState();
    expect(messages).toHaveLength(0);
    expect(sessionId).not.toBe(oldSession);
  });

  it("sets and updates plan steps", () => {
    const msgId = useChatStore.getState().startAssistantMessage();

    useChatStore.getState().setPlan(msgId, [
      { id: "s1", description: "Get AAPL price", tool: "market_data", status: "pending" },
      { id: "s2", description: "Analyze sentiment", tool: "sentiment_analyzer", status: "pending" },
    ]);

    let msg = useChatStore.getState().messages[0];
    expect(msg.plan).toHaveLength(2);
    expect(msg.plan![0].status).toBe("pending");

    useChatStore.getState().updateStep(msgId, "s1", { status: "running" });
    msg = useChatStore.getState().messages[0];
    expect(msg.plan![0].status).toBe("running");

    useChatStore.getState().updateStep(msgId, "s1", {
      status: "done",
      result: "price is $185",
      latencyMs: 500,
    });
    msg = useChatStore.getState().messages[0];
    expect(msg.plan![0].status).toBe("done");
    expect(msg.plan![0].result).toBe("price is $185");
    expect(msg.plan![0].latencyMs).toBe(500);

    expect(msg.plan![1].status).toBe("pending");
  });

  it("sets and clears summarizing state", () => {
    const msgId = useChatStore.getState().startAssistantMessage();

    useChatStore.getState().setSummarizing(msgId, true);
    expect(useChatStore.getState().messages[0].isSummarizing).toBe(true);

    useChatStore.getState().finalizeMessage(msgId, 3000);
    expect(useChatStore.getState().messages[0].isSummarizing).toBe(false);
  });

  it("simulates a complete chat flow", () => {
    const store = useChatStore.getState();

    store.addUserMessage("Analyze NVDA sentiment");
    store.setStreaming(true);
    const msgId = store.startAssistantMessage();

    store.addToolCall(msgId, { tool: "retriever", status: "running" });
    store.addToolCall(msgId, { tool: "sentiment_analyzer", status: "running" });

    store.updateToolCall(msgId, "retriever", { status: "done" });
    store.updateToolCall(msgId, "sentiment_analyzer", {
      status: "done",
      result: { label: "positive", score: 0.91 },
    });

    store.appendToken(msgId, "Based on the analysis, ");
    store.appendToken(msgId, "NVDA sentiment is positive.");

    store.finalizeMessage(msgId, 2100);

    const { messages, isStreaming } = useChatStore.getState();
    expect(messages).toHaveLength(2);
    expect(messages[1].content).toBe("Based on the analysis, NVDA sentiment is positive.");
    expect(messages[1].toolCalls).toHaveLength(2);
    expect(messages[1].latencyMs).toBe(2100);
    expect(isStreaming).toBe(false);
  });
});
