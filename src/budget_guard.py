"""Tracks elapsed time, outbound requests, and estimated cost so the agent
always stays within the challenge's daily limits (45 min / 2,000 requests /
$10), and stops *gracefully* instead of crashing mid-run.
"""
import time
from . import config


class BudgetExceeded(Exception):
    """Raised when a hard limit is reached; callers should catch this and
    save partial results rather than treat it as a crash."""


class BudgetGuard:
    def __init__(
        self,
        max_seconds: int = config.MAX_RUNTIME_SECONDS,
        max_requests: int = config.MAX_OUTBOUND_REQUESTS,
        max_cost_usd: float = config.MAX_COST_USD,
    ):
        self.max_seconds = max_seconds
        self.max_requests = max_requests
        self.max_cost_usd = max_cost_usd
        self.start_time = time.monotonic()
        self.request_count = 0
        self.cost_usd = 0.0

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.start_time

    def check(self) -> None:
        """Raise BudgetExceeded if any limit has been crossed."""
        if self.elapsed_seconds() >= self.max_seconds:
            raise BudgetExceeded(
                f"Runtime limit reached ({self.max_seconds}s)."
            )
        if self.request_count >= self.max_requests:
            raise BudgetExceeded(
                f"Request limit reached ({self.max_requests})."
            )
        if self.cost_usd >= self.max_cost_usd:
            raise BudgetExceeded(
                f"Cost limit reached (${self.max_cost_usd:.2f})."
            )

    def record_request(self, cost_usd: float = 0.0) -> None:
        self.request_count += 1
        self.cost_usd += cost_usd
        self.check()

    def summary(self) -> dict:
        return {
            "elapsed_seconds": round(self.elapsed_seconds(), 1),
            "requests_used": self.request_count,
            "estimated_cost_usd": round(self.cost_usd, 4),
        }
