"use client";

import { Message } from "@/lib/store";
import { ToolCallCard } from "./ToolCallCard";
import { PlanProgressView } from "./PlanProgressView";
import { User, Bot } from "lucide-react";

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

      <div className={`max-w-[75%] space-y-2 ${isUser ? "items-end" : ""}`}>
        {isUser ? (
          <div className="px-4 py-3 rounded-2xl rounded-tr-sm bg-[var(--color-accent)] text-white">
            <p className="whitespace-pre-wrap text-sm">{message.content}</p>
          </div>
        ) : (
          <>
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
              <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-[var(--color-surface)] border border-[var(--color-border)]">
                <p className="whitespace-pre-wrap text-sm leading-relaxed">
                  {message.content}
                </p>
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
