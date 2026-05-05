"use client";

/** Collapsible onboarding copy; opened from header beside product title. */

export function UsageGuidePanel({ open }: { open: boolean }) {
  if (!open) return null;

  return (
    <div className="border-b border-[var(--color-border)] bg-[var(--color-surface)]/80 px-6 py-3 text-sm text-[var(--color-text-muted)] space-y-2">
      <p className="text-[var(--color-text)] font-medium text-xs uppercase tracking-wide">
        使用说明
      </p>
      <ul className="list-disc pl-5 space-y-1.5 leading-relaxed">
        <li>
          每个会话围绕<strong className="text-[var(--color-text)]">一个</strong>
          金融标的展开；当右侧<strong className="text-[var(--color-text)]">「实时投研报告」</strong>
          有内容且你点击<strong className="text-[var(--color-text)]">「保存」</strong>
          入库后，侧边栏会话名将按报告正文尽量提炼为<strong className="text-[var(--color-text)]">标的名称或代码</strong>
          （如 <code className="text-[var(--color-accent)]">NVDA</code>、
          <code className="text-[var(--color-accent)]">$AAPL</code>、括号内代码），与报告保持一致。
        </li>
        <li>
          投研正文与摘录在<strong className="text-[var(--color-text)]">「实时投研报告」</strong>
          面板；左侧气泡为多轮问答与推理过程。若已开启会话库，本轮内容仅在保存后写入数据库。
        </li>
        <li>
          诊断 SSE、会话库、长期记忆默认值由<strong className="text-[var(--color-text)]">启动环境变量</strong>
          控制（参见仓库根目录 <code>.env.example</code>），不在聊天界面勾选。
        </li>
      </ul>
      <p className="text-xs opacity-80 pt-1">
        EZInvest 可能产生不准确信息，不构成投资建议。
      </p>
    </div>
  );
}
