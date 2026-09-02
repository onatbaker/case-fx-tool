from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from fx_client import RateFound, RateProblem, fetch_rate

app = FastAPI(title="fx-tool")

SERIES_START = date(1999, 1, 4)
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")


@dataclass
class ConvertRequest:
    amount: float
    base: str
    target: str
    on_date: date | None
    asked_date: str


@dataclass
class RequestError:
    code: str
    message: str
    status: int


def _parse_amount(raw: str) -> float | None:
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    if value <= 0:
        return None
    if -value.as_tuple().exponent > 2:
        return None
    return float(value)


def _normalize_currency(raw: str) -> str | None:
    if not _CURRENCY_RE.match(raw):
        return None
    return raw.upper()


def _parse_date(raw: str | None) -> tuple[date | None, str] | None:
    if raw is None:
        today = date.today()
        return None, today.isoformat()
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    if parsed > date.today() or parsed < SERIES_START:
        return None
    return parsed, raw


def _validate(amount_raw: str, from_raw: str, to_raw: str, date_raw: str | None) -> ConvertRequest | RequestError:
    amount = _parse_amount(amount_raw)
    if amount is None:
        return RequestError("invalid_amount", "amount must be a positive number with at most 2 decimal places.", 400)

    base = _normalize_currency(from_raw)
    if base is None:
        return RequestError("invalid_currency", f"'{from_raw}' is not a valid 3-letter currency code.", 400)

    target = _normalize_currency(to_raw)
    if target is None:
        return RequestError("invalid_currency", f"'{to_raw}' is not a valid 3-letter currency code.", 400)

    if base == target:
        return RequestError("same_currency", "from and to must be different currencies.", 422)

    parsed_date = _parse_date(date_raw)
    if parsed_date is None:
        return RequestError("invalid_date", "date must be a real date, not in the future, and not before 1999-01-04.", 400)
    on_date, asked_date = parsed_date

    return ConvertRequest(amount=amount, base=base, target=target, on_date=on_date, asked_date=asked_date)


def _map_problem(problem: RateProblem) -> RequestError:
    if problem.reason == "not_found":
        return RequestError("unknown_currency", "no rate is published for that currency.", 404)
    if problem.reason == "invalid_pair":
        return RequestError("same_currency", "from and to must be different currencies.", 422)
    return RequestError("upstream_unavailable", "the rate provider is not returning a trustworthy answer right now.", 502)


@app.get("/tools/convert")
async def convert(
    amount: str = Query(...),
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
    date_: str | None = Query(default=None, alias="date"),
):
    parsed = _validate(amount, from_, to, date_)
    if isinstance(parsed, RequestError):
        return JSONResponse(status_code=parsed.status, content={"error": parsed.code, "message": parsed.message})

    result = await fetch_rate(parsed.base, parsed.target, parsed.on_date)
    if isinstance(result, RateProblem):
        error = _map_problem(result)
        return JSONResponse(status_code=error.status, content={"error": error.code, "message": error.message})

    assert isinstance(result, RateFound)
    return {
        "amount": parsed.amount,
        "from": parsed.base,
        "to": parsed.target,
        "rate": round(result.rate, 4),
        "result": round(parsed.amount * result.rate, 2),
        "rate_date": result.actual_date.isoformat(),
        "asked_date": parsed.asked_date,
        "source": "ECB via frankfurter.dev",
    }
