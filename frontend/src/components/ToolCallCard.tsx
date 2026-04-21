"use client";

import { ToolCall } from "@/lib/store";
import { Search, BarChart3, Calculator, TrendingUp, Loader2, CheckCircle2, XCircle } from "lucide-react";

const TOOL_CONFIG: Record<string, { icon: typeof Search; label: string; color: string }> = {
  retriever: { icon: Search, label: "Searching documents", color: "text-blue-400" },
  sentiment_analyzer: { icon: BarChart3, label: "Analyzing sentiment", color: "text-purple-400" },
  calculator: { icon: Calculator, label: "Computing metrics", color: "text-emerald-400" },
  market_data: { icon: TrendingUp, label: "Fetching market data", color: "text-amber-400" },
};

export function ToolCallCard({ toolCall }: { toolCall: ToolCall }) {
  const config = TOOL_CONFIG[toolCall.tool] || {
    icon: Search,
    label: toolCall.tool,
    color: "text-gray-400",
  };
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-sm animate-fade-in">
      <Icon className={`w-4 h-4 ${config.color}`} />
      <span className="text-[var(--color-text-muted)]">{config.label}</span>
      {toolCall.status === "running" && (
        <Loader2 className="w-3.5 h-3.5 text-[var(--color-text-muted)] animate-spin ml-auto" />
      )}
      {toolCall.status === "done" && (
        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 ml-auto" />
      )}
      {toolCall.status === "error" && (
        <XCircle className="w-3.5 h-3.5 text-red-400 ml-auto" />
      )}
    </div>
  );
}
