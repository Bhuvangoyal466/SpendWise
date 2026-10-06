"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", mark: "01" },
  { href: "/transactions", label: "Transactions", mark: "07" },
  { href: "/simulator", label: "What-If Simulator", mark: "02" },
  { href: "/time-machine", label: "Time Machine", mark: "03" },
  { href: "/goals", label: "Goals", mark: "04" },
  { href: "/insights", label: "Insights", mark: "05" },
  { href: "/assistant", label: "Assistant", mark: "06" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  function handleLogout() {
    clearToken();
    router.push("/login");
  }

  return (
    <aside
      className="flex h-screen w-60 shrink-0 flex-col border-r px-5 py-6"
      style={{ borderColor: "var(--border)", background: "var(--surface)" }}
    >
      <div className="mb-8 flex items-center gap-2 px-1">
        <div
          className="flex h-7 w-7 items-center justify-center rounded"
          style={{ background: "var(--verdigris)" }}
        >
          <span className="font-mono-num text-xs font-semibold text-black">₹</span>
        </div>
        <span className="font-display text-[15px] font-semibold tracking-tight">SpendWise AI</span>
      </div>

      <nav className="flex flex-1 flex-col gap-0.5">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className="group flex items-center gap-3 rounded px-3 py-2.5 text-sm transition-colors"
              style={{
                background: active ? "var(--surface-raised)" : "transparent",
                color: active ? "var(--text-primary)" : "var(--text-muted)",
              }}
            >
              <span
                className="font-mono-num text-[10px]"
                style={{ color: active ? "var(--amber)" : "var(--text-faint)" }}
              >
                {item.mark}
              </span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="ledger-tick" />

      <button
        onClick={handleLogout}
        className="rounded px-3 py-2 text-left text-sm transition-colors hover:text-[var(--text-primary)]"
        style={{ color: "var(--text-muted)" }}
      >
        Sign out
      </button>
    </aside>
  );
}
