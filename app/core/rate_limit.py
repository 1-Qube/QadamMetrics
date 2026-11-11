"""In-memory request limits. One Render instance is enough for the judge demo; a second instance would need a shared store."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

_buckets: dict[str, deque[float]] = defaultdict(deque)


def _rule(path: str, method: str) -> tuple[int, int] | None:
    if method != "POST":
        return None
    if path.startswith("/api/ai/"):
        return 8, 60
    if path.startswith("/api/datasets/import") or path.startswith("/api/textbooks/ingest"):
        return 6, 60
    if path.startswith("/api/datasets/demo") or path.startswith("/api/reports/generate"):
        return 4, 60
    if path.startswith("/api/optimization") or path.startswith("/api/causal-analysis"):
        return 12, 60
    return None


def allow(key: str, limit: int, window_seconds: int) -> bool:
    now = time.monotonic()
    bucket = _buckets[key]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


async def rate_limit_middleware(request: Request, call_next):
    rule = _rule(request.url.path, request.method)
    if rule is None:
        return await call_next(request)
    limit, window = rule
    client = request.client.host if request.client else "unknown"
    if not allow(f"{client}:{request.url.path}", limit, window):
        response = JSONResponse(
            status_code=429,
            content={"error": {"code": "rate_limited", "message": "Too many requests. Wait a minute and try again."}},
        )
        origin = request.headers.get("origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response
    return await call_next(request)
