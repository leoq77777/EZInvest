import { create } from "zustand";

export interface ToolCall {
  tool: string;
  status: "running" | "done" | "error";
  query?: string;
  result?: Record<string, unknown>;
}

export interface PlanStep {
  id: string;
  description: string;
  tool: string;
  status: "pending" | "running" | "done" | "error";
  result?: string;
  latencyMs?: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  thought?: string;
  toolCalls?: ToolCall[];
  plan?: PlanStep[];
  isSummarizing?: boolean;
  latencyMs?: number;
  timestamp: number;
}

interface ChatState {
  messages: Message[];
  sessionId: string;
  isStreaming: boolean;

  addUserMessage: (content: string) => void;
  startAssistantMessage: () => string;
  appendToken: (msgId: string, token: string) => void;
  addToolCall: (msgId: string, toolCall: ToolCall) => void;
  updateToolCall: (msgId: string, tool: string, update: Partial<ToolCall>) => void;
  setPlan: (msgId: string, steps: PlanStep[]) => void;
  setThought: (msgId: string, thought: string) => void;
  updateStep: (msgId: string, stepId: string, update: Partial<PlanStep>) => void;
  setSummarizing: (msgId: string, v: boolean) => void;
  finalizeMessage: (msgId: string, latencyMs: number) => void;
  setStreaming: (v: boolean) => void;
  clearMessages: () => void;
}

let msgCounter = 0;
const newId = () => `msg-${++msgCounter}-${Date.now()}`;

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  sessionId: crypto.randomUUID(),
  isStreaming: false,

  addUserMessage: (content) =>
    set((s) => ({
      messages: [
        ...s.messages,
        { id: newId(), role: "user", content, timestamp: Date.now() },
      ],
    })),

  startAssistantMessage: () => {
    const id = newId();
    set((s) => ({
      messages: [
        ...s.messages,
        {
          id,
          role: "assistant",
          content: "",
          toolCalls: [],
          plan: [],
          isSummarizing: false,
          timestamp: Date.now(),
        },
      ],
    }));
    return id;
  },

  appendToken: (msgId, token) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === msgId ? { ...m, content: m.content + token } : m,
      ),
    })),

  addToolCall: (msgId, toolCall) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === msgId
          ? { ...m, toolCalls: [...(m.toolCalls || []), toolCall] }
          : m,
      ),
    })),

  updateToolCall: (msgId, tool, update) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === msgId
          ? {
              ...m,
              toolCalls: (m.toolCalls || []).map((tc) =>
                tc.tool === tool ? { ...tc, ...update } : tc,
              ),
            }
          : m,
      ),
    })),

  setPlan: (msgId, steps) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === msgId ? { ...m, plan: steps } : m,
      ),
    })),

  setThought: (msgId, thought) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === msgId ? { ...m, thought } : m,
      ),
    })),

  updateStep: (msgId, stepId, update) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === msgId
          ? {
              ...m,
              plan: (m.plan || []).map((step) =>
                step.id === stepId ? { ...step, ...update } : step,
              ),
            }
          : m,
      ),
    })),

  setSummarizing: (msgId, v) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === msgId ? { ...m, isSummarizing: v } : m,
      ),
    })),

  finalizeMessage: (msgId, latencyMs) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === msgId ? { ...m, latencyMs, isSummarizing: false } : m,
      ),
      isStreaming: false,
    })),

  setStreaming: (v) => set({ isStreaming: v }),

  clearMessages: () =>
    set({ messages: [], sessionId: crypto.randomUUID() }),
}));
