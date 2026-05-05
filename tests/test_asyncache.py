import asyncio

import pytest

from inu.utils.asyncache import cached


def test_cached_sync_hits_cache():
    cache = {}
    calls = {"count": 0}

    @cached(cache)
    def add(a, b):
        calls["count"] += 1
        return a + b

    assert add(1, 2) == 3
    assert add(1, 2) == 3
    assert calls["count"] == 1


def test_cached_sync_none_cache():
    calls = {"count": 0}

    @cached(None)
    def add(a, b):
        calls["count"] += 1
        return a + b

    assert add(2, 3) == 5
    assert add(2, 3) == 5
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_cached_async_hits_cache():
    cache = {}
    calls = {"count": 0}

    @cached(cache)
    async def add(a, b):
        calls["count"] += 1
        await asyncio.sleep(0)
        return a + b

    assert await add(3, 4) == 7
    assert await add(3, 4) == 7
    assert calls["count"] == 1
