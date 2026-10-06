from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import Base, engine
from app.models import models  # noqa: F401 - ensures models are registered before create_all

from app.api.routers.auth_router import router as auth_router
from app.api.routers.transactions_router import router as transactions_router
from app.api.routers.dashboard_router import router as dashboard_router
from app.api.routers.intelligence_router import router as intelligence_router
from app.api.routers.goals_router import router as goals_router
from app.api.routers.simulate_router import router as simulate_router
from app.api.routers.ai_router import router as ai_router

app = FastAPI(title="SpendWise AI", version="1.0.0",
              description="AI-powered personal spending intelligence and financial simulation platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to actual frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


app.include_router(auth_router)
app.include_router(transactions_router)
app.include_router(dashboard_router)
app.include_router(intelligence_router)
app.include_router(goals_router)
app.include_router(simulate_router)
app.include_router(ai_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
