"use client";

import { useState, useRef, useEffect } from "react";
import { askAssistant } from "@/lib/api";
import { SectionHeader } from "@/components/ui";

interface Message {
  role: "user" | "assistant";
  text: string;
  intent?: string;
}

const SUGGESTIONS = [
  "How much did I spend on Dining?",
  "Why did my spending increase?",
  "Can I afford my goal?",
  "What if I reduce Shopping by 20%?",
];

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", text: "Ask me about your spending, trends, goals, or try a what-if scenario." },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(question: string) {
    if (!question.trim()) return;
    setMessages((m) => [...m, { role: "user", text: question }]);
    setInput("");
    setLoading(true);
    try {
      const res = await askAssistant(question);
      setMessages((m) => [...m, { role: "assistant", text: res.answer, intent: res.intent }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Something went wrong answering that — try rephrasing." }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col gap-6">
      <SectionHeader mark="06" title="Assistant" subtitle="Routes to the same calculations behind every other page — never invents numbers." />

      <div className="card flex flex-1 flex-col overflow-hidden" style={{ minHeight: 420 }}>
        <div className="flex-1 overflow-y-auto px-5 py-5">
          <div className="flex flex-col gap-4">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className="max-w-[75%] rounded-lg px-4 py-2.5 text-sm"
                  style={{
                    background: m.role === "user" ? "var(--surface-raised)" : "transparent",
                    border: m.role === "assistant" ? "1px solid var(--border)" : "none",
                    color: "var(--text-primary)",
                  }}
                >
                  {m.text}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="font-mono-num rounded-lg border px-4 py-2.5 text-sm" style={{ borderColor: "var(--border)", color: "var(--text-faint)" }}>
                  thinking —
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>
        </div>

        {messages.length <= 1 && (
          <div className="flex flex-wrap gap-2 px-5 pb-3">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="rounded-full border px-3 py-1.5 text-xs"
                style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
              >
                {s}
              </button>
            ))}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex gap-2 border-t px-4 py-3"
          style={{ borderColor: "var(--border)" }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your spending…"
            className="flex-1 bg-transparent px-2 py-2 text-sm outline-none"
            style={{ color: "var(--text-primary)" }}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded px-4 py-2 text-sm font-medium disabled:opacity-40"
            style={{ background: "var(--verdigris)", color: "#0a1410" }}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
