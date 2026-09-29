from types import SimpleNamespace

import pytest

from inu.utils.rest.anime_corner import AnimeCornerAPI


SAMPLE_HTML = """
<html><body>
<a href="https://animecorner.me/polls/vote/w12-summer2026/results">Top 10 of week 12</a>
<a href="https://animecorner.me/polls/vote/w11-summer2026/results">week 11</a>
<a href="https://animecorner.me/polls/vote/w04-fall2026/results">week 4</a>
<a href="https://animecorner.me/polls/vote/w01-winter2027/results">week 1</a>
<a href="https://animecorner.me/polls/vote/w02-winter2027/results">week 2</a>
<a href="/some-other-page/">noise</a>
<a href="https://animecorner.me/polls/vote/w99-fall2026/results">out of range</a>
<a href="https://animecorner.me/polls/vote/w05-fall2026/results/">duplicate-ish</a>
</body></html>
"""


class _FakeResponse:
    def __init__(self, status: int, text: str) -> None:
        self.status = status
        self._text = text

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def text(self) -> str:
        return self._text


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        return self._response

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc) -> None:
        return None


@pytest.fixture(autouse=True)
def _reset_index_cache():
    AnimeCornerAPI._polls_index_cache.clear()
    yield
    AnimeCornerAPI._polls_index_cache.clear()


@pytest.mark.asyncio
async def test_fetch_polls_index_parses_html(monkeypatch):
    response = _FakeResponse(200, SAMPLE_HTML)
    fake_session = _FakeSession(response)

    monkeypatch.setattr(
        "inu.utils.rest.anime_corner.aiohttp.ClientSession",
        lambda: fake_session,
    )

    index = await AnimeCornerAPI.fetch_polls_index()

    assert index[("summer", 2026)] == [11, 12]
    assert index[("fall", 2026)] == [4, 5]
    assert index[("winter", 2027)] == [1, 2]
    # Out-of-range week index must be dropped.
    assert 99 not in index[("fall", 2026)]
    # Cache populated so the next call does not refetch.
    assert AnimeCornerAPI._polls_index_cache.get("index") is index


@pytest.mark.asyncio
async def test_fetch_polls_index_caches_until_ttl(monkeypatch):
    response = _FakeResponse(200, SAMPLE_HTML)
    fake_session = _FakeResponse.__new__(_FakeSession)  # placeholder
    fake_session = _FakeSession(response)

    monkeypatch.setattr(
        "inu.utils.rest.anime_corner.aiohttp.ClientSession",
        lambda: fake_session,
    )

    await AnimeCornerAPI.fetch_polls_index()
    await AnimeCornerAPI.fetch_polls_index()

    assert fake_session.calls == 1


@pytest.mark.asyncio
async def test_fetch_polls_index_returns_empty_on_non_200(monkeypatch):
    response = _FakeResponse(404, "")
    fake_session = _FakeSession(response)

    monkeypatch.setattr(
        "inu.utils.rest.anime_corner.aiohttp.ClientSession",
        lambda: fake_session,
    )

    index = await AnimeCornerAPI.fetch_polls_index()
    assert index == {}


@pytest.mark.asyncio
async def test_fetch_polls_index_returns_empty_on_request_error(monkeypatch):
    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(
        "inu.utils.rest.anime_corner.aiohttp.ClientSession",
        boom,
    )

    index = await AnimeCornerAPI.fetch_polls_index()
    assert index == {}


@pytest.mark.asyncio
async def test_fetch_polls_index_returns_empty_on_unparseable_html(monkeypatch):
    response = _FakeResponse(200, "<html><body>nothing matches</body></html>")
    fake_session = _FakeSession(response)

    monkeypatch.setattr(
        "inu.utils.rest.anime_corner.aiohttp.ClientSession",
        lambda: fake_session,
    )

    index = await AnimeCornerAPI.fetch_polls_index()
    assert index == {}
