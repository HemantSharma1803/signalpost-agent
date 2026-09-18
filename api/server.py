"""FastAPI wrapper so the agent can be deployed and demoed as a live web
service, e.g. on Render.com. Run with:

    uvicorn api.server:app --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from src.agent import process_one
from src.budget_guard import BudgetGuard
from src.brreg_client import CompanyNotFound

app = FastAPI(
    title="Signalpost Agent",
    description="Finds verified Norwegian company information by org number.",
    version="1.0.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/company/{org_number}")
def get_company(org_number: str) -> JSONResponse:
    guard = BudgetGuard()
    try:
        profile = process_one(org_number, guard=guard, use_llm=True)
    except CompanyNotFound:
        raise HTTPException(status_code=404, detail=f"No company found for org number {org_number}")
    return JSONResponse(content=profile.to_dict())
