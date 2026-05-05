/**
 * Build-time / process startup flags (NEXT_PUBLIC_* inlined by Next.js).
 * Configure via `.env.local`, `npm run dev:…`, or `scripts/restart-dev.sh --…`.
 * Do not expose toggles in the chat UI.
 */

function truthy(v: string | undefined): boolean {
  if (v == null || v === "") return false;
  const s = v.trim().toLowerCase();
  return s === "1" || s === "true" || s === "yes" || s === "on";
}

/** SSE `event: debug` + 助手消息内诊断折叠区 */
export function isStreamDebugEnabled(): boolean {
  return truthy(process.env.NEXT_PUBLIC_STREAM_DEBUG);
}

/** 每轮默认是否把用户消息写入长期记忆（仍由后端 save_message_as_memory 执行） */
export function isSaveUserMessageAsMemoryEnabled(): boolean {
  return truthy(process.env.NEXT_PUBLIC_SAVE_USER_MESSAGE_AS_MEMORY);
}

/**
 * `auto`（默认）：按后端 bootstrap 是否可用会话库。
 * `off`：前端不调会话 API，无侧边历史（纯浏览器态聊天）。
 */
export function isConversationDbClientEnabled(): boolean {
  const v = process.env.NEXT_PUBLIC_CONVERSATION_DB?.trim().toLowerCase();
  if (v === "off" || v === "0" || v === "false" || v === "no") return false;
  return true;
}
