"""Hard limits for runtime, outbound requests, and declared API cost."""
import time
from . import config

class BudgetExceeded(Exception):
    pass

class BudgetGuard:
    def __init__(self, max_seconds=config.MAX_RUNTIME_SECONDS,
                 max_requests=config.MAX_OUTBOUND_REQUESTS,
                 max_cost_usd=config.MAX_COST_USD):
        self.max_seconds = max_seconds
        self.max_requests = max_requests
        self.max_cost_usd = max_cost_usd
        self.start_time = time.monotonic()
        self.request_count = 0
        self.cost_usd = 0.0

    def elapsed_seconds(self):
        return time.monotonic() - self.start_time

    def check(self, reserve_requests=0, reserve_cost=0.0):
        if self.elapsed_seconds() + 0 >= self.max_seconds:
            raise BudgetExceeded(f"Runtime limit reached ({self.max_seconds}s).")
        if self.request_count + reserve_requests > self.max_requests:
            raise BudgetExceeded(f"Request limit would be exceeded ({self.max_requests}).")
        if self.cost_usd + reserve_cost > self.max_cost_usd:
            raise BudgetExceeded(f"Cost limit would be exceeded (${self.max_cost_usd:.2f}).")

    def reserve_request(self, cost_usd=0.0):
        # Call immediately before EVERY outbound attempt. Retries count too.
        self.check(reserve_requests=1, reserve_cost=cost_usd)
        self.request_count += 1
        self.cost_usd += cost_usd

    def summary(self):
        return {"elapsed_seconds": round(self.elapsed_seconds(), 1),
                "requests_used": self.request_count,
                "estimated_cost_usd": round(self.cost_usd, 4)}
