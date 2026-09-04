# fx-tool

A small HTTP service that converts an amount between two currencies using
ECB reference rates (via [frankfurter.dev](https://frankfurter.dev)), meant
to be called by an AI agent as a tool.

## Running it

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

Listens on `$PORT` (default `8080`). Upstream base URL comes from
`$FX_UPSTREAM_BASE` (default `https://api.frankfurter.dev`).

## Running the tests

```
./test.sh
```

The whole suite runs with zero network access. It passes even with
`FX_UPSTREAM_BASE` pointed at a closed port.

## The endpoint

```
GET /tools/convert?amount=250&from=EUR&to=TRY&date=2026-08-28
```

`date` is optional; if omitted, the most recently published rate is used.

Success (`200`):
```json
{
  "amount": 250,
  "from": "EUR",
  "to": "TRY",
  "rate": 47.1234,
  "result": 11780.85,
  "rate_date": "2026-08-28",
  "asked_date": "2026-08-28",
  "source": "ECB via frankfurter.dev"
}
```

`rate_date` is the date the rate actually belongs to; `asked_date` is what
was requested. They can differ. See the weekend/holiday case below.

Failure (non-2xx):
```json
{ "error": "<code>", "message": "<sentence>" }
```

## Error codes

| Code | Status | When |
|---|---|---|
| `invalid_amount` | 400 | `amount` missing, non-numeric, zero, negative or more than 2 decimal places |
| `invalid_currency` | 400 | `from`/`to` isn't exactly 3 letters |
| `same_currency` | 422 | `from` and `to` are the same currency |
| `invalid_date` | 400 | `date` isn't a real date, is in the future or is before 1999-01-04 (the start of the supported ECB series) |
| `unknown_currency` | 404 | `from`/`to` is well-formed but isn't a real currency Frankfurter tracks |
| `upstream_unavailable` | 502 | Frankfurter is unreachable, times out or returns something that isn't a trustworthy response |

## Behavior for the cases that matter

- **Weekend or holiday** (no rate published for the asked date): still a `200`. Frankfurter itself rolls back to the last real trading day and tells us which day that is. We report that day as `rate_date`, honestly, alongside the original `asked_date`. No special-case code is needed for this. It's the same success path as any other date.
- **Future date or before 1999-01-04**: rejected locally with `invalid_date`, before ever calling upstream.
- **Currency doesn't exist**: since the date is already validated locally first, a 404 from upstream at that point can only mean the currency. That maps to `unknown_currency`.
- **`from` and `to` are the same**: rejected locally with `same_currency`.
- **Upstream is slow, errors or returns non-JSON**: `upstream_unavailable`. Never a guessed or invented number.
- **Bad `amount`** (missing, zero, negative, more than 2 decimal places): rejected with `invalid_amount` before any network call.

The endpoint never invents a rate and never presents a rate as belonging to a
date it doesn't belong to. Every success response's `rate_date` comes
directly from what Frankfurter says the rate is actually from.

## Caching

Repeated requests for the same `(from, to, date)` don't re-ask upstream.
Explicit historical dates are cached permanently, since a published ECB rate
for a past date never changes. Requests with no `date` (the "latest" rate)
are cached for 5 minutes, since that one can genuinely go stale while the
service keeps running. `amount` is never part of the cache key. The rate
lookup and the multiplication are separate, so different amounts for the
same pair and date share one cached rate.
