"use client";

import { useRef, useEffect, useState, FormEvent } from "react";
import { Send, Trash2 } from "lucide-react";
import { useChatStore } from "@/lib/store";
import {
  streamChat,
  StreamEvent,
  ToolCallEvent,
  PlanEventData,
  StepUpdateData,
  toPlanSteps,
} from "@/lib/api";
import { MessageBubble } from "./MessageBubble";

const EXAMPLE_QUERIES = [
  "How did NVIDIA perform in its latest earnings?",
  "What's the current sentiment on Tesla stock?",
  "Compare the P/E ratios of AAPL and MSFT",
  "Is now a good time to invest in semiconductor ETFs?",
];

export function ChatWindow() {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const {
    messages,
    sessionId,
    isStreaming,
    addUserMessage,
    startAssistantMessage,
    appendToken,
    addToolCall,
    updateToolCall,
    setPlan,
    updateStep,
    setSummarizing,
    finalizeMessage,
    setStreaming,
    clearMessages,
  } = useChatStore();

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;

    setInput("");
    addUserMessage(trimmed);
    setStreaming(true);

    const msgId = startAssistantMessage();

    try {
      await streamChat(trimmed, sessionId, (event: StreamEvent) => {
        switch (event.type) {
          case "plan": {
            const planData = event.data as PlanEventData;
            setPlan(msgId, toPlanSteps(planData));
            break;
          }
          case "step_update": {
            const su = event.data as StepUpdateData;
            updateStep(msgId, su.step_id, {
              status: su.status,
              result: su.result,
              latencyMs: su.latency_ms,
            });
            break;
          }
          case "summarizing": {
            setSummarizing(msgId, true);
            break;
          }
          case "tool_call": {
            const tc = event.data as ToolCallEvent;
            if (tc.status === "running") {
              addToolCall(msgId, {
                tool: tc.tool,
                status: "running",
                query: tc.query,
              });
            } else {
              updateToolCall(msgId, tc.tool, {
                status: tc.status as "done" | "error",
                result: tc.result,
              });
            }
            break;
          }
          case "token": {
            const { content } = event.data as { content: string };
            appendToken(msgId, content);
            break;
          }
          case "done": {
            const { total_latency_ms } = event.data as {
              total_latency_ms: number;
            };
            finalizeMessage(msgId, total_latency_ms);
            break;
          }
        }
      });
    } catch {
      appendToken(
        msgId,
        "\n\n⚠️ Connection error. Please check that the backend is running.",
      );
      setStreaming(false);
    }
  };

  const handleExampleClick = (query: string) => {
    setInput(query);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[var(--color-accent)] flex items-center justify-center font-bold text-white text-sm">
            EZ
          </div>
          <div>
            <h1 className="text-base font-semibold">EZInvest</h1>
            <p className="text-xs text-[var(--color-text-muted)]">
              AI Investment Assistant
            </p>
          </div>
        </div>
        <button
          onClick={clearMessages}
          className="p-2 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] transition-colors"
          title="Clear chat"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </header>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-6 py-6 space-y-6"
      >
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-8 text-center">
            <div>
              <h2 className="text-2xl font-semibold mb-2">
                What would you like to know?
              </h2>
              <p className="text-[var(--color-text-muted)] text-sm">
                Ask about stocks, earnings, market sentiment, or financial
                metrics
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
              {EXAMPLE_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => handleExampleClick(q)}
                  className="text-left px-4 py-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-accent)] text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-[var(--color-border)]">
        <form onSubmit={handleSubmit} className="flex gap-3 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about any investment..."
            rows={1}
            disabled={isStreaming}
            className="flex-1 resize-none rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] px-4 py-3 text-sm placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="flex-shrink-0 w-11 h-11 rounded-xl bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors"
          >
            <Send className="w-4 h-4 text-white" />
          </button>
        </form>
        <p className="text-xs text-[var(--color-text-muted)] mt-2 text-center">
          EZInvest may produce inaccurate information. Not financial advice.
        </p>
      </div>
    </div>
  );
}
