"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { createTransaction, deleteTransaction, importCsv, listTransactions, seedSyntheticData, Transaction } from "@/lib/api";
import { fmtMoney } from "@/lib/format";
import { EmptyState, SectionHeader } from "@/components/ui";

const DEFAULT_CATEGORIES = ["Groceries", "Dining", "Transport", "Shopping", "Entertainment", "Utilities", "Health", "Housing"];

export default function TransactionsPage() {
  const [rows, setRows] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [type, setType] = useState<"expense" | "income">("expense");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("Dining");
  const [merchant, setMerchant] = useState("");
  const [description, setDescription] = useState("");

  async function load() {
    setLoading(true);
    try { setRows(await listTransactions({ limit: 2000 })); }
    catch { setError("Could not load transactions. Check that the backend is running."); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const value = Number(amount);
    if (!date || !Number.isFinite(value) || value <= 0) { setError("Enter a valid date and amount."); return; }
    setSaving(true); setError(null); setMessage(null);
    try {
      await createTransaction({ date, amount: value, transaction_type: type, category_name: category || undefined, merchant: merchant || undefined, description: description || undefined });
      setAmount(""); setMerchant(""); setDescription("");
      setMessage("Transaction added.");
      await load();
    } catch { setError("Could not add the transaction."); }
    finally { setSaving(false); }
  }

  async function remove(id: string) {
    if (!window.confirm("Delete this transaction?")) return;
    try { await deleteTransaction(id); setRows((r) => r.filter((x) => x.id !== id)); }
    catch { setError("Could not delete the transaction."); }
  }

  async function handleCsv(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null); setMessage(null);
    try {
      const result = await importCsv(file);
      setMessage(`Imported ${result.rows_imported} row(s); skipped ${result.rows_skipped}.`);
      if (result.errors.length) setError(result.errors.slice(0, 3).join(" | "));
      await load();
    } catch (err: any) { setError(err?.message || "CSV import failed."); }
    e.target.value = "";
  }

  async function seed() {
    setSaving(true); setError(null); setMessage(null);
    try { const r = await seedSyntheticData(8); setMessage(`Added ${r.transactions_created} sample transactions.`); await load(); }
    catch { setError("Could not generate sample data."); }
    finally { setSaving(false); }
  }

  return (
    <div className="flex flex-col gap-8">
      <SectionHeader mark="07" title="Transactions" subtitle="Add, import, review, and remove the data that powers SpendWise." />
      {(message || error) && <div className="card px-4 py-3 text-sm" style={{ color: error ? "var(--clay)" : "var(--verdigris)" }}>{error || message}</div>}
      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <form onSubmit={submit} className="card flex flex-col gap-4 px-5 py-5">
          <div className="text-sm font-medium">Add transaction</div>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1.5 text-xs"><span style={{ color: "var(--text-muted)" }}>Type</span><select value={type} onChange={(e) => setType(e.target.value as "expense" | "income")} className="rounded border bg-transparent px-3 py-2 text-sm" style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}><option value="expense">Expense</option><option value="income">Income</option></select></label>
            <label className="flex flex-col gap-1.5 text-xs"><span style={{ color: "var(--text-muted)" }}>Date</span><input required type="date" value={date} onChange={(e) => setDate(e.target.value)} className="rounded border bg-transparent px-3 py-2 text-sm font-mono-num" style={{ borderColor: "var(--border)", color: "var(--text-primary)" }} /></label>
          </div>
          <label className="flex flex-col gap-1.5 text-xs"><span style={{ color: "var(--text-muted)" }}>Amount</span><input required min="0.01" step="0.01" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="125.00" className="rounded border bg-transparent px-3 py-2 text-sm font-mono-num" style={{ borderColor: "var(--border)", color: "var(--text-primary)" }} /></label>
          <label className="flex flex-col gap-1.5 text-xs"><span style={{ color: "var(--text-muted)" }}>Category</span><input list="categories" value={category} onChange={(e) => setCategory(e.target.value)} className="rounded border bg-transparent px-3 py-2 text-sm" style={{ borderColor: "var(--border)", color: "var(--text-primary)" }} /><datalist id="categories">{DEFAULT_CATEGORIES.map((c) => <option key={c} value={c} />)}</datalist></label>
          <label className="flex flex-col gap-1.5 text-xs"><span style={{ color: "var(--text-muted)" }}>Merchant</span><input value={merchant} onChange={(e) => setMerchant(e.target.value)} placeholder="Merchant or source" className="rounded border bg-transparent px-3 py-2 text-sm" style={{ borderColor: "var(--border)", color: "var(--text-primary)" }} /></label>
          <label className="flex flex-col gap-1.5 text-xs"><span style={{ color: "var(--text-muted)" }}>Description</span><input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional note" className="rounded border bg-transparent px-3 py-2 text-sm" style={{ borderColor: "var(--border)", color: "var(--text-primary)" }} /></label>
          <button disabled={saving} className="rounded px-4 py-2.5 text-sm font-medium disabled:opacity-50" style={{ background: "var(--verdigris)", color: "#0a1410" }}>{saving ? "Saving…" : "Add transaction"}</button>
          <div className="ledger-tick" />
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>Import CSV</div>
          <input type="file" accept=".csv,text/csv" onChange={handleCsv} className="text-xs" />
          
          <p className="text-[11px]" style={{ color: "var(--text-faint)" }}>CSV columns: date, amount, type; category, merchant, description and payment_method are optional.</p>
        </form>
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between border-b px-5 py-4" style={{ borderColor: "var(--border)" }}><div className="text-sm font-medium">Recent transactions</div><div className="font-mono-num text-xs" style={{ color: "var(--text-faint)" }}>{rows.length} loaded</div></div>
          {loading ? <div className="px-5 py-8 text-sm" style={{ color: "var(--text-faint)" }}>loading —</div> : rows.length === 0 ? <div className="p-5"><EmptyState title="No transactions yet" body="Add one manually, import a CSV, or generate sample data." /></div> : (
            <div className="max-h-[680px] overflow-auto">
              <table className="w-full text-left text-sm"><thead className="sticky top-0" style={{ background: "var(--surface-raised)" }}><tr className="text-xs" style={{ color: "var(--text-muted)" }}><th className="px-4 py-3">Date</th><th className="px-4 py-3">Description</th><th className="px-4 py-3">Category</th><th className="px-4 py-3 text-right">Amount</th><th className="px-4 py-3" /></tr></thead><tbody>{rows.map((r) => <tr key={r.id} className="border-t" style={{ borderColor: "var(--border-soft)" }}><td className="px-4 py-3 font-mono-num text-xs" style={{ color: "var(--text-muted)" }}>{r.date}</td><td className="px-4 py-3"><div>{r.merchant || r.description || "—"}</div><div className="text-[11px]" style={{ color: "var(--text-faint)" }}>{r.description || ""}</div></td><td className="px-4 py-3 text-xs" style={{ color: "var(--text-muted)" }}>{r.category || "Uncategorized"}</td><td className="px-4 py-3 text-right font-mono-num" style={{ color: r.transaction_type === "income" ? "var(--verdigris)" : "var(--text-primary)" }}>{r.transaction_type === "income" ? "+" : "−"}{fmtMoney(r.amount)}</td><td className="px-4 py-3 text-right"><button onClick={() => remove(r.id)} className="text-xs" style={{ color: "var(--text-faint)" }}>Delete</button></td></tr>)}</tbody></table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
