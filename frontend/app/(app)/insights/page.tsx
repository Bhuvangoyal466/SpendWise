"use client";

import { useEffect, useState } from "react";
import { listInsights, generateInsights, Insight } from "@/lib/api";
import { SectionHeader, EmptyState } from "@/components/ui";

const CATEGORY_LABELS: Record<string, string> = {
  spending_change: "Spending change",
  anomaly: "Anomaly",
  goal_risk: "Goal risk",
  subscription: "Subscription",
  behavioral: "Behavioral",
  forecast: "Forecast",
};

const CATEGORY_COLORS: Record<string, string> = {
  spending_change: "var(--verdigris)",
  anomaly: "var(--clay)",
  goal_risk: "var(--clay)",
  subscription: "var(--amber)",
  behavioral: "#7ea9c9",
  forecast: "#b98fd6",
};

export default function InsightsPage() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  function load() {
    listInsights().then(setInsights).finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function handleGenerate() {
    setGenerating(true);
    try {
      await generateInsights();
      load();
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-start justify-between">
        <SectionHeader
          mark="05"
          title="Insights"
          subtitle="Every sentence here is generated from a number computed first — never invented by the AI."
        />
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="rounded px-4 py-2 text-sm font-medium disabled:opacity-50"
          style={{ background: "var(--verdigris)", color: "#0a1410" }}
        >
          {generating ? "Analyzing…" : "Generate new insights"}
        </button>
      </div>

      {loading ? (
        <span className="font-mono-num text-sm" style={{ color: "var(--text-faint)" }}>loading —</span>
      ) : insights.length === 0 ? (
        <EmptyState title="No insights yet" body="Generate insights to get plain-language explanations of your spending trends, anomalies, and goal risk." />
      ) : (
        <div className="flex flex-col gap-3">
          {insights.map((insight) => (
            <div key={insight.id} className="card px-5 py-4">
              <div className="flex items-center gap-2">
                <span
                  className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                  style={{ background: "var(--border-soft)", color: CATEGORY_COLORS[insight.category] || "var(--text-muted)" }}
                >
                  {CATEGORY_LABELS[insight.category] || insight.category}
                </span>
                <span className="font-mono-num text-[10px]" style={{ color: "var(--text-faint)" }}>
                  {new Date(insight.generated_at).toLocaleDateString()}
                </span>
              </div>
              <p className="mt-2 text-sm" style={{ color: "var(--text-primary)" }}>
                {insight.narrative}
              </p>
              <details className="mt-2">
                <summary className="cursor-pointer text-xs" style={{ color: "var(--text-faint)" }}>
                  Underlying data
                </summary>
                <pre
                  className="font-mono-num mt-2 overflow-x-auto rounded px-3 py-2 text-[11px]"
                  style={{ background: "var(--ink)", color: "var(--text-muted)" }}
                >
                  {JSON.stringify(insight.structured_finding, null, 2)}
                </pre>
              </details>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
