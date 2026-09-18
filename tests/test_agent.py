from src.budget_guard import BudgetGuard, BudgetExceeded
from src.agent import _local_summary
from src.models import CompanyProfile

def test_request_guard_counts_retries_as_requests():
    g=BudgetGuard(max_seconds=60,max_requests=2,max_cost_usd=10)
    g.reserve_request(); g.reserve_request()
    assert g.request_count==2
    try: g.reserve_request()
    except BudgetExceeded: pass
    else: assert False, "third request should be blocked"

def test_local_summary_never_invents_financial_values():
    p=CompanyProfile(org_number="123456789",name="Example AS",city="OSLO")
    s=_local_summary(p)
    assert "Example AS" in s
    assert "OSLO" in s
    assert "revenue" not in s.lower()
