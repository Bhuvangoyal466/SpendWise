"use client";

import { useEffect, useState, useCallback } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { getDashboardSummary, runSimulation, DashboardSummary, SimulationResult } from "@/lib/api";
import { fmtMoney, fmtPct } from "@/lib/format";
import { SectionHeader, EmptyState } from "@/components/ui";

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="card-raised px-3 py-2 text-xs">
      <div style={{ color: "var(--text-muted)" }}>{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} className="font-mono-num" style={{ color: p.color }}>
          {p.name}: {fmtMoney(p.value)}
        </div>
      ))}
    </div>
  );
}

export default function SimulatorPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [changes, setChanges] = useState<Record<string, number>>({});
  const [incomeChange, setIncomeChange] = useState(0);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboardSummary()
      .then(setSummary)
      .catch(() => setError("Could not load your spending data."));
  }, []);

  const runSim = useCallback(
    (categoryChanges: Record<string, number>, income: number) => {
      setLoading(true);
      runSimulation({
        mode: "forward",
        assumptions: { category_pct_changes: categoryChanges, income_pct_change: income },
        horizon_months: 6,
      })
        .then(setResult)
        .catch(() => setError("Simulation failed — try adjusting fewer categories at once."))
        .finally(() => setLoading(false));
    },
    []
  );

  useEffect(() => {
    if (summary && Object.keys(changes).length === 0) {
      runSim({}, 0);
    }
  }, [summary]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleSlider(category: string, pct: number) {
    const next = { ...changes, [category]: pct };
    setChanges(next);
    runSim(next, incomeChange);
  }

  if (error && !summary) return <EmptyState title="Something went wrong" body={error} />;
  if (!summary) return <span className="font-mono-num text-sm" style={{ color: "var(--text-faint)" }}>loading —</span>;
  if (summary.top_categories.length === 0) {
    return (
      <EmptyState
        title="Nothing to simulate yet"
        body="Add or import some transactions first — the simulator builds its baseline from your real recent spending."
      />
    );
  }

  const chartData = result
    ? Object.keys(result.baseline.monthly_expense_by_category).map((cat) => ({
        category: cat,
        Current: result.baseline.monthly_expense_by_category[cat],
        Simulated: result.simulated.monthly_expense_by_category[cat],
      }))
    : [];

  return (
    <div className="flex flex-col gap-8">
      <SectionHeader
        mark="02"
        title="Financial What-If Simulator"
        subtitle="Adjust hypothetical spending and see the impact on your savings, instantly."
      />

      <div className="grid grid-cols-[320px_1fr] gap-8">
        {/* controls */}
        <div className="card flex flex-col gap-5 px-5 py-5">
          <div className="text-xs font-medium" style={{ color: "var(--amber)" }}>ADJUST SPENDING</div>
          {summary.top_categories.map((c) => {
            const pct = changes[c.category] ?? 0;
            return (
              <div key={c.category} className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span style={{ color: "var(--text-primary)" }}>{c.category}</span>
                  <span className="font-mono-num" style={{ color: pct < 0 ? "var(--verdigris)" : pct > 0 ? "var(--clay)" : "var(--text-faint)" }}>
                    {pct > 0 ? "+" : ""}{Math.round(pct * 100)}%
                  </span>
                </div>
                <input
                  type="range"
                  min={-50}
                  max={50}
                  step={5}
                  value={pct * 100}
                  onChange={(e) => handleSlider(c.category, Number(e.target.value) / 100)}
                  className="w-full"
                  aria-label={`Adjust ${c.category} spending`}
                />
              </div>
            );
          })}

          <div className="ledger-tick" />

          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-xs">
              <span style={{ color: "var(--text-primary)" }}>Income</span>
              <span className="font-mono-num" style={{ color: incomeChange > 0 ? "var(--verdigris)" : incomeChange < 0 ? "var(--clay)" : "var(--text-faint)" }}>
                {incomeChange > 0 ? "+" : ""}{Math.round(incomeChange * 100)}%
              </span>
            </div>
            <input
              type="range"
              min={-30}
              max={30}
              step={5}
              value={incomeChange * 100}
              onChange={(e) => {
                const v = Number(e.target.value) / 100;
                setIncomeChange(v);
                runSim(changes, v);
              }}
              className="w-full"
              aria-label="Adjust income"
            />
          </div>

          <button
            onClick={() => {
              setChanges({});
              setIncomeChange(0);
              runSim({}, 0);
            }}
            className="mt-2 rounded border px-3 py-2 text-xs"
            style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
          >
            Reset scenario
          </button>
        </div>

        {/* results */}
        <div className="flex flex-col gap-6">
          {result && (
            <>
              <div className="grid grid-cols-3 gap-3">
                <div className="card px-5 py-4">
                  <div className="text-xs" style={{ color: "var(--text-muted)" }}>Current net savings / mo</div>
                  <div className="font-mono-num mt-1 text-xl" style={{ color: "var(--text-primary)" }}>
                    {fmtMoney(result.baseline.net_savings)}
                  </div>
                </div>
                <div className="card px-5 py-4" style={{ borderColor: "var(--amber-dim)" }}>
                  <div className="text-xs" style={{ color: "var(--amber)" }}>Simulated net savings / mo</div>
                  <div className="font-mono-num mt-1 text-xl" style={{ color: "var(--text-primary)" }}>
                    {fmtMoney(result.simulated.net_savings)}
                  </div>
                </div>
                <div className="card px-5 py-4">
                  <div className="text-xs" style={{ color: "var(--text-muted)" }}>Additional over 6 months</div>
                  <div
                    className="font-mono-num mt-1 text-xl"
                    style={{ color: result.delta.additional_savings_over_horizon >= 0 ? "var(--verdigris)" : "var(--clay)" }}
                  >
                    {fmtMoney(result.delta.additional_savings_over_horizon, { signDisplay: true })}
                  </div>
                </div>
              </div>

              {result.goal_impact && (
                <div className="card px-5 py-3">
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>Goal impact — </span>
                  <span className="text-xs" style={{ color: "var(--text-primary)" }}>{result.goal_impact.note}</span>
                </div>
              )}

              <div>
                <div className="mb-2 text-xs" style={{ color: "var(--text-muted)" }}>Current vs. simulated, by category</div>
                <div className="card px-4 py-4">
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={chartData}>
                      <CartesianGrid stroke="var(--border-soft)" vertical={false} />
                      <XAxis dataKey="category" tick={{ fill: "var(--text-faint)", fontSize: 11 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
                      <YAxis tick={{ fill: "var(--text-faint)", fontSize: 11 }} axisLine={false} tickLine={false} width={55} />
                      <Tooltip content={<ChartTooltip />} />
                      <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-muted)" }} />
                      <Bar dataKey="Current" fill="#5c6773" radius={[3, 3, 0, 0]} />
                      <Bar dataKey="Simulated" fill="#f2b84b" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="text-xs" style={{ color: "var(--text-faint)" }}>
                Assumptions: baseline built from your last 3 months of actual spending · {result.assumptions_used ? "" : ""}
                {loading ? " recalculating…" : " "}
                {result.disclaimer}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
