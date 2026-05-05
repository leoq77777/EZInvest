"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { FileText } from "lucide-react";

interface LiveReportPanelProps {
  markdown: string;
  isUpdating?: boolean;
  /** Shown only when non-empty markdown and user has not yet saved this turn (DB). */
  showSave?: boolean;
  saveBusy?: boolean;
  onSave?: () => void;
}

export function LiveReportPanel({
  markdown,
  isUpdating,
  showSave,
  saveBusy,
  onSave,
}: LiveReportPanelProps) {
  const trimmed = markdown.trim();
  const canSave = Boolean(showSave && trimmed && onSave);

  return (
    <aside className="flex flex-col min-h-0 bg-[var(--color-surface)] border-[var(--color-border)] border-t lg:border-t-0 lg:border-l lg:w-[min(440px,42vw)] shrink-0 max-h-[42vh] lg:max-h-none">
      <div className="px-4 py-3 border-b border-[var(--color-border)] flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-medium text-[var(--color-text)]">
          <FileText className="w-4 h-4 text-[var(--color-accent)] shrink-0" />
          实时投研报告
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {canSave && (
            <button
              type="button"
              disabled={Boolean(saveBusy)}
              onClick={onSave}
              className="text-xs font-medium rounded-md px-2.5 py-1 bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)] disabled:opacity-50 transition-colors"
            >
              {saveBusy ? "保存中…" : "保存"}
            </button>
          )}
          {isUpdating && (
            <span className="text-[10px] uppercase tracking-wide text-[var(--color-accent)]">
              更新中…
            </span>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3 text-sm leading-relaxed text-[var(--color-text)] [&_h1]:text-base [&_h1]:font-semibold [&_h1]:mt-4 [&_h1]:mb-2 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:mt-3 [&_h2]:mb-1.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_code]:text-xs [&_code]:bg-[var(--color-bg)] [&_code]:px-1 [&_code]:rounded">
        {trimmed ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
        ) : (
          <p className="text-[var(--color-text-muted)] text-xs leading-relaxed">
            尚无报告。与助手多轮对话后，右侧将展示合并后的标的级投资建议；流式生成结束后若报告非空，可点击「保存」将本轮问答与报告写入会话库，会话名将与报告中的标的一致。
          </p>
        )}
      </div>
    </aside>
  );
}
