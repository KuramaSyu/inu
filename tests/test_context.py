from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from pytz import utc
import hikari

from inu.core.context.interactions import BaseInteractionContext
from inu.core.context.base import UniqueContextInstance
from inu.core.context import response_state
from inu.core.context.response_state import (
    BaseResponseState,
    CreatedResponseState,
    DeferredCreateResponseState,
    InitialResponseState,
    RestResponseState,
)
from inu.core.context.response_proxy import InitialResponseProxy


_REAL_TRIGGER = BaseResponseState.trigger_transition_when_invalid


class DummyApp:
    pass


class DummyMessage:
    def __init__(self, message_id: int) -> None:
        self.id = message_id
        self.created_at = datetime.now(utc)

    async def edit(self, *args, **kwargs):
        return self

    async def delete(self):
        return None


class DummyInteraction:
    def __init__(self, interaction_id: int = 123, created_at: datetime | None = None) -> None:
        self.created_at = created_at or datetime.now(utc)
        self.id = interaction_id
        self._initial_message = DummyMessage(1)
        self.create_initial_calls: list[tuple] = []
        self.edit_initial_calls: list[tuple] = []
        self.execute_calls: list[tuple] = []
        self.edit_message_calls: list[tuple] = []
        self.delete_message_calls: list[tuple] = []
        self.delete_initial_calls: list[tuple] = []

    async def create_initial_response(self, response_type, content=None, **kwargs):
        self.create_initial_calls.append((response_type, content, kwargs))
        return None

    async def edit_initial_response(self, content=None, **kwargs):
        self.edit_initial_calls.append((content, kwargs))
        return self._initial_message

    async def execute(self, content=None, **kwargs):
        self.execute_calls.append((content, kwargs))
        return DummyMessage(2)

    async def edit_message(self, message, content=None, **kwargs):
        self.edit_message_calls.append((message, content, kwargs))
        return DummyMessage(3)

    async def delete_message(self, message):
        self.delete_message_calls.append((message,))
        return None

    async def delete_initial_response(self):
        self.delete_initial_calls.append(())
        return None

    async def fetch_initial_response(self):
        return self._initial_message

    async def fetch_message(self, message):
        return self._initial_message


class DummyContext(BaseInteractionContext):
    def __init__(self, app: DummyApp, interaction: DummyInteraction) -> None:
        super().__init__(app, interaction)

    @property
    def interaction(self) -> DummyInteraction:
        return self._interaction

    @property
    def id(self) -> int:
        return self._interaction.id

    @property
    def custom_id(self) -> None:
        return None

    @property
    def original_message(self):
        return None

    async def message(self):
        return await self.interaction.fetch_initial_response()


@pytest.fixture(autouse=True)
def _patch_response_state(monkeypatch):
    async def _no_transition(self):
        return None

    monkeypatch.setattr(BaseResponseState, "trigger_transition_when_invalid", _no_transition)
    monkeypatch.setattr(BaseResponseState, "interaction", property(lambda self: self._interaction))


