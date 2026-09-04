# Notes

One page is plenty. Four short sections:

## Decisions

Weekend or holiday dates are not an error. Frankfurter already rolls back to the last published trading day and tells us which day that is. The endpoint reports that as `rate_date` alongside the original `asked_date`, so there is no need for separate weekend handling.

The date range is checked locally before calling upstream. Future dates and dates before 1999-01-04 are rejected early. This also means that if a valid date gets a 404 from upstream, it can be treated as an unknown currency.

`from` and `to` being the same is rejected instead of returning a trivial 1.0. Otherwise that shortcut could also accept a currency code that does not actually exist.

If upstream is down, slow or returns something we cannot trust, the request fails instead of returning a made up number.

Caching is keyed by `(from, to, date)`, not by amount, because the amount never affects the rate we ask upstream for. Historical dates are cached permanently. Requests with no date get a 5 minute TTL because the latest rate can change while the service is still running.

## With another day

I would add a currency specific earliest available date instead of using one blanket start date, since some currencies were added to the ECB feed later than 1999.

I would replace the current output with structured logging so upstream failures and other problems are easier to monitor in a real deployment.

I would also move the cache out of process if the service ever needed to run with multiple workers or instances. Redis would be a straightforward option.

## AI tools

I used Claude Code throughout the case for implementation and as a second pair of eyes while I worked through the design and tests. I drove the decisions around validation, same currency behavior, error handling and caching, then reviewed and tested the resulting implementation.

I did not treat its first answer as final. I caught two gaps while working through the caching design and challenged a bug grouping during the Part B review that turned out to combine two separate problems. I used concrete cases to check the behavior before settling on the final implementation. I also did the final wording pass on the documentation and PR descriptions.

## One thing the AI got wrong

While working through the caching design, I noticed that keeping the undated "latest" rate forever would be wrong. A rate fetched on Monday could still be served on Tuesday even after a newer one was available. That meant the latest rate needed some form of expiry.

The next approach was to consider an entry fresh if it had been cached "today." I found another gap there. A rate cached at 9am before the ECB update would still count as fresh at 5pm, even if a new rate had been published that afternoon. I caught this by walking through a simple 9am and 5pm example.

I decided to use a 5 minute TTL for the "latest" rate instead. Historical rates still cache permanently because a published rate for a past date does not change. I checked the behavior on both sides of the TTL boundary before implementing and testing the final version.
