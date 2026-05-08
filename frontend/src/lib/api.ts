import type { PlanStep } from "./store";

export interface ToolCallEvent {
  tool: string;
  status: "running" | "done" | "error";
  query?: string;
  result?: Record<string, unknown>;
  latency_ms?: number;
}

export interface PlanEventData {
  steps: { id: string; description: string; tool: string }[];
}

export interface StepUpdateData {
  step_id: string;
  status: "pending" | "running" | "done" | "error";
  result?: string;
  latency_ms?: number;
}

export type ChatMode = "chat" | "research";

export type StreamEventType =
  | "thought"
  | "plan"
  | "step_update"
  | "summarizing"
  | "tool_call"
  | "token"
  | "report"
  | "done"
  | "error"
  | "debug";

export interface StreamEvent {
  type: StreamEventType;
  data: unknown;
}

/** Classified failure for observability (LLM vs network vs stall). */
export type StreamChatFailureKind =
  | "user_abort"
  | "fetch_network"
  | "fetch_http"
  | "stream_total"
  | "stream_idle";

export class StreamChatError extends Error {
  readonly kind: StreamChatFailureKind;
  readonly lastDebugPhase?: string;

  constructor(
    kind: StreamChatFailureKind,
    message: string,
    lastDebugPhase?: string,
  ) {
    super(message);
    this.name = "StreamChatError";
    this.kind = kind;
    this.lastDebugPhase = lastDebugPhase;
  }
}

/** User-facing hint; pair with NEXT_PUBLIC_STREAM_DEBUG + backend_log. */
export function streamChatErrorHint(e: StreamChatError): string {
  const phase = e.lastDebugPhase
    ? `\n\n最后诊断阶段（需以 NEXT_PUBLIC_STREAM_DEBUG=1 启动前端才有）：「${e.lastDebugPhase}」`
    : "";
  switch (e.kind) {
    case "stream_idle":
      return `流式长时间无新数据（多为后端卡在 LLM、RAG 或数据库；少数为 Next 代理挂起）${phase}\n\n请查 backend/backend_log.txt，并确认 LLM 服务与 LLM_TIMEOUT_SEC；可调 NEXT_PUBLIC_STREAM_CHUNK_IDLE_MS。`;
    case "stream_total":
      return `超过浏览器整流总时限${phase}。可调大 NEXT_PUBLIC_STREAM_TOTAL_MS，或缩短单次 Agent 任务。`;
    case "fetch_network":
      return `无法连到 API（Next rewrites → 后端、或后端未监听、DNS/代理）\n${e.message}`;
    case "fetch_http":
      return `HTTP 错误：${e.message}`;
    case "user_abort":
      return e.message;
    default:
      return e.message;
  }
}

function _envInt(name: string, fallback: number): number {
  if (typeof process === "undefined" || !process.env) return fallback;
  const v = process.env[name];
  if (v == null || v === "") return fallback;
  const n = Number.parseInt(v, 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

function _mergeAbortSignals(signals: AbortSignal[]): AbortSignal {
  const anyFn = (
    AbortSignal as unknown as { any?: (s: AbortSignal[]) => AbortSignal }
  ).any;
  if (typeof anyFn === "function") {
    return anyFn(signals);
  }
  const c = new AbortController();
  for (const s of signals) {
    if (s.aborted) {
      c.abort(s.reason);
      return c.signal;
    }
    s.addEventListener("abort", () => c.abort(s.reason), { once: true });
  }
  return c.signal;
}

/**
 * In the browser, when `NEXT_PUBLIC_API_URL` is unset, use same-origin `/api/*` so
 * Next.js `rewrites` proxy to the backend and the browser never hits cross-origin CORS.
 * On the server (SSR), fall back to direct backend URL for any server-side fetches.
 */
function getApiBase(): string {
  const env = process.env.NEXT_PUBLIC_API_URL;
  if (typeof env === "string" && env.trim() !== "") {
    return env.replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    return "";
  }
  return "http://localhost:8080";
}

const PROFILE_STORAGE_KEY = "ezinvest_profile_id";

export function getOrCreateProfileId(): string {
  if (typeof window === "undefined") return "";
  let id = localStorage.getItem(PROFILE_STORAGE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(PROFILE_STORAGE_KEY, id);
  }
  return id;
}

export interface BootstrapResult {
  database_available: boolean;
  conversation_id: string | null;
  report_markdown?: string | null;
  messages: {
    id: string;
    role: string;
    content: string;
    created_at: string;
  }[];
}

/** Row from GET /api/conversations */
export interface ConversationRow {
  id: string;
  profile_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export async function bootstrapConversation(
  profileId: string,
): Promise<BootstrapResult> {
  const res = await fetch(`${getApiBase()}/api/conversations/bootstrap`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: profileId }),
  });
  if (!res.ok) {
    return {
      database_available: false,
      conversation_id: null,
      messages: [],
    };
  }
  return res.json() as Promise<BootstrapResult>;
}

