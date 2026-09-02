import socket
from datetime import date

import pytest

import fx_client
from fx_client import RateFound, RateProblem, _interpret, fetch_rate


def test_success_reports_upstreams_actual_date():
    payload = {"amount": 1.0, "base": "EUR", "date": "2026-08-28", "rates": {"TRY": 56.1718}}
    result = _interpret(200, payload, "TRY")
    assert result == RateFound(rate=56.1718, actual_date=date(2026, 8, 28))


def test_currency_not_in_response_is_a_bad_response():
    payload = {"amount": 1.0, "base": "EUR", "date": "2026-08-28", "rates": {}}
    result = _interpret(200, payload, "TRY")
    assert result == RateProblem("bad_response")


def test_missing_date_field_is_a_bad_response():
    payload = {"amount": 1.0, "base": "EUR", "rates": {"TRY": 56.1718}}
    result = _interpret(200, payload, "TRY")
    assert result == RateProblem("bad_response")


def test_404_is_not_found():
    assert _interpret(404, {"message": "not found"}, "TRY") == RateProblem("not_found")


def test_422_is_invalid_pair():
    assert _interpret(422, {"message": "bad currency pair"}, "EUR") == RateProblem("invalid_pair")


def test_500_is_upstream_unavailable():
    assert _interpret(500, None, "TRY") == RateProblem("upstream_unavailable")


@pytest.mark.asyncio
async def test_fetch_rate_when_upstream_is_unreachable(monkeypatch):
    # bind and release a port so we know for sure nothing's listening on it
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    closed_port = sock.getsockname()[1]
    sock.close()

    monkeypatch.setenv("FX_UPSTREAM_BASE", f"http://127.0.0.1:{closed_port}")

    result = await fetch_rate("EUR", "TRY", None)
    assert result == RateProblem("upstream_unavailable")


@pytest.mark.asyncio
async def test_repeated_explicit_date_uses_cache(monkeypatch):
    calls = []

    async def fake_uncached(base, target, on_date):
        calls.append(on_date)
        return RateFound(rate=1.0, actual_date=date(2026, 8, 28))

    monkeypatch.setattr(fx_client, "_fetch_rate_uncached", fake_uncached)

    await fetch_rate("EUR", "TRY", date(2026, 8, 28))
    await fetch_rate("EUR", "TRY", date(2026, 8, 28))

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_different_explicit_dates_do_not_share_a_cache_entry(monkeypatch):
    calls = []

    async def fake_uncached(base, target, on_date):
        calls.append(on_date)
        return RateFound(rate=1.0, actual_date=on_date)

    monkeypatch.setattr(fx_client, "_fetch_rate_uncached", fake_uncached)

    await fetch_rate("EUR", "TRY", date(2026, 8, 28))
    await fetch_rate("EUR", "TRY", date(2026, 8, 29))

    assert calls == [date(2026, 8, 28), date(2026, 8, 29)]


@pytest.mark.asyncio
async def test_repeated_latest_within_ttl_uses_cache(monkeypatch):
    calls = []

    async def fake_uncached(base, target, on_date):
        calls.append(on_date)
        return RateFound(rate=1.0, actual_date=date(2026, 8, 28))

    monkeypatch.setattr(fx_client, "_fetch_rate_uncached", fake_uncached)
    monkeypatch.setattr(fx_client, "_now", lambda: 1000.0)

    await fetch_rate("EUR", "TRY", None)
    await fetch_rate("EUR", "TRY", None)

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_latest_refetches_after_ttl_expires(monkeypatch):
    calls = []

    async def fake_uncached(base, target, on_date):
        calls.append(on_date)
        return RateFound(rate=1.0, actual_date=date(2026, 8, 28))

    monkeypatch.setattr(fx_client, "_fetch_rate_uncached", fake_uncached)

    clock = iter([1000.0, 1301.0, 1301.0])
    monkeypatch.setattr(fx_client, "_now", lambda: next(clock))

    await fetch_rate("EUR", "TRY", None)
    await fetch_rate("EUR", "TRY", None)

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_failed_lookup_is_never_cached(monkeypatch):
    calls = []

    async def fake_uncached(base, target, on_date):
        calls.append(on_date)
        return RateProblem("upstream_unavailable")

    monkeypatch.setattr(fx_client, "_fetch_rate_uncached", fake_uncached)

    await fetch_rate("EUR", "TRY", date(2026, 8, 28))
    await fetch_rate("EUR", "TRY", date(2026, 8, 28))

    assert len(calls) == 2
