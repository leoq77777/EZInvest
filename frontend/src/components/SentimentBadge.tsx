"use client";

interface SentimentBadgeProps {
  label: "positive" | "negative" | "neutral";
  score: number;
}

const STYLE_MAP = {
  positive: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  negative: "bg-red-500/15 text-red-400 border-red-500/30",
  neutral: "bg-amber-500/15 text-amber-400 border-amber-500/30",
};

export function SentimentBadge({ label, score }: SentimentBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${STYLE_MAP[label]}`}
    >
      <span className="capitalize">{label}</span>
      <span className="opacity-70">{(score * 100).toFixed(0)}%</span>
    </span>
  );
}
