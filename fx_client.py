from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date

import httpx


@dataclass
class RateFound:
    rate: float
    actual_date: date


@dataclass
class RateProblem:
    reason: str


def _upstream_base() -> str:
    return os.environ.get("FX_UPSTREAM_BASE", "https://api.frankfurter.dev").rstrip("/")


def _now() -> float:
    return time.time()


_LATEST_TTL_SECONDS = 300
_cache: dict[tuple[str, str, date | None], tuple[RateFound, float]] = {}


def _interpret(status_code: int, payload: dict | None, target: str) -> RateFound | RateProblem:
    if status_code == 200 and payload is not None:
        rates = payload.get("rates", {})
        # never on_date - upstream may have rolled back to an earlier trading day
        raw_date = payload.get("date")
        if target in rates and raw_date:
            return RateFound(rate=rates[target], actual_date=date.fromisoformat(raw_date))
        return RateProblem("bad_response")

    if status_code == 404:
        return RateProblem("not_found")

    if status_code == 422:
        return RateProblem("invalid_pair")

    if status_code >= 500:
        return RateProblem("upstream_unavailable")

    return RateProblem("bad_response")


async def fetch_rate(base: str, target: str, on_date: date | None) -> RateFound | RateProblem:
    key = (base, target, on_date)
    cached = _cache.get(key)
    if cached is not None:
        result, cached_at = cached
        if on_date is not None or _now() - cached_at < _LATEST_TTL_SECONDS:
            return result

    result = await _fetch_rate_uncached(base, target, on_date)
    if isinstance(result, RateFound):
        _cache[key] = (result, _now())
    return result


async def _fetch_rate_uncached(base: str, target: str, on_date: date | None) -> RateFound | RateProblem:
    path = on_date.isoformat() if on_date else "latest"
    url = f"{_upstream_base()}/v1/{path}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params={"base": base, "symbols": target})
    except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError):
        return RateProblem("upstream_unavailable")

    try:
        payload = response.json()
    except ValueError:
        return RateProblem("bad_response")

    return _interpret(response.status_code, payload, target)
