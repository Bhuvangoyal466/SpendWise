export function SectionHeader({
  mark,
  title,
  subtitle,
}: {
  mark: string;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-6">
      <div className="flex items-baseline gap-2">
        <span className="font-mono-num text-xs" style={{ color: "var(--text-faint)" }}>
          {mark}
        </span>
        <h2 className="font-display text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
          {title}
        </h2>
      </div>
      {subtitle && (
        <p className="mt-1 text-sm" style={{ color: "var(--text-muted)" }}>
          {subtitle}
        </p>
      )}
    </div>
  );
}

export function StatCard({
  label,
  value,
  delta,
  deltaLabel,
  tone = "neutral",
}: {
  label: string;
  value: string;
  delta?: string;
  deltaLabel?: string;
  tone?: "positive" | "negative" | "neutral";
}) {
  const deltaColor =
    tone === "positive" ? "var(--verdigris)" : tone === "negative" ? "var(--clay)" : "var(--text-muted)";
  return (
    <div className="card px-5 py-4">
      <div className="text-xs" style={{ color: "var(--text-muted)" }}>
        {label}
      </div>
      <div className="font-mono-num mt-1.5 text-2xl font-medium" style={{ color: "var(--text-primary)" }}>
        {value}
      </div>
      {delta && (
        <div className="font-mono-num mt-1 text-xs" style={{ color: deltaColor }}>
          {delta} {deltaLabel && <span style={{ color: "var(--text-faint)" }}>{deltaLabel}</span>}
        </div>
      )}
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="card flex flex-col items-start gap-1 px-5 py-6">
      <div className="font-display text-sm font-medium" style={{ color: "var(--text-primary)" }}>
        {title}
      </div>
      <div className="text-sm" style={{ color: "var(--text-muted)" }}>
        {body}
      </div>
    </div>
  );
}
