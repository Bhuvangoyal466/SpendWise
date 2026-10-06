# SpendWise AI — Project Plan & Technical Blueprint

## 0. How to read this document

This is the build plan for SpendWise AI: a personal financial intelligence platform, not
an expense tracker with charts bolted on. It's organized the way you should actually
build it — foundation first, intelligence layered on top, simulation last (because
simulation depends on everything below it being correct).

Every module below answers three questions: **what it does, how it's computed
(deterministic vs. ML vs. LLM), and how it feeds the simulator** — because per the
brief, the biggest risk in this project is ending up with a pile of unrelated features
instead of one coherent system.

---

## 1. Product Framing (why this isn't a CRUD app)

The spine of the product is a single causal chain, and every screen should visibly sit
somewhere on it:

```
What happened?  →  Why did it happen?  →  What's likely to happen?  →  What if I change something?
   (Dashboard)      (Behavioral/Anomaly)      (Forecasting)              (Simulator / Time Machine)
```

The What-If Simulator is the hero feature *because* it's the only module that lets a
user act on the insight, not just read it. Everything else in the system exists to feed
it good inputs (accurate baselines, real patterns, real forecasts) so the simulation
isn't just a toy slider — it's a projection built on the same numbers the dashboard
shows.

**Critical evaluation of differentiation (per section 28 of the brief):** the What-If
Simulator alone is a good feature but not a rare one — several finance apps have
basic "reduce category X by Y%" sliders. What makes it genuinely differentiated is:

1. **It's built on the same deterministic engine as the dashboard**, not a separate toy
   calculator — so "reduce shopping 30%" recalculates savings rate, goal feasibility,
   and forecast simultaneously, consistently.
2. **The Financial Time Machine** (retroactive "what if I'd done this 6 months ago")
   is the actually rare part — most apps only simulate forward. Backward simulation
   against real historical data, clearly labeled hypothetical, is a stronger academic
   and product story.
3. Tie the simulator to **behavioral profile and anomaly detection** — e.g., "You're
   flagged as a Weekend Spender; simulate capping weekend spend to weekday
   average" — turns three separate features into one narrative instead of three
   disconnected modules. This is the single highest-leverage design decision in the
   whole project: make every intelligent module a *simulation input*, not a dead end.

---

## 2. Technology Stack (concrete, not just "suggested")

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind | SSR for dashboard perf, one language across stack |
| Charts | Recharts | Composable, good for trend/forecast overlays |
| Backend | Python + FastAPI | Needed anyway for Pandas/scikit-learn; avoids a second service in Node |
| Database | PostgreSQL | Relational integrity between transactions/goals/simulations matters |
| ORM | SQLAlchemy + Alembic | Migrations for evolving schema |
| Data processing | Pandas / NumPy | Analytics layer |
| ML | scikit-learn (Isolation Forest, linear regression) + statsmodels (optional, for seasonal) | Small, explainable, no GPU needed |
| LLM | Anthropic API (Claude), backend-mediated only | Never called directly from frontend; only receives structured JSON, never raw DB access |
| Auth | JWT (FastAPI + passlib) | Simple, sufficient for single-user-per-account model |
| Deployment | Docker Compose (frontend, backend, Postgres) → single VM or Render/Railway | Matches "achievable by one developer" |

**Explicit no's** (per section 19 — don't use tech without a technical purpose): no
Kafka/queues (batch jobs run synchronously or via a simple cron), no vector DB (the
AI assistant does structured retrieval, not semantic search over transactions), no
microservices split (one backend service, modular internally).

---

## 3. Data Model

### Core tables

**users** — id, email, password_hash, name, created_at, base_currency

**transactions** — id, user_id (FK), date, amount (signed decimal), transaction_type
(income/expense), category_id (FK), merchant, description, payment_method,
is_synthetic (bool), created_at

**categories** — id, user_id (nullable for system defaults), name, parent_category
(optional, for grouping e.g. "Dining" under "Food"), icon/color

**recurring_expenses** — id, user_id, merchant, category_id, average_amount,
frequency (weekly/monthly/annual), first_seen, last_seen, confidence_score,
is_active

