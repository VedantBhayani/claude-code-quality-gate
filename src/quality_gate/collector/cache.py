"""Polite, cached fetching: one GET per URL ever (per cache dir), ~1 s between network
calls, a descriptive User-Agent. The cache records the date each URL was fetched, so an
offline re-run keeps the original collection date."""
from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Callable

USER_AGENT = (
    "frontal-hire-quality-gate/0.1 (independent research; reads public job-board APIs only; "
    "one list call per board, >=1s between requests)"
)
DELAY_S = 1.0

# transport(url, headers) -> (HTTP status, body bytes or None)
Transport = Callable[[str, dict], "tuple[int | str, bytes | None]"]


def urllib_transport(url: str, headers: dict) -> tuple[int | str, bytes | None]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, None


class PoliteFetcher:
    """fetch(url) -> (status, body). 200 and 404 answers are cached on disk in cache_dir."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        transport: Transport = urllib_transport,
        delay_s: float = DELAY_S,
        user_agent: str = USER_AGENT,
        today: Callable[[], date] = date.today,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self._transport = transport
        self._delay_s = delay_s
        self._headers = {"User-Agent": user_agent, "Accept": "application/json"}
        self._today = today
        self._sleep = sleep
        self._clock = clock
        self._last_call: float | None = None

    def _path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()[:32]}.json"

    def _read(self, url: str) -> dict | None:
        path = self._path(url)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def fetched_on(self, url: str) -> date | None:
        """The date `url` was fetched over the network, if it is in the cache."""
        entry = self._read(url)
        return date.fromisoformat(entry["fetched_on"]) if entry else None

    def __call__(self, url: str) -> tuple[int | str, bytes | None]:
        entry = self._read(url)
        if entry is None:
            status, body = self._network(url)
            if status not in (200, 404):
                return status, body  # transient: not cached
            entry = {
                "url": url,
                "fetched_on": self._today().isoformat(),
                "status": status,
                "body_b64": base64.b64encode(body).decode() if body is not None else None,
            }
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._path(url).write_text(json.dumps(entry), encoding="utf-8")
        body = base64.b64decode(entry["body_b64"]) if entry["body_b64"] is not None else None
        return entry["status"], body

    def _network(self, url: str):
        if self._last_call is not None:
            wait = self._delay_s - (self._clock() - self._last_call)
            if wait > 0:
                self._sleep(wait)
        try:
            return self._transport(url, dict(self._headers))
        finally:
            self._last_call = self._clock()
