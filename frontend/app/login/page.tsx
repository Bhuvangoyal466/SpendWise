"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login, signup, seedSyntheticData } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [seedData, setSeedData] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === "signup") {
        await signup(email, password, name || undefined);
      }
      await login(email, password);
      if (mode === "signup" && seedData) {
        await seedSyntheticData();
      }
      router.push("/dashboard");
    } catch (err: any) {
      setError(mode === "login" ? "Incorrect email or password." : "Could not create account — email may already be registered.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-6" style={{ background: "var(--ink)" }}>
      <div className="w-full max-w-sm">
        <div className="mb-10 flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded" style={{ background: "var(--verdigris)" }}>
            <span className="font-mono-num text-sm font-semibold text-black">₹</span>
          </div>
          <span className="font-display text-lg font-semibold tracking-tight">SpendWise AI</span>
        </div>

        <h1 className="font-display text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>
          {mode === "login" ? "Welcome back" : "Create your account"}
        </h1>
        <p className="mt-2 text-sm" style={{ color: "var(--text-muted)" }}>
          {mode === "login"
            ? "Sign in to see what happened, why, and what's next."
            : "Set up your financial intelligence dashboard."}
        </p>

        <div className="ledger-tick" />

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {mode === "signup" && (
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>Name</span>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="rounded border bg-transparent px-3 py-2 text-sm outline-none"
                style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
                placeholder="Jordan Rivera"
              />
            </label>
          )}
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="rounded border bg-transparent px-3 py-2 text-sm outline-none"
              style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
              placeholder="you@example.com"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>Password</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded border bg-transparent px-3 py-2 text-sm outline-none"
              style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
              placeholder="••••••••"
            />
          </label>

          {mode === "signup" && (
            <label className="flex items-center gap-2 pt-1">
              <input
                type="checkbox"
                checked={seedData}
                onChange={(e) => setSeedData(e.target.checked)}
                className="h-3.5 w-3.5"
              />
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                Populate with 8 months of sample data so I can explore immediately
              </span>
            </label>
          )}

          {error && (
            <p className="text-xs" style={{ color: "var(--clay)" }}>{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="mt-2 rounded px-4 py-2.5 text-sm font-medium transition-opacity disabled:opacity-50"
            style={{ background: "var(--verdigris)", color: "#0a1410" }}
          >
            {loading ? "Working…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <button
          onClick={() => setMode(mode === "login" ? "signup" : "login")}
          className="mt-6 text-xs"
          style={{ color: "var(--text-muted)" }}
        >
          {mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}
        </button>
      </div>
    </div>
  );
}