**goals** — id, user_id, name, target_amount, current_saved, target_date,
created_at

**behavioral_scores** — id, user_id, computed_at, savings_discipline,
expense_stability, spending_consistency, impulse_tendency,
weekend_spending_tendency, subscription_burden, category_concentration,
goal_readiness *(each 0–100, versioned by computed_at so history is preserved)*

**anomalies** — id, user_id, transaction_id (FK), anomaly_score, method
(isolation_forest/statistical), reason (structured, e.g. `{"feature":
"amount_zscore", "value": 4.2}`), reviewed (bool)

**forecasts** — id, user_id, generated_at, category_id (nullable = total),
horizon_days, method, predicted_values (JSON array of {date, value,
confidence_interval})

**simulations** — id, user_id, name, created_at, baseline_snapshot (JSON),
assumptions (JSON: category deltas, income delta, etc.), results (JSON), mode
(forward/time_machine), period_start, period_end

**insights** — id, user_id, generated_at, category (spending_change / anomaly /
goal_risk / subscription / behavioral), structured_finding (JSON — the
deterministic fact), narrative (text — the LLM's explanation of that fact),
dismissed (bool)

**Design rule enforced throughout:** every table that stores a *number the user sees*
(behavioral_scores, anomalies, forecasts, simulations) stores the **structured finding
separately from any generated text**. The LLM is never the source of truth for a
number — only for phrasing.

---

## 4. Backend Architecture (module boundaries)

```
/backend
  /api            → FastAPI routers (transactions, dashboard, goals, simulate, insights, assistant)
  /analytics       → pure deterministic Pandas functions (totals, trends, category breakdowns)
  /behavioral      → feature engineering + scoring (rule-based, documented formulas)
  /ml
     /anomaly      → Isolation Forest wrapper, feature prep, explanation extraction
     /forecast     → method selection (moving avg / linear regression / seasonal) + evaluation
  /simulation      → baseline builder + scenario applier (the engine behind the hero feature)
  /ai
     /insight_engine → takes structured findings → prompts Claude → returns narrative
     /assistant      → intent parsing → routes to analytics functions → Claude phrases the answer
  /data            → synthetic data generator, CSV importer, validators
  /models          → SQLAlchemy models
  /db              → session, migrations
```

The dividing line that matters most: **`/analytics`, `/behavioral`, `/ml`, and
`/simulation` never call the LLM.** They return numbers and structured reasons only.
`/ai` is the *only* layer allowed to call Claude, and it only ever receives already-
computed JSON — it cannot query the database directly. This directly implements
section 14's requirement ("do not let an LLM invent financial conclusions") as an
architectural constraint, not just a prompting guideline.

---

## 5. Analytics Layer (deterministic — the foundation everything else trusts)

Computed with Pandas on each request (or cached with a short TTL once data volume
grows):

- **Aggregates:** income, expenses, net savings, savings rate (%), average
  transaction size, top categories/merchants by total and by count.
- **Trend detection:** period-over-period % change per category using simple
  rolling windows (e.g., trailing 30 vs. prior 30 days). Classify as
  increasing/decreasing/stable using a threshold (e.g., >10% = increasing) —
  explicit, tunable, not a black box.
- **Volatility:** coefficient of variation (std/mean) of weekly spend — feeds
  directly into the `expense_stability` behavioral score.
- **Weekday/weekend split, heatmap data:** groupby on day-of-week / date.
- **Category concentration:** Herfindahl-style index (sum of squared category
  shares) — a single number that says "how spread out is your spending," feeds
  `category_concentration` score.

This layer is the one every other module (behavioral, anomaly, forecast,
simulation) is allowed to depend on. Nothing here depends on ML or the LLM —
this is what lets the system "degrade gracefully" per section 21: if there's not
enough data for forecasting or anomaly detection, the dashboard still fully works.

---

## 6. Behavioral Profile & Spending Personality

Each score is a **documented formula**, not a model — this is what makes it
explainable per section 8/24, and it's the right complexity level for a one-developer
project:

| Score | Formula sketch |
|---|---|
| Savings discipline | savings_rate normalized against a target band (e.g. 0–30% mapped to 0–100) |
| Expense stability | inverse of monthly spend volatility (coefficient of variation) |
| Spending consistency | inverse of day-to-day variance in daily spend |
| Impulse tendency | frequency of "large, non-recurring, non-typical-category" transactions relative to total transaction count |
| Weekend spending tendency | (weekend avg daily spend) / (weekday avg daily spend), normalized |
| Subscription burden | recurring monthly total / total monthly income |
| Category concentration | Herfindahl index from the analytics layer |
| Goal readiness | projected time-to-goal (from forecast) vs. user's target date |

**Spending Personality** is then a simple rule-based classifier on top of these scores
(not a separate ML model — a decision table is more defensible academically because
it's fully explainable):

- `subscription_burden > 70` → **Subscription Heavy**
- `weekend_spending_tendency > 70` and `impulse_tendency < 50` → **Weekend Spender**
- `impulse_tendency > 70` → **Impulse Buyer**
- `savings_discipline > 60` and `expense_stability > 60` → **Balanced Planner**
- fallback → **Developing Profile** (explicitly shown when data is too thin to classify —
  don't force a label)

---

## 7. Anomaly Detection (real ML, kept honest)

- **Method:** Isolation Forest (scikit-learn), trained **per-user** on that user's own
  transaction history — not a global model. This matters both technically (personal
  baselines are what "unusual for you" means) and for the brief's requirement to use
  "user-specific historical behaviour."
- **Features per transaction:** amount (z-score within category), day-of-week,
  category frequency, merchant novelty (has this merchant been seen before),
  deviation from that category's rolling average.
- **Minimum data guard:** don't run Isolation Forest below ~30–50 transactions;
  fall back to a simple statistical rule (z-score > 3 within category) so the feature
  still works for new users — this is the "degrade gracefully" requirement in
  practice.
- **Explanation:** store which feature(s) drove the flag (e.g., "amount is 4.1 standard
  deviations above your typical Dining transaction") — this becomes the structured
  finding that the AI insight engine turns into a sentence. The model's job stops at
  the score + feature attribution; it never generates the explanation text itself.
- **Evaluation:** since there's no labeled ground truth, evaluate qualitatively —
  sample flagged transactions, sanity-check with synthetic injected outliers during
  development (inject known anomalies into synthetic data, confirm recall).

---

## 8. Forecasting

Method selection is **explicit and data-driven**, not a single fixed model:

| Data available | Method |
|---|---|
| < 2 months | Show "insufficient data" — no forecast, don't guess |
| 2–6 months | Weighted moving average (recent months weighted higher) |
| 6+ months, roughly linear trend | Simple linear regression on monthly totals |
| 12+ months | Optional: statsmodels seasonal decomposition to catch e.g. December spending spikes |

- Always output a **confidence interval**, not just a point estimate (even if it's a
  simple ± based on historical residual std dev) — a bare number without uncertainty
  is misleading in a finance product.
- **Evaluation:** backtest — hold out the last N months, forecast them from the
  months before, compute MAE/MAPE, and actually show this evaluation in an
  "about this forecast" tooltip. This is a cheap way to make the ML feel legitimate
  rather than decorative, and it's easy for one developer to implement.
- Actual vs. Forecast is **visually distinct everywhere** (solid vs. dashed line,
  different color) — never allowed to visually blend with historical actuals, per
  section 11/25.

---

## 9. Subscription / Recurring Detection

- Group transactions by merchant, look for repeating intervals (weekly/monthly/
  annual) within a tolerance window, and repeating amounts within a tolerance
  band (e.g. ±10%).
- Confidence score based on: number of repetitions observed, consistency of
  amount, consistency of interval.
- Compute monthly-equivalent burden (annualize annual subscriptions, etc.) and
  feed into `subscription_burden` behavioral score.
- **Explicit guardrail from the brief:** never claim "you're not using this service" —
  only ever claim spending facts ("this recurring charge increased from $12.99 to
  $15.99 in March"), because there's no usage data to justify a usage claim.

---

## 10. Financial Goals

- Store target_amount, current_saved, target_date.
- Derived: remaining_amount = target − current_saved; required_monthly_savings =
  remaining / months_left; feasibility = compare required_monthly_savings against
  the user's actual average savings rate (from analytics) *and* forecasted future
  savings rate (from forecasting layer) — feasibility should use the forecast, not
  just historical average, since that's the more honest predictive answer.
- Goals connect directly into the simulator: "simulate a change and see updated
  goal feasibility" is one of the most concrete, motivating things the What-If tool
  can show.

---

## 11. AI Insight Engine (LLM as explainer, not calculator)

Pipeline for every insight:

1. Deterministic layer computes a **structured finding** — e.g.
   `{"type": "category_increase", "category": "Dining", "prior": 220, "current": 340,
   "pct_change": 54.5}`.
2. That JSON — and *only* that JSON, never raw transactions — is sent to Claude with
   a tightly scoped prompt: "Explain this finding in one or two plain-language
   sentences. Do not add numbers not present in the input. Do not speculate about
   causes not evidenced in the data."
3. Store both the structured_finding and the narrative in `insights`, so the UI can
   always show the number the sentence is based on — this makes the LLM output
   auditable, which matters both for trust and for the academic evaluation story
   (section 24 — "avoid fake AI").

Insight types generated this way: spending increase/decrease, anomaly explanation,
category concentration warning, recurring expense change, behavioral pattern
summary, savings trend, forecast warning ("at this rate you'll exceed last month's
spend by X"), goal feasibility commentary.

---

## 12. AI Financial Assistant (conversational layer)

Explicitly **not** a general chatbot with database access. Flow:

1. User asks a question in natural language.
2. A lightweight intent classifier (can literally be a Claude call with function-
   calling / tool-use, or a simpler keyword+regex router for the MVP) maps the
   question to one of a fixed set of backend functions: `get_category_total`,
   `get_trend`, `get_goal_status`, `run_simulation`, etc.
3. Backend executes the function against real data — all arithmetic happens here.
4. Result JSON goes back to Claude, which phrases the final answer conversationally.

This means "What if I reduce shopping by 20%?" asked in chat literally calls the same
`/simulation` engine used by the slider UI — one engine, two entry points. That
consistency is worth calling out explicitly in your write-up as a design strength.

**Guardrail:** if the parsed intent doesn't map to any available function, the
assistant says so rather than letting the LLM improvise a numeric answer.

---

## 13. Financial What-If Simulator (hero feature — build this carefully)

### Baseline construction
Baseline = actual recent income + actual/forecasted spending per category +
detected recurring expenses, as of "today." This reuses the analytics and forecasting
layers directly — the simulator does not recompute spending logic from scratch.

### Scenario application
User adjustments are simple deltas applied to the baseline:
- category spend: `new_amount = baseline_amount * (1 + pct_change)`
- income: absolute or % change
- recurring/subscription: toggle off, or scale
- savings target: adjust target amount/date

### Output
- New monthly spend, new savings, new savings rate, additional monthly savings,
  updated goal timeline, and a projected N-month trajectory chart (current path vs.
  simulated path, both clearly labeled).
- **Assumptions panel** always visible: "baseline built from your last 3 months,
  forecast method = linear regression" — per section 18, assumptions must be
  visible, not hidden in a black box.

### UI
Sliders per category (bounded, e.g. -50% to +50%) + editable numeric fields for
precision, with the comparison chart updating live (debounced client-side call, or
even client-side recompute using the last-fetched baseline JSON for instant
feedback, hitting the server only for persistence).

---

## 14. Financial Time Machine

Same engine, opposite direction: pick a historical period (e.g., "last 6 months"),
define a hypothetical strategy that *could have* applied then ("what if I'd capped
Dining at $200/month starting in March"), and recompute what savings/goal progress
*would have been*, using the same scenario-application logic as the forward
simulator against real historical baselines instead of a forward-looking one.

Everything shown here is prefixed **"Hypothetical — not what actually happened"**
in the UI, non-negotiably, per section 17. Actual, forecast, and simulated data get
three distinct visual treatments (e.g., solid actual / dashed forecast / dotted
simulated) used consistently across every chart in the app — this single convention
is what keeps three intelligence layers from becoming confusing on screen.

---

## 15. Data Strategy

- **Synthetic data generator**: produces multi-month realistic transaction history
  with seeded categories, merchants, some recurring charges, some injected
  anomalies, mild seasonal variation — needed both for demoing and for testing
  the ML/forecast code paths without waiting on real usage data. Every synthetic
  row is flagged `is_synthetic=true` and the UI shows a banner when viewing
  synthetic data.
- **CSV import**: column-mapping step (map arbitrary bank export columns to the
  schema), validation (dates parse, amounts numeric, dedupe on
  date+amount+description), error report shown to user before commit.
- **Graceful degradation matrix** (build this as an actual lookup the frontend
  checks): below data thresholds, hide/disable forecasting, anomaly detection, and
  behavioral scoring individually — each has its own minimum, not one global
  "not enough data" flag.

---

## 16. Security & Privacy

- Password hashing (bcrypt/argon2 via passlib), JWT with short expiry + refresh
  token.
- All API routes scoped to `user_id` from the token — never trust a client-supplied
  user id.
- TLS in transit (terminate at reverse proxy / platform-managed cert).
- CSV import: size limits, strict parsing (no formula injection into any
  spreadsheet export feature), virus/type checks not needed for CSV but validate
  MIME type regardless.
- Minimum data collection: no need to store more than category/merchant/amount/
  date — avoid ingesting anything like full bank account numbers even if present
  in an import file (strip/ignore such columns).
- Clear DB-level separation: `is_synthetic` flag on transactions, and
  `simulations`/`forecasts` are entirely separate tables from `transactions` — actual
  data is never overwritten or blended with generated data.

---

## 17. Evaluation Strategy (for the academic/technical writeup)

| Component | How to evaluate |
|---|---|
| Anomaly detection | Inject known synthetic anomalies, measure recall; manually review a sample of flags for precision |
| Forecasting | Backtest (holdout last N months), report MAE/MAPE per method, justify method selection thresholds |
| Behavioral scores | Sanity-test against hand-constructed synthetic users (e.g., a deliberately "impulsive" synthetic profile should score high on impulse_tendency) |
| Simulation engine | Unit tests: known baseline + known delta → known expected output (this is pure arithmetic, should be 100% deterministic and testable) |
| AI insight/assistant | Manual review that narrative never contradicts or adds numbers beyond the structured finding it was given |

---

## 18. Build Sequence (realistic for one developer)

1. **Foundation:** schema, auth, transaction CRUD, CSV import, synthetic data
   generator.
2. **Dashboard + analytics layer** (all deterministic) — this alone is a demoable
   product.
3. **Behavioral scores + spending personality** (still deterministic, builds on #2).
4. **Recurring/subscription detection.**
5. **Goals module.**
6. **Anomaly detection (ML).**
7. **Forecasting (ML/stats) + backtesting.**
8. **Simulation engine** (forward) — the hero feature, now has real baselines to
   work from.
9. **Financial Time Machine** (reuses #8's engine against historical data).
10. **AI Insight Engine** (wraps structured findings from #2–#9 in narrative).
11. **AI Assistant** (routes to the same functions built in #2–#9).
12. **Polish pass:** visual hierarchy, trend indicators, empty/low-data states, the
    actual/forecast/simulated visual convention applied consistently everywhere.

Notice steps 1–9 never touch the LLM — the entire analytical and simulation core is
independently correct and testable before AI is layered on top, which is exactly
what section 14's "don't let an LLM invent financial conclusions" is asking for
architecturally, not just as a prompting rule.

---

## 19. Open Decisions Worth Making Early

- **Single currency vs. multi-currency:** brief doesn't require multi-currency —
  recommend single base currency per user for v1, explicitly out of scope, to avoid
  scope creep.
- **Multi-user/household accounts:** not in the brief — recommend single-user
  accounts only for v1.
- **Real bank integration (Plaid etc.):** not required by the brief and adds real
  security/compliance surface area — recommend staying with manual + CSV import
  only, explicitly noted as a "future work" item in your writeup rather than
  attempted.