def _install_fake_clock(monkeypatch, start: datetime):
    """Install a controllable clock and sleep that advances time without waiting."""
    sleep_calls: list[float] = []

    class FakeDateTime:
        _now = start

        @classmethod
        def now(cls, tz=None):
            return cls._now

        @classmethod
        def advance(cls, delta: timedelta) -> None:
            cls._now = cls._now + delta

    async def fake_sleep(seconds: float):
        sleep_calls.append(seconds)
        FakeDateTime.advance(timedelta(seconds=seconds))

    monkeypatch.setattr(response_state, "datetime", FakeDateTime)
    monkeypatch.setattr(response_state.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(response_state.asyncio, "create_task", lambda _coro: None)

    return FakeDateTime, sleep_calls


@pytest.mark.asyncio
async def test_respond_initial_creates_response_and_transitions():
    """Initial respond should create the first response and advance to CreatedResponseState."""
    ctx = DummyContext(DummyApp(), DummyInteraction())

    proxy = await ctx.respond(content="hello")

    assert isinstance(proxy, InitialResponseProxy)
    assert isinstance(ctx.response_state, CreatedResponseState)
    assert len(ctx.response_state.responses) == 1

    response_type, content, kwargs = ctx.interaction.create_initial_calls[0]
    assert response_type == hikari.ResponseType.MESSAGE_CREATE
    assert content == "hello"
    assert kwargs["flags"] == hikari.MessageFlag.NONE


@pytest.mark.asyncio
async def test_respond_initial_update_uses_message_update():
    """Update in InitialResponseState should issue a MESSAGE_UPDATE response."""
    ctx = DummyContext(DummyApp(), DummyInteraction())

    proxy = await ctx.respond(content="update", update=True)

    assert isinstance(proxy, InitialResponseProxy)
    assert isinstance(ctx.response_state, CreatedResponseState)

    response_type, content, _kwargs = ctx.interaction.create_initial_calls[0]
    assert response_type == hikari.ResponseType.MESSAGE_UPDATE
    assert content == "update"


@pytest.mark.asyncio
async def test_defer_then_respond_edits_initial_response():
    """Deferred state should edit the initial response when respond is called."""
    ctx = DummyContext(DummyApp(), DummyInteraction())

    await ctx.defer()
    assert isinstance(ctx.response_state, DeferredCreateResponseState)

    proxy = await ctx.respond(content="after")

    assert isinstance(proxy, InitialResponseProxy)
    assert isinstance(ctx.response_state, CreatedResponseState)
    assert ctx.interaction.edit_initial_calls


@pytest.mark.asyncio
async def test_created_state_update_edits_last_response():
    """In CreatedResponseState, update should edit the last response, not create a followup."""
    ctx = DummyContext(DummyApp(), DummyInteraction())

    await ctx.respond(content="first")
    await ctx.respond(content="edit", update=True)

    assert ctx.interaction.edit_message_calls
    assert not ctx.interaction.execute_calls


@pytest.mark.asyncio
async def test_unique_context_instance_non_hashable_returns_self():
    """Non-hashable contexts should bypass caching and return themselves."""
    ctx = DummyContext(DummyApp(), DummyInteraction(interaction_id=None))

    result = UniqueContextInstance.get(ctx)

    assert result is ctx


@pytest.mark.asyncio
async def test_unique_context_instance_hashable_returns_cached_instance():
    """Hashable contexts should be cached and return the same instance."""
    ctx = DummyContext(DummyApp(), DummyInteraction(interaction_id=42))

    result = UniqueContextInstance.get(ctx)
    result_again = UniqueContextInstance.get(ctx)

    assert result is result_again


@pytest.mark.asyncio
async def test_is_responded_matches_initial_state():
    """is_responded should be False before any initial response is created."""
    ctx = DummyContext(DummyApp(), DummyInteraction())

    assert isinstance(ctx.response_state, InitialResponseState)
    assert ctx.is_responded() is False


@pytest.mark.asyncio
async def test_transition_after_short_wait_2s(monkeypatch):
    """InitialResponseState should transition after its 3-minute window elapses."""
    start = datetime(2026, 5, 5, 12, 0, 0, tzinfo=utc)
    fake_dt, sleep_calls = _install_fake_clock(monkeypatch, start)
    monkeypatch.setattr(BaseResponseState, "trigger_transition_when_invalid", _REAL_TRIGGER)

    # Pretend the interaction was created just under 3 minutes ago.
    created_at = fake_dt._now - (timedelta(minutes=3) - timedelta(seconds=2))
    ctx = DummyContext(DummyApp(), DummyInteraction(created_at=created_at))

    await ctx.response_state.trigger_transition_when_invalid()

    # Expect a single sleep for (remaining + 1s) before the transition fires.
    assert sleep_calls == [pytest.approx(3.0)]
    assert isinstance(ctx.response_state, RestResponseState)


@pytest.mark.asyncio
async def test_transition_after_short_wait_3s(monkeypatch):
    """InitialResponseState transition should sleep ~4 seconds with the +1s cushion."""
    start = datetime(2026, 5, 5, 12, 0, 0, tzinfo=utc)
    fake_dt, sleep_calls = _install_fake_clock(monkeypatch, start)
    monkeypatch.setattr(BaseResponseState, "trigger_transition_when_invalid", _REAL_TRIGGER)

    # Slightly longer remaining time still results in a single sleep call.
    created_at = fake_dt._now - (timedelta(minutes=3) - timedelta(seconds=3))
    ctx = DummyContext(DummyApp(), DummyInteraction(created_at=created_at))

    await ctx.response_state.trigger_transition_when_invalid()

    # Expect a single sleep for (remaining + 1s) before the transition fires.
    assert sleep_calls == [pytest.approx(4.0)]
    assert isinstance(ctx.response_state, RestResponseState)


@pytest.mark.asyncio
async def test_transition_after_15_minutes(monkeypatch):
    """CreatedResponseState should transition immediately once invalid."""
    start = datetime(2026, 5, 5, 12, 0, 0, tzinfo=utc)
    fake_dt, sleep_calls = _install_fake_clock(monkeypatch, start)
    monkeypatch.setattr(BaseResponseState, "trigger_transition_when_invalid", _REAL_TRIGGER)

    # CreatedResponseState invalidates after 15 minutes from creation.
    created_at = fake_dt._now - timedelta(minutes=15, seconds=1)
    ctx = DummyContext(DummyApp(), DummyInteraction(created_at=created_at))
    state = CreatedResponseState(ctx.interaction, ctx, [])
    ctx.set_response_state(state)

    await ctx.response_state.trigger_transition_when_invalid()

    # Already invalid, so no sleep should occur before transition.
    assert sleep_calls == []
    assert isinstance(ctx.response_state, RestResponseState)


@pytest.mark.asyncio
async def test_transition_after_longer_than_15_minutes(monkeypatch):
    """CreatedResponseState should transition when well past its validity window."""
    start = datetime(2026, 5, 5, 12, 0, 0, tzinfo=utc)
    fake_dt, sleep_calls = _install_fake_clock(monkeypatch, start)
    monkeypatch.setattr(BaseResponseState, "trigger_transition_when_invalid", _REAL_TRIGGER)

    # Well beyond 15 minutes means no sleep is needed.
    created_at = fake_dt._now - timedelta(minutes=20)
    ctx = DummyContext(DummyApp(), DummyInteraction(created_at=created_at))
    state = CreatedResponseState(ctx.interaction, ctx, [])
    ctx.set_response_state(state)

    await ctx.response_state.trigger_transition_when_invalid()

    # Already invalid well past the window, so no sleep should occur.
    assert sleep_calls == []
    assert isinstance(ctx.response_state, RestResponseState)