export async function createConversation(
  profileId: string,
): Promise<{ id: string } | null> {
  const res = await fetch(`${getApiBase()}/api/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: profileId }),
  });
  if (!res.ok) return null;
  const data = await res.json();
  return { id: data.id };
}

export async function listConversations(
  profileId: string,
  limit = 30,
): Promise<ConversationRow[]> {
  const q = new URLSearchParams({
    profile_id: profileId,
    limit: String(limit),
  });
  const res = await fetch(`${getApiBase()}/api/conversations?${q}`);
  if (!res.ok) return [];
  return res.json() as Promise<ConversationRow[]>;
}

export async function fetchResearchReport(
  conversationId: string,
  profileId: string,
): Promise<string> {
  const q = new URLSearchParams({ profile_id: profileId });
  const res = await fetch(
    `${getApiBase()}/api/conversations/${encodeURIComponent(conversationId)}/research-report?${q}`,
  );
  if (!res.ok) return "";
  const data = (await res.json()) as { report_markdown?: string };
  return data.report_markdown || "";
}

export async function fetchConversationMessages(
  conversationId: string,
  profileId: string,
): Promise<
  { id: string; role: string; content: string; created_at: string }[]
> {
  const q = new URLSearchParams({ profile_id: profileId });
  const res = await fetch(
    `${getApiBase()}/api/conversations/${encodeURIComponent(conversationId)}/messages?${q}`,
  );
  if (!res.ok) return [];
  return res.json();
}

export interface CommitConversationTurnPayload {
  user_message: string;
  assistant_message: string;
  report_markdown: string;
  save_message_as_memory?: boolean;
}

export async function commitConversationTurn(
  conversationId: string,
  profileId: string,
  payload: CommitConversationTurnPayload,
): Promise<{ ok: boolean; conversation_title?: string | null }> {
  const res = await fetch(
    `${getApiBase()}/api/conversations/${encodeURIComponent(conversationId)}/commit-turn`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: profileId,
        user_message: payload.user_message,
        assistant_message: payload.assistant_message,
        report_markdown: payload.report_markdown,
        save_message_as_memory: Boolean(payload.save_message_as_memory),
      }),
    },
  );
  const text = await res.text();
  if (!res.ok) {
    throw new Error(text || res.statusText || `HTTP ${res.status}`);
  }
  try {
    return JSON.parse(text) as {
      ok: boolean;
      conversation_title?: string | null;
    };
  } catch {
    return { ok: true };
  }
}

export interface StreamChatOptions {
  mode?: ChatMode;
  profileId?: string;
  conversationId?: string | null;
  saveMessageAsMemory?: boolean;
  /**
   * When true, persist each stream turn automatically (legacy/tests).
   * Default false: user saves via commit-turn after streaming.
   */
  autoPersistTurn?: boolean;
  /** Ask backend for SSE `debug` events (phase + elapsed ms). */
  debugStream?: boolean;
  /** Abort to stop streaming (Stop button). */
  signal?: AbortSignal;
}

function _isAbortError(e: unknown): boolean {
  if (e instanceof DOMException && e.name === "AbortError") return true;
  if (e instanceof Error && e.name === "AbortError") return true;
  return false;
}

export async function streamChat(
  message: string,
  sessionId: string,
  onEvent: (event: StreamEvent) => void,
  opts?: StreamChatOptions,
): Promise<void> {
  const body: Record<string, unknown> = {
    message,
    session_id: sessionId,
    stream: true,
    mode: opts?.mode ?? "research",
  };
  if (opts?.profileId) body.profile_id = opts.profileId;
  if (opts?.conversationId) body.conversation_id = opts.conversationId;
  if (opts?.saveMessageAsMemory) body.save_message_as_memory = true;
  body.auto_persist_turn = Boolean(opts?.autoPersistTurn);
  // Always send explicit flag so FastAPI/Pydantic never relies on a missing field after hydration races.
  body.debug_stream = Boolean(opts?.debugStream);

  const userSignal = opts?.signal;
  const lastPhase = { current: "(尚未收到 debug 事件；卡在连接或首包)" };

  const wrapOnEvent = (ev: StreamEvent) => {
    if (ev.type === "debug") {
      const d = ev.data as { phase?: string };
      if (d?.phase) lastPhase.current = d.phase;
    }
    onEvent(ev);
  };

  const totalMs = _envInt("NEXT_PUBLIC_STREAM_TOTAL_MS", 600_000);
  const idleMs = _envInt("NEXT_PUBLIC_STREAM_CHUNK_IDLE_MS", 120_000);

  const totalCtrl = new AbortController();
  let totalWallFired = false;
  const totalTimer = setTimeout(() => {
    totalWallFired = true;
    totalCtrl.abort();
  }, totalMs);

  const combinedSignal = userSignal
    ? _mergeAbortSignals([userSignal, totalCtrl.signal])
    : totalCtrl.signal;

  let response: Response;
  try {
    try {
      response = await fetch(`${getApiBase()}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: combinedSignal,
      });
    } catch (e) {
      if (userSignal?.aborted) return;
      if (_isAbortError(e) && totalWallFired) {
        throw new StreamChatError(
          "stream_total",
          `整流超过 ${totalMs}ms`,
          lastPhase.current,
        );
      }
      if (_isAbortError(e)) return;
      const msg = e instanceof Error ? e.message : String(e);
      throw new StreamChatError(
        "fetch_network",
        msg || "fetch failed",
        lastPhase.current,
      );
    }

    if (!response.ok) {
      throw new StreamChatError(
        "fetch_http",
        `HTTP ${response.status}`,
        lastPhase.current,
      );
    }

    if (opts?.debugStream && typeof console !== "undefined") {
      console.info(
        "[EZInvest] stream POST ok; reading SSE（已请求 debug_stream，首帧应含 event: debug / route.handshake）",
      );
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new StreamChatError(
        "fetch_http",
        "No response body",
        lastPhase.current,
      );
    }

    const decoder = new TextDecoder();
    let buffer = "";
    /** SSE message may span multiple `data:` lines; blank line ends frame (RFC 8895). */
    let pendingEvent = "";
    const pendingDataLines: string[] = [];
    let lastActivity = Date.now();
    let idleKill = false;
    let idleCheckInterval: ReturnType<typeof setInterval> | undefined;
    let completedFullRead = false;

    const flushSseFrame = () => {
      if (!pendingEvent || pendingDataLines.length === 0) {
        pendingEvent = "";
        pendingDataLines.length = 0;
        return;
      }
      const payload = pendingDataLines.join("\n");
      const evName = pendingEvent;
      pendingEvent = "";
      pendingDataLines.length = 0;
      try {
        const data = JSON.parse(payload);
        wrapOnEvent({ type: evName as StreamEventType, data });
      } catch {
        /* skip malformed JSON */
      }
    };

    const processSseLineArray = (lineArr: string[]) => {
      for (const raw of lineArr) {
        const line = raw.replace(/\r$/, "");
        if (line === "") {
          flushSseFrame();
          continue;
        }
        if (line.startsWith("event: ")) {
          flushSseFrame();
          pendingEvent = line.slice(7).trim();
          continue;
        }
        if (line.startsWith("data: ")) {
          if (!pendingEvent) continue;
          pendingDataLines.push(line.slice(6));
          continue;
        }
      }
    };

    if (idleMs > 0 && typeof setInterval !== "undefined") {
      idleCheckInterval = setInterval(() => {
        if (Date.now() - lastActivity >= idleMs) {
          idleKill = true;
          if (idleCheckInterval) clearInterval(idleCheckInterval);
          idleCheckInterval = undefined;
          void reader.cancel();
        }
      }, 2000);
    }

    try {
      while (true) {
        if (userSignal?.aborted) {
          await reader.cancel().catch(() => {});
          return;
        }
        let readResult: ReadableStreamReadResult<Uint8Array>;
        try {
          readResult = await reader.read();
        } catch (e) {
          if (userSignal?.aborted) return;
          if (idleKill) {
            throw new StreamChatError(
              "stream_idle",
              `超过 ${idleMs}ms 未收到新的 SSE 数据`,
              lastPhase.current,
            );
          }
          if (_isAbortError(e) && totalWallFired) {
            throw new StreamChatError(
              "stream_total",
              `整流超过 ${totalMs}ms`,
              lastPhase.current,
            );
          }
          throw e;
        }

        lastActivity = Date.now();
        const { done, value } = readResult;
        if (value) {
          buffer += decoder.decode(value, { stream: true });
        }
        if (done) {
          // Flush any incomplete UTF-8 code point held inside TextDecoder (stream:true).
          buffer += decoder.decode(new Uint8Array(), { stream: false });
          // RFC 8895: each SSE event ends with a blank line. Some proxies close the body right
          // after the last `data:` byte without the final `\n\n`, so `lines.pop()` keeps the
          // whole `data:` line in `buffer` and we never flush the final `done` frame.
          buffer += "\n\n";
        }
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        processSseLineArray(lines);

        if (done) {
          if (buffer) {
            processSseLineArray(buffer.split("\n"));
            buffer = "";
          }
          flushSseFrame();
          completedFullRead = true;
          break;
        }
      }
    } finally {
      if (idleCheckInterval) clearInterval(idleCheckInterval);
      if (!completedFullRead) {
        try {
          await reader.cancel();
        } catch {
          /* ignore */
        }
      }
    }
  } finally {
    clearTimeout(totalTimer);
  }
}

/**
 * Convert a backend plan event into PlanStep[] for the store.
 */
export function toPlanSteps(data: PlanEventData): PlanStep[] {
  return data.steps.map((s) => ({
    id: s.id,
    description: s.description,
    tool: s.tool,
    status: "pending" as const,
  }));
}
