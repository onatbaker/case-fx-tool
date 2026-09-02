import httpx
from fastapi.testclient import TestClient

import fx_client
from main import app


def _fake_upstream(request: httpx.Request) -> httpx.Response:
    assert request.url.host == "fake-upstream.test"
    assert request.url.params["base"] == "EUR"
    assert request.url.params["symbols"] == "TRY"
    return httpx.Response(
        200,
        json={"amount": 1.0, "base": "EUR", "date": "2026-08-28", "rates": {"TRY": 56.1718}},
    )


def test_full_stack_uses_fx_upstream_base(monkeypatch):
    monkeypatch.setenv("FX_UPSTREAM_BASE", "http://fake-upstream.test")
    real_async_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(_fake_upstream)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(fx_client.httpx, "AsyncClient", fake_async_client)

    client = TestClient(app)
    response = client.get("/tools/convert", params={"amount": "100", "from": "EUR", "to": "TRY", "date": "2026-08-29"})

    assert response.status_code == 200
    body = response.json()
    assert body["rate_date"] == "2026-08-28"
    assert body["asked_date"] == "2026-08-29"
    assert body["result"] == round(100 * 56.1718, 2)
