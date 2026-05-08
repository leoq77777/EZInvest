"use client";

import {
  useRef,
  useEffect,
  useState,
  useCallback,
  useMemo,
  FormEvent,
} from "react";
import { Send, Square, Trash2, MessageSquare, CircleHelp } from "lucide-react";
import { useChatStore } from "@/lib/store";
import {
  streamChat,
  StreamChatError,
  streamChatErrorHint,
  StreamEvent,
  ToolCallEvent,
  PlanEventData,
  StepUpdateData,
  toPlanSteps,
  getOrCreateProfileId,
  bootstrapConversation,
  createConversation,
  listConversations,
  fetchConversationMessages,
  fetchResearchReport,
  commitConversationTurn,
  type ConversationRow,
  type ChatMode,
} from "@/lib/api";
import {
  isStreamDebugEnabled,
  isConversationDbClientEnabled,
} from "@/lib/runtimeConfig";
import { MessageBubble } from "./MessageBubble";
import { LiveReportPanel } from "./LiveReportPanel";
import { UsageGuidePanel } from "./UsageGuidePanel";

const EXAMPLE_QUERIES = [
  "How did NVIDIA perform in its latest earnings?",
  "What's the current sentiment on Tesla stock?",
  "Compare the P/E ratios of AAPL and MSFT",
  "Is now a good time to invest in semiconductor ETFs?",
];

function formatSessionLabel(row: ConversationRow): string {
  if (row.title?.trim()) return row.title.trim().slice(0, 48);
  const d = new Date(row.updated_at);
  const t = Number.isNaN(d.getTime()) ? "" : d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return t || "未命名会话";
}

