import { create } from "zustand";
import { isSaveUserMessageAsMemoryEnabled } from "./runtimeConfig";

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
  /** Backend debug_stream lines: [ms] phase — detail */
  debugTrace?: string[];
  /** True when NEXT_PUBLIC_STREAM_DEBUG=1 (show panel even before first debug SSE). */
  diagnosticRequested?: boolean;
  toolCalls?: ToolCall[];
  plan?: PlanStep[];
  isSummarizing?: boolean;
  latencyMs?: number;
  timestamp: number;
}

export interface ServerMessageRow {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

interface ChatState {
  messages: Message[];
  sessionId: string;
  /** Stable browser identity for server-side history + memory */
  profileId: string;
  /** PostgreSQL conversation UUID when persistence is available */
  conversationId: string | null;
  persistenceReady: boolean;
  /** First bootstrap finished (DB on or off); avoids sending before profile_id is ready */
  bootstrapDone: boolean;
  rememberNextMessage: boolean;
  isStreaming: boolean;
  /** Merged investment report (markdown), updated each assistant turn */
  liveReportMarkdown: string;

  setProfileId: (id: string) => void;
  setConversationId: (id: string | null) => void;
  setPersistenceReady: (v: boolean) => void;
  setBootstrapDone: (v: boolean) => void;
  setRememberNextMessage: (v: boolean) => void;
  setLiveReport: (markdown: string) => void;
  hydrateFromServer: (rows: ServerMessageRow[]) => void;

  addUserMessage: (content: string) => void;
  startAssistantMessage: (opts?: { diagnostic?: boolean }) => string;
  appendToken: (msgId: string, token: string) => void;
  addToolCall: (msgId: string, toolCall: ToolCall) => void;
  updateToolCall: (msgId: string, tool: string, update: Partial<ToolCall>) => void;
  setPlan: (msgId: string, steps: PlanStep[]) => void;
  setThought: (msgId: string, thought: string) => void;
  /** Append one line to the assistant thought trace (multi-step reasoning). */
  appendThought: (msgId: string, line: string) => void;
  appendDebug: (msgId: string, line: string) => void;
  updateStep: (msgId: string, stepId: string, update: Partial<PlanStep>) => void;
  setSummarizing: (msgId: string, v: boolean) => void;
  finalizeMessage: (msgId: string, latencyMs: number) => void;
  setStreaming: (v: boolean) => void;
  /** Clears UI only; caller should create a new server conversation when DB is on */
  clearLocalMessages: () => void;
  /** New random session id for LLM request correlation */
  rotateSessionId: () => void;
}

let msgCounter = 0;
const newId = () => `msg-${++msgCounter}-${Date.now()}`;

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  sessionId: crypto.randomUUID(),
  profileId: "",
  conversationId: null,
  persistenceReady: false,
  bootstrapDone: false,
  rememberNextMessage: isSaveUserMessageAsMemoryEnabled(),
  isStreaming: false,
  liveReportMarkdown: "",

  setProfileId: (id) => set({ profileId: id }),
  setConversationId: (id) => set({ conversationId: id }),
  setPersistenceReady: (v) => set({ persistenceReady: v }),
  setBootstrapDone: (v) => set({ bootstrapDone: v }),
  setRememberNextMessage: (v) => set({ rememberNextMessage: v }),
  setLiveReport: (markdown) => set({ liveReportMarkdown: markdown }),

  hydrateFromServer: (rows) =>
    set({
      messages: rows.map((r) => ({
        id: `srv-${r.id}`,
        role:
          (r.role || "").toLowerCase() === "assistant" ? "assistant" : "user",
        content: r.content,
        timestamp: Date.parse(r.created_at) || Date.now(),
      })),
    }),

  addUserMessage: (content) =>
    set((s) => ({
      messages: [
        ...s.messages,
        { id: newId(), role: "user", content, timestamp: Date.now() },
      ],
    })),

  startAssistantMessage: (opts) => {
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
          debugTrace: [],
          diagnosticRequested: Boolean(opts?.diagnostic),
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

  appendThought: (msgId, line) =>
    set((s) => ({
      messages: s.messages.map((m) => {
        if (m.id !== msgId) return m;
        const prev = m.thought?.trim();
        const next = line.trim();
        if (!next) return m;
        return {
          ...m,
          thought: prev ? `${prev}\n\n${next}` : next,
        };
      }),
    })),

  appendDebug: (msgId, line) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === msgId
          ? { ...m, debugTrace: [...(m.debugTrace || []), line] }
          : m,
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

  clearLocalMessages: () => set({ messages: [], liveReportMarkdown: "" }),

  rotateSessionId: () => set({ sessionId: crypto.randomUUID() }),
}));
