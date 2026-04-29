"use client";

import { Message } from "@/lib/store";
import { ToolCallCard } from "./ToolCallCard";
import { PlanProgressView } from "./PlanProgressView";
import { User, Bot, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const hasPlan = message.plan && message.plan.length > 0;

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
            {/* Thought/Progress message */}
            {message.thought && !message.content && (
              <div className="flex items-center gap-2 px-1 py-1 text-xs text-[var(--color-text-muted)] animate-pulse">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>{message.thought}</span>
              </div>
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

            {message.content && (
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
            )}

            {!message.content && !hasPlan && (
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
