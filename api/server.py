"""FastAPI live demo for Signalpost."""
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from src.agent import process_one
from src.budget_guard import BudgetGuard
from src.brreg_client import CompanyNotFound

app=FastAPI(title="Signalpost Agent",version="2.0",
            description="Verified Norwegian company information with provenance.")

@app.get("/health")
def health(): return {"status":"ok","service":"signalpost-agent"}

@app.get("/company/{org_number}")
def get_company(org_number:str):
    guard=BudgetGuard()
    try:
        profile=process_one(org_number,guard,use_llm=bool(os.getenv("GEMINI_API_KEY")))
    except CompanyNotFound:
        raise HTTPException(status_code=404,detail=f"No company found for {org_number}")
    except ValueError as exc:
        raise HTTPException(status_code=400,detail=str(exc))
    return JSONResponse(content=profile.to_dict())
