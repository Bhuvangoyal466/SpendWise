"use client";

import { useEffect, useState } from "react";
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { getDashboardSummary, getBehavioralProfile, getAnomalies, getForecast, getSubscriptions, DashboardSummary, BehavioralProfile, Anomaly, Forecast, RecurringExpense } from "@/lib/api";
import { fmtMoney, fmtPct } from "@/lib/format";
import { SectionHeader, StatCard, EmptyState } from "@/components/ui";

const CATEGORY_COLORS = ["#4fd1a5", "#f2b84b", "#e8927c", "#7ea9c9", "#b98fd6", "#d1a15e", "#6bbfa0", "#c97a9e"];

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="card-raised px-3 py-2 text-xs">
      <div style={{ color: "var(--text-muted)" }}>{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} className="font-mono-num" style={{ color: p.color || "var(--text-primary)" }}>
          {p.name}: {fmtMoney(p.value)}
        </div>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [behavioral, setBehavioral] = useState<BehavioralProfile | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [subscriptions, setSubscriptions] = useState<RecurringExpense[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getDashboardSummary(), getBehavioralProfile(), getAnomalies(), getForecast(undefined, 3), getSubscriptions()])
      .then(([s, b, a, f, r]) => {
        setSummary(s);
        setBehavioral(b);
        setAnomalies(a.slice(0, 3));
        setForecast(f);
        setSubscriptions(r);
      })
      .catch(() => setError("Could not load your dashboard. Is the backend running?"));
  }, []);

  if (error) return <EmptyState title="Something went wrong" body={error} />;
  if (!summary) {
    return <span className="font-mono-num text-sm" style={{ color: "var(--text-faint)" }}>loading —</span>;
  }

  const hasData = summary.total_income > 0 || summary.total_expenses > 0;
  if (!hasData) {
    return (
      <EmptyState
        title="No transactions yet"
        body="Add transactions, import a CSV, or seed sample data from the login screen to see your dashboard come alive."
      />
    );
  }

  return (
    <div className="flex flex-col gap-10">
      <div>
        <SectionHeader
          mark="01"
          title="What happened"
          subtitle={`${summary.period_start} → ${summary.period_end}`}
        />
        <div className="grid grid-cols-4 gap-3">
          <StatCard label="Income" value={fmtMoney(summary.total_income)} />
          <StatCard label="Expenses" value={fmtMoney(summary.total_expenses)} />
          <StatCard
            label="Net savings"
            value={fmtMoney(summary.net_savings)}
            tone={summary.net_savings >= 0 ? "positive" : "negative"}
          />
          <StatCard
            label="Savings rate"
            value={fmtPct(summary.savings_rate)}
            tone={summary.savings_rate >= 0 ? "positive" : "negative"}
          />
        </div>
      </div>

      <div>
        <SectionHeader mark="—" title="Income vs. expenses" subtitle="Monthly trend across your full history" />
        <div className="card px-4 py-4">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={summary.monthly_trend}>
              <CartesianGrid stroke="var(--border-soft)" vertical={false} />
              <XAxis dataKey="month" tick={{ fill: "var(--text-faint)", fontSize: 11 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
              <YAxis tick={{ fill: "var(--text-faint)", fontSize: 11 }} axisLine={false} tickLine={false} width={60} />
              <Tooltip content={<ChartTooltip />} />
              <Line type="monotone" dataKey="income" name="Income" stroke="#4fd1a5" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="expense" name="Expenses" stroke="#e8927c" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div>
          <SectionHeader mark="—" title="Top categories" />
          <div className="card px-4 py-4">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={summary.top_categories} layout="vertical" margin={{ left: 10 }}>
                <CartesianGrid stroke="var(--border-soft)" horizontal={false} />
                <XAxis type="number" tick={{ fill: "var(--text-faint)", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis
                  type="category"
                  dataKey="category"
                  tick={{ fill: "var(--text-muted)", fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                  width={90}
                />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="total" name="Spent" radius={[0, 3, 3, 0]}>
                  {summary.top_categories.map((_, i) => (
                    <Cell key={i} fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div>
          <SectionHeader mark="—" title="Behavioral profile" subtitle={behavioral?.personality_label} />
          <div className="card flex flex-col gap-3 px-4 py-4">
            {behavioral && !("status" in (behavioral.explanation || {})) ? (
              [
                ["Savings discipline", behavioral.savings_discipline],
                ["Expense stability", behavioral.expense_stability],
                ["Impulse tendency", behavioral.impulse_tendency],
                ["Weekend spending", behavioral.weekend_spending_tendency],
                ["Subscription burden", behavioral.subscription_burden],
              ].map(([label, val]) => (
                <div key={label as string} className="flex items-center gap-3">
                  <span className="w-36 text-xs" style={{ color: "var(--text-muted)" }}>{label}</span>
                  <div className="h-1.5 flex-1 rounded-full" style={{ background: "var(--border-soft)" }}>
                    <div
                      className="h-1.5 rounded-full"
                      style={{ width: `${val}%`, background: "var(--verdigris)" }}
                    />
                  </div>
                  <span className="font-mono-num w-8 text-right text-xs" style={{ color: "var(--text-primary)" }}>
                    {Math.round(val as number)}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                {behavioral?.explanation?.status || "Not enough data yet to build your behavioral profile."}
              </p>
            )}
          </div>
        </div>
      </div>


      <div className="grid grid-cols-2 gap-6">
        <div>
          <SectionHeader mark="—" title="Spending forecast" subtitle={forecast?.insufficient_data ? "Not enough monthly history yet" : `${forecast?.method || "Model"} · next 3 months`} />
          <div className="card px-4 py-4">
            {forecast?.points?.length ? (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={forecast.points}>
                  <CartesianGrid stroke="var(--border-soft)" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: "var(--text-faint)", fontSize: 11 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
                  <YAxis tick={{ fill: "var(--text-faint)", fontSize: 11 }} axisLine={false} tickLine={false} width={60} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="upper" stroke="none" fill="var(--border-soft)" name="Upper" />
                  <Line type="monotone" dataKey="value" stroke="var(--verdigris)" strokeWidth={2} dot={false} name="Forecast" />
                </AreaChart>
              </ResponsiveContainer>
            ) : <p className="text-sm" style={{ color: "var(--text-muted)" }}>Keep adding monthly history to unlock forecasting.</p>}
          </div>
        </div>
        <div>
          <SectionHeader mark="—" title="Recurring expenses" subtitle="Detected patterns in your transaction history" />
          <div className="card divide-y" style={{ borderColor: "var(--border-soft)" }}>
            {subscriptions.length ? subscriptions.slice(0, 5).map((r) => (
              <div key={`${r.merchant}-${r.first_seen}`} className="flex items-center justify-between px-4 py-3">
                <div><div className="text-sm">{r.merchant}</div><div className="text-xs" style={{ color: "var(--text-faint)" }}>{r.category || "Uncategorized"} · {r.frequency}</div></div>
                <div className="font-mono-num text-sm">{fmtMoney(r.monthly_equivalent)}<span className="ml-1 text-[10px]" style={{ color: "var(--text-faint)" }}>/mo</span></div>
              </div>
            )) : <p className="px-4 py-5 text-sm" style={{ color: "var(--text-muted)" }}>No recurring patterns detected yet.</p>}
          </div>
        </div>
      </div>

      {anomalies.length > 0 && (
        <div>
          <SectionHeader mark="—" title="Recently flagged" subtitle="Unusual transactions detected in your history" />
          <div className="flex flex-col gap-2">
            {anomalies.map((a) => (
              <div key={a.id} className="card flex items-center justify-between px-4 py-3">
                <div>
                  <div className="text-sm" style={{ color: "var(--text-primary)" }}>
                    {a.merchant} <span style={{ color: "var(--text-faint)" }}>· {a.category}</span>
                  </div>
                  <div className="text-xs" style={{ color: "var(--text-muted)" }}>{a.reason.message}</div>
                </div>
                <div className="font-mono-num text-sm" style={{ color: "var(--clay)" }}>{fmtMoney(a.amount)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
