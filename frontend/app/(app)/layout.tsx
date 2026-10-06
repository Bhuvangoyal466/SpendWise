"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { getToken } from "@/lib/api";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    setReady(true);
  }, [router]);

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ background: "var(--ink)" }}>
        <span className="font-mono-num text-sm" style={{ color: "var(--text-faint)" }}>
          loading —
        </span>
      </div>
    );
  }

  return (
    <div className="flex h-screen" style={{ background: "var(--ink)" }}>
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-10 py-10">{children}</div>
      </main>
    </div>
  );
}
