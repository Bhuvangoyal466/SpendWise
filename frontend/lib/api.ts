/**
 * Thin typed client over the SpendWise AI backend. Every function here maps
 * 1:1 to a FastAPI route — no business logic lives in the frontend; all
 * arithmetic, ML, and simulation happens server-side (see project plan).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("spendwise_token");
}

export function setToken(token: string) {
  localStorage.setItem("spendwise_token", token);
}

export function clearToken() {
  localStorage.removeItem("spendwise_token");
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((options.headers as Record<string, string>) || {}),
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, text || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ---------- Auth ----------

export async function signup(email: string, password: string, name?: string) {
  return request("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password, name }),
  });
}

export async function login(email: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username: email, password });
  const res = await request<{ access_token: string }>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  setToken(res.access_token);
  return res.access_token;
}

// ---------- Transactions ----------

export interface Transaction {
  id: string;
  date: string;
  amount: number;
  transaction_type: "income" | "expense";
  category?: string;
  merchant?: string;
  description?: string;
  payment_method?: string;
  is_synthetic: boolean;
}

export const seedSyntheticData = (months = 8) =>
  request<{ status: string; transactions_created: number }>(`/api/transactions/seed-synthetic?months=${months}`, {
    method: "POST",
  });

export const listTransactions = (params: { limit?: number; category?: string } = {}) => {
  const qs = new URLSearchParams();
  if (params.limit) qs.set("limit", String(params.limit));
  if (params.category) qs.set("category", params.category);
  return request<Transaction[]>(`/api/transactions?${qs.toString()}`);
};

export const createTransaction = (payload: Partial<Transaction> & { category_name?: string }) =>
  request<Transaction>("/api/transactions", { method: "POST", body: JSON.stringify(payload) });

export const deleteTransaction = (id: string) =>
  request(`/api/transactions/${id}`, { method: "DELETE" });

export const importCsv = async (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return request<{ rows_received: number; rows_imported: number; rows_skipped: number; errors: string[] }>(
    "/api/transactions/import-csv",
    { method: "POST", body: form }
  );
};

// ---------- Dashboard ----------

export interface DashboardSummary {
  period_start: string;
  period_end: string;
  total_income: number;
  total_expenses: number;
  net_savings: number;
  savings_rate: number;
  average_transaction: number;
  top_categories: { category: string; total: number; count: number; average: number; pct_of_total: number }[];
  top_merchants: { merchant: string; total: number; count: number; average: number; largest: number }[];
  category_breakdown: { category: string; total: number; average: number; count: number; pct_of_total: number }[];
  monthly_trend: { month: string; income: number; expense: number; net: number }[];
  weekday_weekend: { weekday_avg_daily: number; weekend_avg_daily: number };
  category_concentration: number;
}

export const getDashboardSummary = () => request<DashboardSummary>("/api/dashboard/summary");

// ---------- Behavioral ----------

export interface BehavioralProfile {
  savings_discipline: number;
  expense_stability: number;
  spending_consistency: number;
  impulse_tendency: number;
  weekend_spending_tendency: number;
  subscription_burden: number;
  category_concentration: number;
  goal_readiness: number;
  personality_label: string;
  explanation: Record<string, string>;
}

export const getBehavioralProfile = () => request<BehavioralProfile>("/api/behavioral/profile");

// ---------- Anomalies ----------

export interface Anomaly {
  id: string;
  transaction_id: string;
  date: string;
  amount: number;
  merchant?: string;
  category?: string;
  anomaly_score: number;
  method: string;
  reason: { feature: string; value: number; message: string };
}

export const getAnomalies = () => request<Anomaly[]>("/api/anomalies");

// ---------- Forecast ----------

export interface ForecastPoint {
  date: string;
  value: number;
  lower: number;
  upper: number;
}

export interface Forecast {
  method: string;
  horizon_days: number;
  category?: string;
  points: ForecastPoint[];
  evaluation?: { mae: number; mape: number; holdout_months: number };
  insufficient_data: boolean;
}

export const getForecast = (category?: string, horizonMonths = 3) => {
  const qs = new URLSearchParams({ horizon_months: String(horizonMonths) });
  if (category) qs.set("category", category);
  return request<Forecast>(`/api/forecast?${qs.toString()}`);
};

// ---------- Subscriptions ----------

export interface RecurringExpense {
  merchant: string;
  category?: string;
  average_amount: number;
  frequency: string;
  monthly_equivalent: number;
  confidence_score: number;
  first_seen: string;
  last_seen: string;
  is_active: boolean;
}

export const getSubscriptions = () => request<RecurringExpense[]>("/api/subscriptions");

// ---------- Goals ----------

export interface Goal {
  id: string;
  name: string;
  target_amount: number;
  current_saved: number;
  target_date: string;
  remaining_amount: number;
  months_left: number;
  required_monthly_savings: number;
  feasible: boolean | null;
  feasibility_note: string;
}

export const listGoals = () => request<Goal[]>("/api/goals");
export const createGoal = (payload: { name: string; target_amount: number; current_saved: number; target_date: string }) =>
  request<Goal>("/api/goals", { method: "POST", body: JSON.stringify(payload) });
export const deleteGoal = (id: string) => request(`/api/goals/${id}`, { method: "DELETE" });

// ---------- Simulation ----------

export interface SimulationRequest {
  mode: "forward" | "time_machine";
  assumptions: {
    category_pct_changes: Record<string, number>;
    income_pct_change?: number;
    disable_recurring_merchants?: string[];
  };
  horizon_months?: number;
  period_start?: string;
  period_end?: string;
}

export interface SimulationResult {
  id: string;
  mode: string;
  baseline: Record<string, any>;
  simulated: Record<string, any>;
  delta: Record<string, any>;
  trajectory: Record<string, any>[];
  assumptions_used: Record<string, any>;
  goal_impact?: Record<string, any>;
  disclaimer: string;
}

export const runSimulation = (payload: SimulationRequest) =>
  request<SimulationResult>("/api/simulate", { method: "POST", body: JSON.stringify(payload) });

// ---------- Insights ----------

export interface Insight {
  id: string;
  category: string;
  structured_finding: Record<string, any>;
  narrative?: string;
  generated_at: string;
}

export const generateInsights = () => request<Insight[]>("/api/insights/generate", { method: "POST" });
export const listInsights = () => request<Insight[]>("/api/insights");

// ---------- Assistant ----------

export interface AssistantResponse {
  answer: string;
  intent: string;
  data_used: Record<string, any>;
}

export const askAssistant = (question: string) =>
  request<AssistantResponse>("/api/assistant/ask", { method: "POST", body: JSON.stringify({ question }) });

export { ApiError };
