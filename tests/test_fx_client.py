import socket
from datetime import date

import pytest

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
