# SpendWise AI

AI-powered personal spending intelligence and financial simulation platform.
Built per the project plan: deterministic analytics → behavioral profiling →
ML anomaly detection & forecasting → the What-If Simulator / Financial Time
Machine → AI narration on top of all of it.

Full architecture rationale lives in `spendwise_ai_project_plan.md` (the
companion planning document). This README is just "how do I run it."

## What's implemented

- **Backend** (`/backend`) — FastAPI + SQLAlchemy + Pandas/scikit-learn.
  Every module from the plan is implemented and covered by an end-to-end
  smoke test (`backend/tests/smoke_test.py`): auth, transactions/CSV
  import/synthetic seeding, dashboard analytics, behavioral scoring,
  Isolation Forest anomaly detection, forecasting with backtest evaluation,
  subscription detection, goals, the What-If Simulator + Time Machine, and
  the AI insight engine + assistant (both with a template fallback when no
  `ANTHROPIC_API_KEY` is set, so the app works fully offline).
- **Frontend** (`/frontend`) — Next.js 15 (App Router) + TypeScript +
  Tailwind + Recharts. Pages: login/signup, dashboard, What-If Simulator,
  Financial Time Machine, goals, insights, and the AI assistant chat.

## Quick start (local, no Docker)

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# optional: cp .env.example .env and fill in ANTHROPIC_API_KEY, SECRET_KEY, etc.
# without a .env, it runs on SQLite with dev defaults — good enough to try it out.

uvicorn app.main:app --reload --port 8000
```

Runs on `http://127.0.0.1:8000`. Interactive API docs at `/docs`.

Verify everything works end-to-end:
```bash
python tests/smoke_test.py
```

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
cp .env.local.example .env.local   # points at http://127.0.0.1:8000 by default
npm run dev
```

Runs on `http://127.0.0.1:3000`. Sign up, tick "Populate with sample data,"
and you'll land on a fully populated dashboard immediately.

## Quick start (Docker)

```bash
docker compose up --build
```

Backend on `:8000`, frontend on `:3000`, Postgres on `:5432`. Set
`ANTHROPIC_API_KEY` in your shell before running if you want real
LLM-generated narratives instead of the template fallback.

## Trying the hero feature

1. Sign up with sample data enabled (or import your own CSV under
   Transactions → the `/api/transactions/import-csv` endpoint).
2. Go to **What-If Simulator** — drag any category slider and watch net
   savings, savings rate, and the 6-month trajectory update live, alongside
   how it changes your goal feasibility.
3. Go to **Time Machine** — pick a category, a hypothetical % change, and a
   real historical date range, and see what your actual savings *would have
   been* had you made that change. Everything there is explicitly labeled
   hypothetical.

## Notes on the AI layer

`ANTHROPIC_API_KEY` is optional everywhere. Without it, `/api/insights` and
`/api/assistant/ask` still work — they return the same structured, correct
numbers, just phrased by a simple deterministic template instead of Claude.
This is intentional: it demonstrates the plan's core architectural rule (the
LLM only ever explains a number that was already computed; it's never the
source of the number) even in a fully offline environment.

## CSV import format

Flexible column order, case-insensitive headers. Required: `date`, `amount`,
`type` (`income`/`expense`). Optional: `category`, `merchant`, `description`,
`payment_method`. Dates accepted as `YYYY-MM-DD`, `MM/DD/YYYY`, or
`DD/MM/YYYY`.

## Known limitations (by design, see plan section 19)

- Single currency per user, no multi-user/household accounts, no live bank
  integration (Plaid etc.) — all explicitly out of scope per the plan to keep
  the project realistically buildable by one developer.
- Anomaly detection and forecasting both degrade gracefully (documented
  minimum-data thresholds) rather than producing unreliable output on thin
  data — this is intentional, not a bug, if you see "insufficient data"
  responses on a brand-new account before seeding/importing history.
