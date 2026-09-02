import pytest

import fx_client


@pytest.fixture(autouse=True)
def _clear_fx_cache():
    fx_client._cache.clear()
    yield
