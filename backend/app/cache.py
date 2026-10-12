"""Small in-memory caches and rate limiting."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict, defaultdict, deque


class TTLCache:
    """Results keyed by image hash, so re-running the same photo is instant.

    Only results (transcriptions and boxes) are kept, never the photo itself,
    and only in memory for a limited time.
    """

    def __init__(self, maxsize: int = 64, ttl: float = 3600):
        self.maxsize, self.ttl = maxsize, ttl
        self._data: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            ts, value = item
            if time.monotonic() - ts > self.ttl:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key, value):
        with self._lock:
            self._data[key] = (time.monotonic(), value)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def clear(self):
        with self._lock:
            self._data.clear()


class RateLimiter:
    """Sliding-window limiter keyed by (bucket, client)."""

    def __init__(self):
        self._hits: dict = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, bucket: str, client: str, limit: int, window: float) -> bool:
        if limit <= 0:
            return True
        now = time.monotonic()
        key = (bucket, client)
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            if len(self._hits) > 50_000:
                # Forget idle clients.
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > window][:10_000]:
                    self._hits.pop(k, None)
            return True

    def reset(self):
        with self._lock:
            self._hits.clear()
