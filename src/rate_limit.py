import time
from dataclasses import dataclass, field


@dataclass
class SimpleRateLimiter:
    min_interval_sec: float = 2.0  # ~30 req/min
    daily_token_budget: int = 190_000  # keep headroom below provider hard limit
    used_tokens_estimate: int = 0
    last_call_ts: float = field(default=0.0)

    def wait_turn(self):
        now = time.time()
        wait = self.min_interval_sec - (now - self.last_call_ts)
        if wait > 0:
            time.sleep(wait)
        self.last_call_ts = time.time()

    def can_spend(self, estimated_tokens: int) -> bool:
        return (self.used_tokens_estimate + estimated_tokens) <= self.daily_token_budget

    def spend(self, estimated_tokens: int):
        self.used_tokens_estimate += estimated_tokens


def estimate_tokens(*texts: str) -> int:
    # rough heuristic: 1 token ~ 4 chars (English-ish)
    chars = sum(len(t or "") for t in texts)
    return max(1, chars // 4)
