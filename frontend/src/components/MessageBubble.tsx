"use client";

import { Message } from "@/lib/store";
import { ToolCallCard } from "./ToolCallCard";
import { PlanProgressView } from "./PlanProgressView";
import { User, Bot, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MessageBubbleProps {
  message: Message;
  /** True while this assistant message is still receiving SSE */
  isStreamingAssistant?: boolean;
}

export function MessageBubble({
  message,
  isStreamingAssistant = false,
}: MessageBubbleProps) {
  const isUser = message.role === "user";
  const hasPlan = message.plan && message.plan.length > 0;
  const hasThought = Boolean(message.thought?.trim());
  const showThoughtPanel =
    hasThought || (message.role === "assistant" && isStreamingAssistant);
  const hasDebugLines = Boolean(message.debugTrace?.length);
  const showDebugPanel =
    message.role === "assistant" &&
    (hasDebugLines || Boolean(message.diagnosticRequested));

  return (
    <div className={`flex gap-3 animate-fade-in ${isUser ? "justify-end" : ""}`}>
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[var(--color-accent)] flex items-center justify-center">
          <Bot className="w-4 h-4 text-white" />
        </div>
      )}

      <div className={`max-w-[85%] space-y-2 ${isUser ? "items-end" : ""}`}>
        {isUser ? (
          <div className="px-4 py-3 rounded-2xl rounded-tr-sm bg-[var(--color-accent)] text-white shadow-sm">
            <p className="whitespace-pre-wrap text-sm">{message.content}</p>
          </div>
        ) : (
          <>
            {/* Thought trace: show shell while streaming so users see progress before first SSE. */}
            {showThoughtPanel && (
              <details
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]/50 px-3 py-2"
                open={isStreamingAssistant}
              >
                <summary className="cursor-pointer text-xs font-medium text-[var(--color-text-muted)] select-none flex items-center gap-2">
                  {isStreamingAssistant && (
                    <Loader2 className="w-3 h-3 animate-spin shrink-0 text-[var(--color-accent)]" />
                  )}
                  思考过程
                  {!isStreamingAssistant && (
                    <span className="text-[10px] font-normal opacity-70">
                      （点击展开）
                    </span>
                  )}
                </summary>
                <pre className="mt-2 max-h-52 overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed text-[var(--color-text-muted)] border-t border-[var(--color-border)] pt-2">
                  {hasThought
                    ? message.thought
                    : "正在等待服务器推送步骤（若长时间停留在此，多半是数据库写入、RAG 检索或模型首包较慢）…"}
                </pre>
              </details>
            )}

            {showDebugPanel && (
              <details
                className="rounded-lg border border-amber-500/40 bg-amber-500/5 px-3 py-2"
                open={isStreamingAssistant}
              >
                <summary className="cursor-pointer text-xs font-medium text-amber-200/90 select-none">
                  后端诊断（SSE event: debug）
                </summary>
                <pre className="mt-2 max-h-60 overflow-y-auto whitespace-pre-wrap font-mono text-[11px] leading-snug text-amber-100/90 border-t border-amber-500/20 pt-2">
                  {hasDebugLines
                    ? message.debugTrace!.join("\n")
                    : "已用 NEXT_PUBLIC_STREAM_DEBUG=1 启动前端，但尚未收到任何 debug 行。\n\n请先确认：① 浏览器控制台是否出现 “[EZInvest] stream POST ok…”；② 后端终端是否出现 “chat stream: request.debug_stream=… effective=True”；③ Network 里该请求的 Response 是否能看到 “event: debug”。正常时首帧应为 route.handshake。\n\n若①无则未发到本后端；若②里 effective=False 则未带上 debug_stream；若③无 event:debug 则中间层改写了响应体。"}
                </pre>
              </details>
            )}

            {/* Plan progress (replaces flat ToolCallCards when present) */}
            {hasPlan ? (
              <PlanProgressView
                steps={message.plan!}
                isSummarizing={message.isSummarizing}
              />
            ) : (
              message.toolCalls &&
              message.toolCalls.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {message.toolCalls.map((tc, i) => (
                    <ToolCallCard key={`${tc.tool}-${i}`} toolCall={tc} />
                  ))}
                </div>
              )
            )}

            {message.content &&
              (isStreamingAssistant ? (
                <div className="px-5 py-4 rounded-2xl rounded-tl-sm bg-[var(--color-surface)] border border-[var(--color-border)] shadow-sm text-sm leading-relaxed text-[var(--color-text)] whitespace-pre-wrap break-words">
                  {message.content}
                </div>
              ) : (
                <div className="px-5 py-4 rounded-2xl rounded-tl-sm bg-[var(--color-surface)] border border-[var(--color-border)] shadow-sm prose prose-sm prose-invert max-w-none">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h1: ({ ...props }) => <h1 className="text-lg font-bold mb-2 text-[var(--color-accent)]" {...props} />,
                      h2: ({ ...props }) => <h2 className="text-md font-bold mb-2 mt-4 border-b border-[var(--color-border)] pb-1" {...props} />,
                      h3: ({ ...props }) => <h3 className="text-sm font-bold mb-1 mt-3" {...props} />,
                      p: ({ ...props }) => <p className="mb-3 leading-relaxed text-sm text-[var(--color-text)]" {...props} />,
                      ul: ({ ...props }) => <ul className="list-disc pl-5 mb-3 space-y-1" {...props} />,
                      ol: ({ ...props }) => <ol className="list-decimal pl-5 mb-3 space-y-1" {...props} />,
                      li: ({ ...props }) => <li className="text-sm" {...props} />,
                      table: ({ ...props }) => (
                        <div className="overflow-x-auto my-4">
                          <table className="min-w-full divide-y divide-[var(--color-border)] border border-[var(--color-border)] rounded-lg" {...props} />
                        </div>
                      ),
                      thead: ({ ...props }) => <thead className="bg-[var(--color-surface-hover)]" {...props} />,
                      th: ({ ...props }) => <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider" {...props} />,
                      td: ({ ...props }) => <td className="px-3 py-2 text-sm border-t border-[var(--color-border)]" {...props} />,
                      blockquote: ({ ...props }) => <blockquote className="border-l-4 border-[var(--color-accent)] pl-4 italic my-4 text-[var(--color-text-muted)]" {...props} />,
                      code: ({ ...props }) => <code className="bg-[var(--color-surface-hover)] px-1 rounded text-[var(--color-accent)]" {...props} />,
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                </div>
              ))}

            {!message.content &&
              !hasPlan &&
              !showThoughtPanel &&
              !showDebugPanel && (
              <div className="flex gap-1 px-4 py-3">
                <span className="w-2 h-2 rounded-full bg-[var(--color-text-muted)] typing-dot" />
                <span className="w-2 h-2 rounded-full bg-[var(--color-text-muted)] typing-dot" />
                <span className="w-2 h-2 rounded-full bg-[var(--color-text-muted)] typing-dot" />
              </div>
            )}

            {message.latencyMs && (
              <p className="text-xs text-[var(--color-text-muted)] pl-1">
                {(message.latencyMs / 1000).toFixed(1)}s
              </p>
            )}
          </>
        )}
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[var(--color-surface)] border border-[var(--color-border)] flex items-center justify-center">
          <User className="w-4 h-4 text-[var(--color-text-muted)]" />
        </div>
      )}
    </div>
  );
}
