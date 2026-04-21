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

export type StreamEventType =
  | "plan"
  | "step_update"
  | "summarizing"
  | "tool_call"
  | "token"
  | "done"
  | "error";

export interface StreamEvent {
  type: StreamEventType;
  data: unknown;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export async function streamChat(
  message: string,
  sessionId: string,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, stream: true }),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let currentEventType = "";

    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEventType = line.slice(7).trim();
      } else if (line.startsWith("data: ") && currentEventType) {
        try {
          const data = JSON.parse(line.slice(6));
          onEvent({ type: currentEventType as StreamEventType, data });
        } catch {
          // skip malformed JSON
        }
        currentEventType = "";
      }
    }
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
