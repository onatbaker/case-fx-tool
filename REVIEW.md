# Review of tool.py

One page. Findings **ranked** — most harmful to a customer first.

For each finding: what is wrong, what it does to a customer (not to a linter),
and how you would verify it.

## 1. Failures come back as a successful, zero-valued conversion

On any failure (it can be a bad currency code, upstream being down, a malformed
response, anything at all) the endpoint returns a normal `200` with
`rate: 0.0, result: 0.0` instead of an error. The `except Exception` around
the conversion is what routes every kind of failure into that same response.
To a customer this looks like a valid conversion response. An agent can't tell 
that the conversion failed and could present the zero result as real financial data,
which can be pretty dangerous.

Verified by replacing the upstream call with a generic, unrelated exception
(not a currency issue, not a timeout but just a random failure) and confirming the
endpoint still answered `200` with `rate: 0.0`. This isn't scoped to one kind
of failure. Anything that goes wrong takes this path.

## 2. The cache ignores the date it was asked about

The cache key is just `base-target`, and the rate it stores has no date
attached either. Once any rate gets cached for a pair, every later request
for that pair, regardless of what date is actually being asked about,
silently gets handed that same number, for as long as the process keeps
running.

Verified by caching a rate for one date, then requesting a different date for
the same pair with a distinct rate ready to be returned. The second request
never touched upstream at all and came back with the first request's wrong
rate, mislabeled as belonging to the second date.

## 3. A valid pair with no available rate still gets answered instead of rejected

If a user requests a date for which no rate is available (such as a future date or a date before Frankfurter's available history),
the code can't tell that apart from "no rate today, try the
latest one," so it quietly retries against `/latest` and returns whatever
comes back. A request that should be flat out refused instead incorrectly gets a genuine rate.

Verified by asking for a date over 70 years out, for which no rate could
possibly exist. The response came back `200` with a substituted rate and the
call log confirmed the fallback endpoint was genuinely hit rather than the
request being rejected.

## The one I would fix before shipping tonight

Finding 1. It has the broadest failure surface of the three as it fires on
*any* exception and not one specific misuse. It's the only one that turns
an arbitrary failure into a believable financial answer with no signal
anything went wrong at all.

## Things that look suspicious but are fine

Logging via `print()` instead of a proper logging setup. A linter would flag
it but it has no effect on any customer. For the scope of this case, it's a non-issue.

Being right about a non-issue is worth as much as finding a real defect.
