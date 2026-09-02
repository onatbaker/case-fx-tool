from datetime import date

from fastapi.testclient import TestClient

import main
from fx_client import RateFound, RateProblem
from main import _normalize_currency, _parse_amount, _parse_date, app

client = TestClient(app)


def test_parse_amount_accepts_two_decimal_places():
    assert _parse_amount("250.25") == 250.25


def test_parse_amount_rejects_zero():
    assert _parse_amount("0") is None


def test_parse_amount_rejects_negative():
    assert _parse_amount("-10") is None


def test_parse_amount_rejects_too_many_decimals():
    assert _parse_amount("250.1234567890") is None


def test_parse_amount_rejects_non_numeric():
    assert _parse_amount("abc") is None


def test_normalize_currency_uppercases():
    assert _normalize_currency("eur") == "EUR"


def test_normalize_currency_rejects_wrong_length():
    assert _normalize_currency("EURO") is None


def test_parse_date_defaults_to_today():
    on_date, asked_date = _parse_date(None)
    assert on_date is None
    assert asked_date == date.today().isoformat()


def test_parse_date_rejects_future():
    assert _parse_date("2099-01-01") is None


def test_parse_date_rejects_before_series_start():
    assert _parse_date("1998-01-01") is None


def test_parse_date_rejects_malformed():
    assert _parse_date("not-a-date") is None


def test_parse_date_accepts_valid_date():
    on_date, asked_date = _parse_date("2026-08-28")
    assert on_date == date(2026, 8, 28)
    assert asked_date == "2026-08-28"


def test_convert_success(monkeypatch):
    async def fake_fetch_rate(base, target, on_date):
        return RateFound(rate=56.1718, actual_date=date(2026, 8, 28))

    monkeypatch.setattr(main, "fetch_rate", fake_fetch_rate)

    response = client.get("/tools/convert", params={"amount": "250", "from": "EUR", "to": "TRY", "date": "2026-08-29"})
    assert response.status_code == 200
    body = response.json()
    assert body["rate_date"] == "2026-08-28"
    assert body["asked_date"] == "2026-08-29"
    assert body["result"] == round(250 * 56.1718, 2)


def test_convert_invalid_amount():
    response = client.get("/tools/convert", params={"amount": "0", "from": "EUR", "to": "TRY"})
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_amount"


def test_convert_invalid_currency():
    response = client.get("/tools/convert", params={"amount": "10", "from": "EU", "to": "TRY"})
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_currency"


def test_convert_same_currency():
    response = client.get("/tools/convert", params={"amount": "10", "from": "EUR", "to": "EUR"})
    assert response.status_code == 422
    assert response.json()["error"] == "same_currency"


def test_convert_invalid_date():
    response = client.get("/tools/convert", params={"amount": "10", "from": "EUR", "to": "TRY", "date": "2099-01-01"})
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_date"


def test_convert_unknown_currency(monkeypatch):
    async def fake_fetch_rate(base, target, on_date):
        return RateProblem("not_found")

    monkeypatch.setattr(main, "fetch_rate", fake_fetch_rate)

    response = client.get("/tools/convert", params={"amount": "10", "from": "EUR", "to": "ZZZ"})
    assert response.status_code == 404
    assert response.json()["error"] == "unknown_currency"


def test_convert_upstream_unavailable(monkeypatch):
    async def fake_fetch_rate(base, target, on_date):
        return RateProblem("upstream_unavailable")

    monkeypatch.setattr(main, "fetch_rate", fake_fetch_rate)

    response = client.get("/tools/convert", params={"amount": "10", "from": "EUR", "to": "TRY"})
    assert response.status_code == 502
    assert response.json()["error"] == "upstream_unavailable"