export function ChatWindow() {
  const [input, setInput] = useState("");
  const [sessions, setSessions] = useState<ConversationRow[]>([]);
  const [usageGuideOpen, setUsageGuideOpen] = useState(false);
  const [chatMode, setChatMode] = useState<ChatMode>("research");
  const [pendingTurnSave, setPendingTurnSave] = useState<{
    userMessage: string;
    assistantMessage: string;
    reportMarkdown: string;
  } | null>(null);
  const [saveTurnBusy, setSaveTurnBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const streamAbortRef = useRef<AbortController | null>(null);

  const {
    messages,
    sessionId,
    profileId,
    conversationId,
    rememberNextMessage,
    persistenceReady,
    bootstrapDone,
    isStreaming,
    liveReportMarkdown,
    setProfileId,
    setConversationId,
    setPersistenceReady,
    setBootstrapDone,
    setLiveReport,
    hydrateFromServer,
    addUserMessage,
    startAssistantMessage,
    appendToken,
    addToolCall,
    updateToolCall,
    setPlan,
    appendThought,
    appendDebug,
    updateStep,
    setSummarizing,
    finalizeMessage,
    setStreaming,
    clearLocalMessages,
    rotateSessionId,
  } = useChatStore();

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const refreshSessions = useCallback(async (pid: string) => {
    if (!pid) return;
    const rows = await listConversations(pid);
    setSessions(rows);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const pid = getOrCreateProfileId();
      if (!pid) {
        setBootstrapDone(true);
        return;
      }
      setProfileId(pid);
      if (!isConversationDbClientEnabled()) {
        setPersistenceReady(false);
        setConversationId(null);
        setLiveReport("");
        setBootstrapDone(true);
        return;
      }
      const boot = await bootstrapConversation(pid);
      if (cancelled) return;
      if (boot.database_available && boot.conversation_id) {
        setPersistenceReady(true);
        setConversationId(boot.conversation_id);
        hydrateFromServer(boot.messages);
        setLiveReport(boot.report_markdown ?? "");
        await refreshSessions(pid);
      } else {
        setPersistenceReady(false);
        setConversationId(null);
        setLiveReport("");
      }
      setBootstrapDone(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [
    setProfileId,
    setConversationId,
    setPersistenceReady,
    setBootstrapDone,
    hydrateFromServer,
    setLiveReport,
    refreshSessions,
  ]);

  const handleSelectConversation = async (id: string) => {
    if (isStreaming || id === conversationId) return;
    setPendingTurnSave(null);
    const pid = profileId || getOrCreateProfileId();
    if (!pid) return;
    const rows = await fetchConversationMessages(id, pid);
    hydrateFromServer(rows);
    const reportMd = await fetchResearchReport(id, pid);
    setLiveReport(reportMd);
    setConversationId(id);
    rotateSessionId();
  };

  const handleNewConversation = async () => {
    setPendingTurnSave(null);
    clearLocalMessages();
    rotateSessionId();
    if (!profileId || !persistenceReady) return;
    const conv = await createConversation(profileId);
    if (conv?.id) {
      setConversationId(conv.id);
      await refreshSessions(profileId);
    }
  };

  const handleStopStream = () => {
    streamAbortRef.current?.abort();
  };

  const handleCommitPendingTurn = useCallback(async () => {
    if (!pendingTurnSave || !conversationId || !profileId) return;
    setSaveTurnBusy(true);
    try {
      await commitConversationTurn(conversationId, profileId, {
        user_message: pendingTurnSave.userMessage,
        assistant_message: pendingTurnSave.assistantMessage,
        report_markdown: pendingTurnSave.reportMarkdown,
        save_message_as_memory: rememberNextMessage,
      });
      const rows = await fetchConversationMessages(conversationId, profileId);
      hydrateFromServer(rows);
      const reportMd = await fetchResearchReport(conversationId, profileId);
      setLiveReport(reportMd);
      await refreshSessions(profileId);
      setPendingTurnSave(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      window.alert(`保存失败：${msg}`);
    } finally {
      setSaveTurnBusy(false);
    }
  }, [
    pendingTurnSave,
    conversationId,
    profileId,
    rememberNextMessage,
    hydrateFromServer,
    setLiveReport,
    refreshSessions,
  ]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isStreaming || !bootstrapDone) return;

    const effectivePid = profileId || getOrCreateProfileId();
    if (effectivePid && !profileId) setProfileId(effectivePid);

    setPendingTurnSave(null);
    setInput("");
    addUserMessage(trimmed);
    setStreaming(true);

    const debugForThisRequest = isStreamDebugEnabled();
    const msgId = startAssistantMessage({
      diagnostic: debugForThisRequest,
    });
    const ac = new AbortController();
    streamAbortRef.current = ac;
    let gotDone = false;

    try {
      await streamChat(
        trimmed,
        sessionId,
        (event: StreamEvent) => {
        switch (event.type) {
          case "thought": {
            const thoughtData = event.data as { content: string };
            appendThought(msgId, thoughtData.content);
            break;
          }
          case "debug": {
            const d = event.data as {
              phase?: string;
              detail?: string;
              elapsed_ms?: number;
            };
            const ms = (d.elapsed_ms ?? 0).toFixed(0);
            const tail = d.detail ? ` — ${d.detail}` : "";
            appendDebug(msgId, `[${ms}ms] ${d.phase ?? "?"}${tail}`);
            break;
          }
          case "plan": {
            const planData = event.data as PlanEventData;
            setPlan(msgId, toPlanSteps(planData));
            break;
          }
          case "step_update": {
            const su = event.data as StepUpdateData & { stepId?: string };
            const stepId = su.step_id ?? su.stepId;
            if (!stepId) break;
            updateStep(msgId, stepId, {
              status: su.status,
              result: su.result,
              latencyMs: su.latency_ms,
            });
            break;
          }
          case "summarizing": {
            setSummarizing(msgId, true);
            break;
          }
          case "tool_call": {
            const tc = event.data as ToolCallEvent;
            if (tc.status === "running") {
              addToolCall(msgId, {
                tool: tc.tool,
                status: "running",
                query: tc.query,
              });
            } else {
              updateToolCall(msgId, tc.tool, {
                status: tc.status as "done" | "error",
                result: tc.result,
              });
            }
            break;
          }
          case "token": {
            const { content } = event.data as { content: string };
            appendToken(msgId, content);
            break;
          }
          case "report": {
            const d = event.data as { markdown?: string };
            setLiveReport(d.markdown ?? "");
            break;
          }
          case "done": {
            const { total_latency_ms } = event.data as {
              total_latency_ms: number;
            };
            gotDone = true;
            finalizeMessage(msgId, total_latency_ms);
            break;
          }
          case "error": {
            const d = event.data as { detail?: string };
            appendToken(
              msgId,
              `\n\n⚠️ 服务端错误：${d.detail ?? "未知错误"}`,
            );
            gotDone = true;
            finalizeMessage(msgId, 0);
            break;
          }
        }
      },
        {
        mode: chatMode,
        profileId: effectivePid || undefined,
        conversationId,
        saveMessageAsMemory: rememberNextMessage,
        autoPersistTurn: false,
        debugStream: debugForThisRequest,
        signal: ac.signal,
      },
      );

      // 流正常结束却未收到 done（代理掐断、后端崩溃、或 SSE 解析丢事件）时必须收尾，否则会永远 isStreaming
      if (!gotDone) {
        if (ac.signal.aborted) {
          appendToken(msgId, "\n\n_已停止生成。_");
        } else {
          appendToken(
            msgId,
            "\n\n⚠️ 流式连接已结束，但未收到完成信号（done）。常见于 Next/反向代理超时、后端进程退出或网络中断。若以 `NEXT_PUBLIC_STREAM_DEBUG=1` 启动前端，请看该条助手消息上方的「后端诊断」折叠区里的 phase（来自 SSE，不会进 backend_log.txt）；同时可对照运行后端的终端日志。",
          );
        }
        finalizeMessage(msgId, 0);
      }

      const rep = useChatStore.getState().liveReportMarkdown.trim();
      if (
        persistenceReady &&
        conversationId &&
        effectivePid &&
        rep &&
        chatMode === "research" &&
        !ac.signal.aborted
      ) {
        const msgs = useChatStore.getState().messages;
        const lastUser = [...msgs].reverse().find((m) => m.role === "user");
        const lastAsst = [...msgs].reverse().find((m) => m.role === "assistant");
        if (lastUser && lastAsst && lastUser.content === trimmed) {
          setPendingTurnSave({
            userMessage: lastUser.content,
            assistantMessage: lastAsst.content,
            reportMarkdown: rep,
          });
        }
      }
    } catch (err) {
      if (!ac.signal.aborted) {
        if (err instanceof StreamChatError) {
          appendToken(msgId, `\n\n⚠️ ${streamChatErrorHint(err)}`);
        } else {
          const msg = err instanceof Error ? err.message : String(err);
          appendToken(
            msgId,
            `\n\n⚠️ 请求异常：${msg}\n\n若需区分网络 / LLM / 后端，请用 NEXT_PUBLIC_STREAM_DEBUG=1 重启前端后再试。`,
          );
        }
        finalizeMessage(msgId, 0);
      } else {
        appendToken(msgId, "\n\n_已停止生成。_");
        finalizeMessage(msgId, 0);
      }
    } finally {
      streamAbortRef.current = null;
      setStreaming(false);
    }
  };

  const handleExampleClick = (query: string) => {
    setInput(query);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const sessionRowsForPicker = useMemo((): ConversationRow[] => {
    if (sessions.length > 0) return sessions;
    if (conversationId && persistenceReady) {
      return [
        {
          id: conversationId,
          profile_id: profileId || "",
          title: null,
          created_at: "",
          updated_at: new Date().toISOString(),
        },
      ];
    }
    return [];
  }, [sessions, conversationId, persistenceReady, profileId]);

  const inputLocked = isStreaming || !bootstrapDone;
  const persistenceHint = !bootstrapDone
    ? "正在连接会话存储…"
    : !isConversationDbClientEnabled()
      ? "会话库：已关闭（NEXT_PUBLIC_CONVERSATION_DB=off）"
      : persistenceReady
        ? "已同步历史"
        : "未启用数据库";
  const isResearchMode = chatMode === "research";

  return (
    <div className="flex h-screen w-full max-w-[1600px] mx-auto">
      {persistenceReady && (
        <aside className="hidden sm:flex flex-col w-56 shrink-0 border-r border-[var(--color-border)] bg-[var(--color-surface)]">
          <div className="px-3 py-3 border-b border-[var(--color-border)] flex items-center gap-2 text-xs font-medium text-[var(--color-text-muted)]">
            <MessageSquare className="w-3.5 h-3.5" />
            会话
          </div>
          <nav className="flex-1 overflow-y-auto p-2 space-y-1">
            {sessionRowsForPicker.map((row) => {
              const active = row.id === conversationId;
              return (
                <button
                  key={row.id}
                  type="button"
                  disabled={isStreaming}
                  onClick={() => void handleSelectConversation(row.id)}
                  className={`w-full text-left rounded-lg px-2.5 py-2 text-xs transition-colors ${
                    active
                      ? "bg-[var(--color-accent)]/20 text-[var(--color-text)] border border-[var(--color-accent)]/40"
                      : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] border border-transparent"
                  } disabled:opacity-50`}
                >
                  <span className="line-clamp-2">{formatSessionLabel(row)}</span>
                </button>
              );
            })}
            {sessionRowsForPicker.length === 0 && (
              <p className="px-2 text-xs text-[var(--color-text-muted)]">暂无会话</p>
            )}
          </nav>
        </aside>
      )}

      <div className="flex flex-1 flex-col lg:flex-row min-w-0 min-h-0">
      <div className="flex flex-col flex-1 min-w-0 min-h-0 w-full max-w-4xl lg:max-w-none">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)] gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-[var(--color-accent)] flex items-center justify-center font-bold text-white text-sm shrink-0">
            EZ
          </div>
          <div className="min-w-0 flex items-start gap-1.5">
            <div className="min-w-0">
              <div className="flex items-center gap-1 flex-wrap">
                <h1 className="text-base font-semibold">EZInvest</h1>
                <button
                  type="button"
                  onClick={() => setUsageGuideOpen((v) => !v)}
                  className="shrink-0 rounded-lg p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface-hover)] transition-colors"
                  aria-expanded={usageGuideOpen}
                  title={usageGuideOpen ? "收起使用说明" : "打开使用说明"}
                >
                  <CircleHelp className="w-[18px] h-[18px]" />
                </button>
              </div>
              <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
                AI Investment Assistant
                {" · "}
                {persistenceHint}
                {" · "}
                {isResearchMode ? "研究模式" : "闲聊模式"}
              </p>
            </div>
          </div>
        </div>
        <button
          onClick={handleNewConversation}
          className="p-2 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] transition-colors shrink-0"
          title="新对话（保留长期记忆）"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </header>

      <UsageGuidePanel open={usageGuideOpen} />

      {persistenceReady && (
        <div className="sm:hidden px-4 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
          <label className="block text-[10px] uppercase tracking-wide text-[var(--color-text-muted)] mb-1">
            当前会话
          </label>
          <select
            className="w-full rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm px-3 py-2 text-[var(--color-text)]"
            value={conversationId ?? ""}
            disabled={isStreaming}
            onChange={(e) => void handleSelectConversation(e.target.value)}
          >
            {sessionRowsForPicker.map((row) => (
              <option key={row.id} value={row.id}>
                {formatSessionLabel(row)}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-6 py-6 space-y-6"
      >
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-8 text-center">
            <div>
              <h2 className="text-2xl font-semibold mb-2">
                What would you like to know?
              </h2>
              <p className="text-[var(--color-text-muted)] text-sm">
                Ask about stocks, earnings, market sentiment, or financial
                metrics
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
              {EXAMPLE_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => handleExampleClick(q)}
                  className="text-left px-4 py-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-accent)] text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            isStreamingAssistant={
              isStreaming &&
              idx === messages.length - 1 &&
              msg.role === "assistant"
            }
          />
        ))}
      </div>

      {/* Input */}
      <div className="px-6 py-4 border-t border-[var(--color-border)] space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="inline-flex rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-1">
            <button
              type="button"
              disabled={isStreaming}
              onClick={() => setChatMode("chat")}
              className={`rounded-lg px-3 py-1.5 transition-colors ${
                chatMode === "chat"
                  ? "bg-[var(--color-accent)] text-white"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              } disabled:opacity-50`}
            >
              闲聊（快速）
            </button>
            <button
              type="button"
              disabled={isStreaming}
              onClick={() => setChatMode("research")}
              className={`rounded-lg px-3 py-1.5 transition-colors ${
                chatMode === "research"
                  ? "bg-[var(--color-accent)] text-white"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              } disabled:opacity-50`}
            >
              研究（研报）
            </button>
          </div>
          <span className="text-[var(--color-text-muted)]">
            {isResearchMode
              ? "会使用 RAG / 工具并生成研报"
              : "纯 LLM 回复，不生成研报"}
          </span>
        </div>
        <form onSubmit={handleSubmit} className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              inputLocked && !isStreaming
                ? "正在连接会话存储…"
                : isResearchMode
                  ? "Ask for research, filings, valuation, or a report..."
                  : "Ask a quick question..."
            }
            rows={1}
            disabled={inputLocked}
            className="flex-1 resize-none rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] px-4 py-3 text-sm placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors disabled:opacity-50"
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={handleStopStream}
              title="停止生成"
              className="flex-shrink-0 w-11 h-11 rounded-xl bg-[var(--color-negative)]/90 hover:bg-[var(--color-negative)] text-white flex items-center justify-center transition-colors"
            >
              <Square className="w-4 h-4 fill-current" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={inputLocked || !input.trim()}
              className="flex-shrink-0 w-11 h-11 rounded-xl bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-colors"
            >
              <Send className="w-4 h-4 text-white" />
            </button>
          )}
        </form>
        <p className="text-xs text-[var(--color-text-muted)] mt-2 text-center">
          EZInvest may produce inaccurate information. Not financial advice.
        </p>
      </div>
      </div>

      {isResearchMode && (
        <LiveReportPanel
          markdown={liveReportMarkdown}
          isUpdating={isStreaming}
          showSave={Boolean(persistenceReady && pendingTurnSave)}
          saveBusy={saveTurnBusy}
          onSave={
            pendingTurnSave && persistenceReady
              ? () => void handleCommitPendingTurn()
              : undefined
          }
        />
      )}
      </div>
    </div>
  );
}
