"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { getDashboardSummary, runSimulation, DashboardSummary, SimulationResult } from "@/lib/api";
import { fmtMoney } from "@/lib/format";
import { SectionHeader, EmptyState } from "@/components/ui";

function ChartTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  return (
    <div className="card-raised px-3 py-2 text-xs">
      <div className="font-mono-num" style={{ color: p.color }}>{p.payload.label}: {fmtMoney(p.value)}</div>
    </div>
  );
}

export default function TimeMachinePage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [category, setCategory] = useState<string>("");
  const [pct, setPct] = useState(-0.3);
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboardSummary().then((s) => {
      setSummary(s);
      setPeriodStart(s.period_start);
      setPeriodEnd(s.period_end);
      if (s.top_categories.length) setCategory(s.top_categories[0].category);
    }).catch(() => setError("Could not load your spending data."));
  }, []);

  function run() {
    if (!category || !periodStart || !periodEnd) return;
    setLoading(true);
    setError(null);
    runSimulation({
      mode: "time_machine",
      assumptions: { category_pct_changes: { [category]: pct } },
      period_start: periodStart,
      period_end: periodEnd,
    })
      .then(setResult)
      .catch(() => setError("Couldn't run that scenario — try a different date range."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (category && periodStart && periodEnd) run();
  }, [category]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!summary) return <span className="font-mono-num text-sm" style={{ color: "var(--text-faint)" }}>loading —</span>;
  if (summary.top_categories.length === 0) {
    return (
      <EmptyState
        title="No history to replay yet"
        body="The Time Machine needs real transaction history to compare against — add some transactions first."
      />
    );
  }

  const chartData = result
    ? [
        { label: "Actual", value: result.baseline.actual_net_savings, fill: "#5c6773" },
        { label: "Hypothetical", value: result.simulated.hypothetical_net_savings, fill: "#f2b84b" },
      ]
    : [];

  return (
    <div className="flex flex-col gap-8">
      <SectionHeader
        mark="03"
        title="Financial Time Machine"
        subtitle="See how a different decision would have played out against your real history."
      />

      <div
        className="card px-4 py-3 text-xs"
        style={{ color: "var(--amber)", borderColor: "var(--amber-dim)" }}
      >
        Hypothetical — everything below is a retroactive projection, not what actually happened.
      </div>

      <div className="grid grid-cols-[320px_1fr] gap-8">
        <div className="card flex flex-col gap-4 px-5 py-5">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>Category</span>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="rounded border bg-transparent px-3 py-2 text-sm"
              style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
            >
              {summary.top_categories.map((c) => (
                <option key={c.category} value={c.category} style={{ background: "var(--surface)" }}>
                  {c.category}
                </option>
              ))}
            </select>
          </label>

          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-xs">
              <span style={{ color: "var(--text-muted)" }}>Hypothetical change</span>
              <span className="font-mono-num" style={{ color: "var(--amber)" }}>{Math.round(pct * 100)}%</span>
            </div>
            <input
              type="range"
              min={-70}
              max={0}
              step={5}
              value={pct * 100}
              onChange={(e) => setPct(Number(e.target.value) / 100)}
              onMouseUp={run}
              onTouchEnd={run}
              className="w-full"
            />
          </div>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>From</span>
            <input
              type="date"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              className="rounded border bg-transparent px-3 py-2 text-sm font-mono-num"
              style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>To</span>
            <input
              type="date"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              className="rounded border bg-transparent px-3 py-2 text-sm font-mono-num"
              style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
            />
          </label>

          <button
            onClick={run}
            disabled={loading}
            className="mt-2 rounded px-4 py-2.5 text-sm font-medium disabled:opacity-50"
            style={{ background: "var(--amber)", color: "#241a06" }}
          >
            {loading ? "Replaying history…" : "Replay this scenario"}
          </button>
          {error && <p className="text-xs" style={{ color: "var(--clay)" }}>{error}</p>}
        </div>

        {result && (
          <div className="flex flex-col gap-6">
            <div className="grid grid-cols-2 gap-3">
              <div className="card px-5 py-4">
                <div className="text-xs" style={{ color: "var(--text-muted)" }}>Actual net savings, this period</div>
                <div className="font-mono-num mt-1 text-xl" style={{ color: "var(--text-primary)" }}>
                  {fmtMoney(result.baseline.actual_net_savings)}
                </div>
              </div>
              <div className="card px-5 py-4" style={{ borderColor: "var(--amber-dim)" }}>
                <div className="text-xs" style={{ color: "var(--amber)" }}>Hypothetical net savings</div>
                <div className="font-mono-num mt-1 text-xl" style={{ color: "var(--text-primary)" }}>
                  {fmtMoney(result.simulated.hypothetical_net_savings)}
                </div>
              </div>
            </div>

            <div className="card px-4 py-4">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData}>
                  <CartesianGrid stroke="var(--border-soft)" vertical={false} />
                  <XAxis dataKey="label" tick={{ fill: "var(--text-faint)", fontSize: 12 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
                  <YAxis tick={{ fill: "var(--text-faint)", fontSize: 11 }} axisLine={false} tickLine={false} width={60} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                    {chartData.map((d, i) => <Cell key={i} fill={d.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div
              className="font-mono-num text-xs"
              style={{ color: result.delta.additional_savings_over_period >= 0 ? "var(--verdigris)" : "var(--clay)" }}
            >
              {fmtMoney(result.delta.additional_savings_over_period, { signDisplay: true })} vs. what actually happened
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
