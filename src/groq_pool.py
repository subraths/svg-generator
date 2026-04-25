import os
import re
import time
import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Any
from groq import Groq


def _parse_retry_after_seconds(msg: str, default_sec: int = 30) -> int:
    m = re.search(r"Please try again in\s+((?:(\d+)m)?([\d.]+)s)", msg or "")
    if not m:
        return default_sec
    mins = int(m.group(2)) if m.group(2) else 0
    secs = float(m.group(3)) if m.group(3) else 0.0
    return max(1, int(mins * 60 + secs + 0.999))


def _is_429_rate_limit(err: Exception) -> bool:
    s = str(err)
    return ("429" in s) and ("rate_limit_exceeded" in s or "Rate limit reached" in s)


@dataclass
class KeyState:
    api_key: str
    blocked_until: float = 0.0


class GroqClientPool:
    def __init__(
        self,
        api_keys: List[str],
        label: str = "GroqPool",
        state_path: str = ".cache/groq_pool_state.json",
    ):
        clean = [k.strip() for k in api_keys if k and k.strip()]
        if not clean:
            raise ValueError("No API keys provided.")
        self.keys: List[KeyState] = [KeyState(api_key=k) for k in clean]
        self.active_idx: int = 0
        self.label = label
        self.state_path = Path(state_path)
        self.key_fingerprint = self._fingerprint_keys(clean)
        self._load_state()

    @classmethod
    def from_env(
        cls, env_name: str = "GROQ_API_KEYS", fallback_single: str = "GROQ_API_KEY"
    ):
        multi = os.getenv(env_name, "").strip()
        if multi:
            return cls([x.strip() for x in multi.split(",") if x.strip()])
        one = os.getenv(fallback_single, "").strip()
        if not one:
            raise ValueError(f"Set {env_name} or {fallback_single}")
        return cls([one])

    def _fingerprint_keys(self, keys: List[str]) -> str:
        h = hashlib.sha256()
        for k in keys:
            h.update(hashlib.sha256(k.encode()).hexdigest().encode())
        return h.hexdigest()

    def _save_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "active_idx": self.active_idx,
            "blocked_until": [ks.blocked_until for ks in self.keys],
            "key_fingerprint": self.key_fingerprint,
            "saved_at": time.time(),
        }
        self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_state(self):
        if not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            if payload.get("key_fingerprint") != self.key_fingerprint:
                # key set changed; ignore stale state
                return

            idx = int(payload.get("active_idx", 0))
            self.active_idx = idx % len(self.keys)

            blocked = payload.get("blocked_until", [])
            for i, ts in enumerate(blocked):
                if i < len(self.keys):
                    self.keys[i].blocked_until = float(ts)
        except Exception:
            # corrupt state; ignore
            return

    def _client_for_active(self) -> Groq:
        return Groq(api_key=self.keys[self.active_idx].api_key)

    def _rotate_next(self):
        self.active_idx = (self.active_idx + 1) % len(self.keys)
        self._save_state()

    def _find_unblocked_index(self) -> Optional[int]:
        now = time.time()
        for step in range(len(self.keys)):
            idx = (self.active_idx + step) % len(self.keys)
            if self.keys[idx].blocked_until <= now:
                return idx
        return None

    def _earliest_unblock_delay(self) -> int:
        now = time.time()
        earliest = min(k.blocked_until for k in self.keys)
        return max(1, int(earliest - now + 0.999))

    def chat_completion_with_failover(
        self, *, model: str, messages: list, temperature: float = 0.0
    ) -> Any:
        while True:
            idx = self._find_unblocked_index()
            if idx is None:
                wait_sec = self._earliest_unblock_delay()
                print(f"[{self.label}] all keys blocked; waiting {wait_sec}s")
                time.sleep(wait_sec)
                continue

            self.active_idx = idx
            self._save_state()

            try:
                client = self._client_for_active()
                resp = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                )
                # success: persist active idx
                self._save_state()
                return resp

            except Exception as e:
                if not _is_429_rate_limit(e):
                    raise

                wait_sec = _parse_retry_after_seconds(str(e), default_sec=30)
                self.keys[self.active_idx].blocked_until = time.time() + wait_sec
                self._save_state()
                print(
                    f"[{self.label}] 429 on key#{self.active_idx + 1}; "
                    f"blocked {wait_sec}s; rotating"
                )
                self._rotate_next()
