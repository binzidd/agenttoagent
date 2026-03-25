/**
 * ChatPanel – streaming chat powered by Claude.
 * Sends the latest agent analysis as context so Claude can answer
 * questions like "Should I ride today?" or "Is it worth going to Costco?"
 */
import { useState, useRef, useEffect, useCallback } from "react";
import type { ChatMessage, AnalysisResult } from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const SUGGESTED = [
  "Should I ride today?",
  "Is the fuel detour worth it?",
  "Should I export solar or store it?",
  "What does today look like overall?",
  "When should I charge the battery?",
];

interface Props {
  analysisResult: AnalysisResult | null;
}

export function ChatPanel({ analysisResult }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hi! I'm your Austral home advisor powered by Claude. Run an analysis first, then ask me anything about your solar, fuel, riding conditions, or the energy grid.",
    },
  ]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // When analysis finishes, inject a proactive summary message
  useEffect(() => {
    if (!analysisResult?.summary) return;
    setMessages((prev) => {
      // Don't duplicate if already added
      if (prev.some((m) => m.content === analysisResult.summary)) return prev;
      return [
        ...prev,
        { role: "assistant", content: analysisResult.summary! },
      ];
    });
  }, [analysisResult?.summary]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || streaming) return;

      const userMsg: ChatMessage = { role: "user", content: text };
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: "",
        streaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setInput("");
      setStreaming(true);

      // Build messages array for API (exclude the streaming placeholder)
      const history = [
        ...messages.filter((m) => !m.streaming),
        userMsg,
      ].map(({ role, content }) => ({ role, content }));

      abortRef.current = new AbortController();

      try {
        const resp = await fetch(`${API_BASE}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ messages: history, context: analysisResult }),
          signal: abortRef.current.signal,
        });

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        if (!resp.body) throw new Error("No response body");

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const payload = line.slice(6).trim();
            if (payload === "[DONE]") break;
            try {
              const token = JSON.parse(payload) as string;
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last.streaming) {
                  return [
                    ...updated.slice(0, -1),
                    { ...last, content: last.content + token },
                  ];
                }
                return updated;
              });
            } catch {
              // ignore malformed SSE chunk
            }
          }
        }
      } catch (err: unknown) {
        if ((err as Error).name === "AbortError") return;
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.streaming) {
            return [
              ...updated.slice(0, -1),
              {
                ...last,
                content: "⚠️ Chat error. Make sure ANTHROPIC_API_KEY is set in backend/.env",
                streaming: false,
              },
            ];
          }
          return updated;
        });
      } finally {
        setStreaming(false);
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.streaming) {
            return [...updated.slice(0, -1), { ...last, streaming: false }];
          }
          return updated;
        });
      }
    },
    [messages, streaming, analysisResult]
  );

  return (
    <div className="flex flex-col bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-800">
        <span className="text-lg">🤖</span>
        <span className="font-semibold text-white text-sm">Ask Claude</span>
        {!analysisResult && (
          <span className="ml-auto text-xs text-gray-600">Run analysis first for context</span>
        )}
        {analysisResult && (
          <span className="ml-auto flex items-center gap-1 text-xs text-green-500">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
            Has live context
          </span>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto trace-scroll p-4 space-y-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="w-6 h-6 rounded-full bg-green-800 flex items-center justify-center text-xs shrink-0 mt-0.5">
                🤖
              </div>
            )}
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-green-700 text-white rounded-tr-sm"
                  : "bg-gray-800 text-gray-200 rounded-tl-sm"
              }`}
            >
              {msg.content}
              {msg.streaming && (
                <span className="inline-block w-1.5 h-4 bg-green-400 ml-0.5 animate-pulse rounded-sm" />
              )}
            </div>
            {msg.role === "user" && (
              <div className="w-6 h-6 rounded-full bg-gray-700 flex items-center justify-center text-xs shrink-0 mt-0.5">
                👤
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions (only when no chat history yet) */}
      {messages.length <= 1 && (
        <div className="px-4 pb-2 flex flex-wrap gap-1.5">
          {SUGGESTED.map((s) => (
            <button
              key={s}
              onClick={() => sendMessage(s)}
              className="text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 px-3 py-1.5 rounded-full transition-colors border border-gray-700"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="px-3 pb-3 pt-2 border-t border-gray-800">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage(input);
          }}
          className="flex gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about solar, fuel, riding conditions…"
            disabled={streaming}
            className="flex-1 bg-gray-800 text-gray-100 text-sm px-4 py-2.5 rounded-xl border border-gray-700 focus:outline-none focus:border-green-600 placeholder-gray-600 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={streaming || !input.trim()}
            className="bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 text-white px-4 py-2.5 rounded-xl text-sm font-semibold transition-colors"
          >
            {streaming ? (
              <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin block" />
            ) : (
              "↑"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
