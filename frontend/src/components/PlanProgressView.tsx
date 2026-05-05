"use client";

import { PlanStep } from "@/lib/store";
import {
  Search,
  BarChart3,
  Calculator,
  TrendingUp,
  Loader2,
  CheckCircle2,
  XCircle,
  Circle,
  Sparkles,
} from "lucide-react";

const TOOL_CONFIG: Record<
  string,
  { icon: typeof Search; label: string; color: string }
> = {
  retriever: {
    icon: Search,
    label: "知识库检索",
    color: "text-blue-400",
  },
  web_scraper: {
    icon: Sparkles,
    label: "联网实时搜索",
    color: "text-cyan-400",
  },
  sentiment_analyzer: {
    icon: BarChart3,
    label: "情感倾向分析",
    color: "text-purple-400",
  },
  calculator: {
    icon: Calculator,
    label: "财务数据计算",
    color: "text-emerald-400",
  },
  market_data: {
    icon: TrendingUp,
    label: "行情数据获取",
    color: "text-amber-400",
  },
};

function StepStatus({ status }: { status: PlanStep["status"] }) {
  switch (status) {
    case "running":
      return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />;
    case "done":
      return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
    case "error":
      return <XCircle className="w-4 h-4 text-red-400" />;
    default:
      return <Circle className="w-4 h-4 text-[var(--color-text-muted)]" />;
  }
}

export function PlanProgressView({
  steps,
  isSummarizing,
}: {
  steps: PlanStep[];
  isSummarizing?: boolean;
}) {
  if (!steps.length) return null;

  const completedCount = steps.filter((s) => s.status === "done").length;
  const runningCount = steps.filter((s) => s.status === "running").length;
  const errorCount = steps.filter((s) => s.status === "error").length;
  const allDone = completedCount === steps.length;

  return (
    <div className="rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] overflow-hidden animate-fade-in">
      {/* Progress header */}
      <div className="px-4 py-3 border-b border-[var(--color-border)] flex items-center justify-between">
        <span className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wide">
          投研执行计划
        </span>
        <span className="text-xs text-[var(--color-text-muted)] tabular-nums">
          完成 {completedCount}/{steps.length}
          {runningCount > 0 ? ` · 进行中 ${runningCount}` : ""}
          {errorCount > 0 ? ` · 失败 ${errorCount}` : ""}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-0.5 bg-[var(--color-border)]">
        <div
          className="h-full bg-[var(--color-accent)] transition-all duration-500 ease-out"
          style={{ width: `${(completedCount / steps.length) * 100}%` }}
        />
      </div>

      {/* Step list */}
      <div className="divide-y divide-[var(--color-border)]">
        {steps.map((step, i) => {
          const config = TOOL_CONFIG[step.tool] || {
            icon: Search,
            label: step.tool,
            color: "text-gray-400",
          };
          const ToolIcon = config.icon;

          return (
            <div
              key={step.id}
              className={`flex items-start gap-3 px-4 py-3 transition-colors ${
                step.status === "running"
                  ? "bg-blue-500/5"
                  : step.status === "done"
                    ? "bg-emerald-500/5"
                    : step.status === "error"
                      ? "bg-red-500/5"
                      : ""
              }`}
            >
              <div className="flex-shrink-0 mt-0.5">
                <StepStatus status={step.status} />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <ToolIcon className={`w-3.5 h-3.5 ${config.color}`} />
                  <span className="text-xs text-[var(--color-text-muted)]">
                    {config.label}
                  </span>
                  {step.latencyMs != null && step.status === "done" && (
                    <span className="text-[10px] text-[var(--color-text-muted)] ml-auto">
                      {(step.latencyMs / 1000).toFixed(1)}s
                    </span>
                  )}
                </div>
                <p className="text-sm mt-0.5 leading-snug">{step.description}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Summarizing indicator */}
      {allDone && isSummarizing && (
        <div className="px-4 py-3 border-t border-[var(--color-border)] flex items-center gap-2 bg-[var(--color-accent)]/5">
          <Sparkles className="w-4 h-4 text-[var(--color-accent)] animate-pulse" />
          <span className="text-sm text-[var(--color-text-muted)]">
            正在撰写投资报告...
          </span>
        </div>
      )}
    </div>
  );
}
