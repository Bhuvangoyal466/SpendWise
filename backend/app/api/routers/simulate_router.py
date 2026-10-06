from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.models import User, Simulation, SimulationMode, Goal
from app.schemas.schemas import SimulationRequest, SimulationResult
from app.api.auth import get_current_user
from app.api.deps import load_transactions_for_user
from app.analytics.core import transactions_to_df
from app.simulation import engine as simulation
from app.goals.service import evaluate_goal
from app.utils.json_safe import to_jsonable
from datetime import date

router = APIRouter(prefix="/api/simulate", tags=["simulation"])


@router.post("", response_model=SimulationResult)
def run_simulation(payload: SimulationRequest, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    transactions = load_transactions_for_user(db, user.id)
    df = transactions_to_df(transactions)
    if df.empty:
        raise HTTPException(status_code=400, detail="No transaction data available to simulate against.")

    assumptions = payload.assumptions.dict()

    if payload.mode == "time_machine":
        if not payload.period_start or not payload.period_end:
            raise HTTPException(status_code=400, detail="time_machine mode requires period_start and period_end.")
        result = simulation.run_time_machine_simulation(df, assumptions, payload.period_start, payload.period_end)
        mode = SimulationMode.time_machine
        disclaimer = result["disclaimer"]
    else:
        result = simulation.run_forward_simulation(df, assumptions, horizon_months=payload.horizon_months)
        mode = SimulationMode.forward
        disclaimer = "Simulated projection based on your recent 3-month spending average — not a guarantee of future results."

        # tie to goals if any exist (plan section 13: connect simulation with goals)
        goals = db.query(Goal).filter(Goal.user_id == user.id).all()
        if goals:
            g = goals[0]
            evaluation = evaluate_goal(g.target_amount, g.current_saved, g.target_date, date.today(),
                                        actual_avg_monthly_savings=result["baseline"]["net_savings"])
            result["goal_impact"] = simulation.apply_goal_impact(result, evaluation["required_monthly_savings"])

    record = Simulation(
        user_id=user.id, mode=mode, baseline_snapshot=to_jsonable(result["baseline"]),
        assumptions=to_jsonable(assumptions), results=to_jsonable(result),
        period_start=payload.period_start, period_end=payload.period_end,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return SimulationResult(
        id=record.id, mode=payload.mode, baseline=result["baseline"], simulated=result["simulated"],
        delta=result["delta"], trajectory=result["trajectory"], assumptions_used=result["assumptions_used"],
        goal_impact=result.get("goal_impact"), disclaimer=disclaimer,
    )
