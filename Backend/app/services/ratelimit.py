"""Límite de peticiones en memoria (por proceso). Con varias réplicas, cambiar por Redis."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


def check(scope: str, key: str, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    with _lock:
        q = _hits[(scope, key)]
        while q and now - q[0] > window_seconds:
            q.popleft()
        if len(q) >= limit:
            retry = int(window_seconds - (now - q[0])) + 1
            raise HTTPException(status_code=429, detail=f"Demasiados intentos. Prueba en {retry} s.",
                                headers={"Retry-After": str(retry)})
        q.append(now)


def reset() -> None:
    with _lock:
        _hits.clear()
