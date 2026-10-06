"use client";

import { useEffect, useState } from "react";
import { listGoals, createGoal, deleteGoal, Goal } from "@/lib/api";
import { fmtMoney } from "@/lib/format";
import { SectionHeader, EmptyState } from "@/components/ui";

export default function GoalsPage() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [current, setCurrent] = useState("");
  const [date, setDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  function load() {
    listGoals().then(setGoals).finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await createGoal({
        name,
        target_amount: parseFloat(target),
        current_saved: parseFloat(current || "0"),
        target_date: date,
      });
      setName(""); setTarget(""); setCurrent(""); setDate("");
      setShowForm(false);
      load();
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    await deleteGoal(id);
    load();
  }

  if (loading) return <span className="font-mono-num text-sm" style={{ color: "var(--text-faint)" }}>loading —</span>;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-start justify-between">
        <SectionHeader mark="04" title="Goals" subtitle="Target amounts, feasibility, and how they connect to your simulations." />
        <button
          onClick={() => setShowForm(!showForm)}
          className="rounded px-4 py-2 text-sm font-medium"
          style={{ background: "var(--verdigris)", color: "#0a1410" }}
        >
          {showForm ? "Cancel" : "New goal"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card grid grid-cols-4 gap-3 px-5 py-5">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>Name</span>
            <input required value={name} onChange={(e) => setName(e.target.value)}
              className="rounded border bg-transparent px-3 py-2 text-sm" style={{ borderColor: "var(--border)", color: "var(--text-primary)" }} />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>Target amount</span>
            <input required type="number" min="0" step="0.01" value={target} onChange={(e) => setTarget(e.target.value)}
              className="rounded border bg-transparent px-3 py-2 text-sm font-mono-num" style={{ borderColor: "var(--border)", color: "var(--text-primary)" }} />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>Already saved</span>
            <input type="number" min="0" step="0.01" value={current} onChange={(e) => setCurrent(e.target.value)}
              className="rounded border bg-transparent px-3 py-2 text-sm font-mono-num" style={{ borderColor: "var(--border)", color: "var(--text-primary)" }} />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>Target date</span>
            <input required type="date" value={date} onChange={(e) => setDate(e.target.value)}
              className="rounded border bg-transparent px-3 py-2 text-sm font-mono-num" style={{ borderColor: "var(--border)", color: "var(--text-primary)" }} />
          </label>
          <div className="col-span-4">
            <button type="submit" disabled={saving} className="rounded px-4 py-2 text-sm font-medium disabled:opacity-50"
              style={{ background: "var(--verdigris)", color: "#0a1410" }}>
              {saving ? "Saving…" : "Create goal"}
            </button>
          </div>
        </form>
      )}

      {goals.length === 0 ? (
        <EmptyState title="No goals set yet" body="Create a goal to see whether your current pace gets you there — and to connect it to the What-If Simulator." />
      ) : (
        <div className="flex flex-col gap-3">
          {goals.map((g) => {
            const progress = Math.min((g.current_saved / g.target_amount) * 100, 100);
            return (
              <div key={g.id} className="card px-5 py-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-display text-base font-medium" style={{ color: "var(--text-primary)" }}>{g.name}</div>
                    <div className="font-mono-num mt-0.5 text-sm" style={{ color: "var(--text-muted)" }}>
                      {fmtMoney(g.current_saved)} / {fmtMoney(g.target_amount)} · by {g.target_date}
                    </div>
                  </div>
                  <button onClick={() => handleDelete(g.id)} className="text-xs" style={{ color: "var(--text-faint)" }}>Remove</button>
                </div>
                <div className="mt-3 h-1.5 rounded-full" style={{ background: "var(--border-soft)" }}>
                  <div className="h-1.5 rounded-full" style={{ width: `${progress}%`, background: g.feasible ? "var(--verdigris)" : "var(--clay)" }} />
                </div>
                <div className="mt-3 flex items-center justify-between text-xs">
                  <span style={{ color: "var(--text-muted)" }}>
                    Requires <span className="font-mono-num" style={{ color: "var(--text-primary)" }}>{fmtMoney(g.required_monthly_savings)}</span>/mo
                  </span>
                  <span style={{ color: g.feasible ? "var(--verdigris)" : "var(--clay)" }}>
                    {g.feasible ? "On track" : "At risk"}
                  </span>
                </div>
                <p className="mt-2 text-xs" style={{ color: "var(--text-faint)" }}>{g.feasibility_note}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
