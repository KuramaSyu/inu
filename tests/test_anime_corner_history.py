import asyncio
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from hikari import Embed

from inu.utils.paginators.anime_corner_history import AnimeCornerHistoryPaginator, HistoryView
from inu.utils.paginators.base import Paginator
from inu.utils.db.anime_corner_history import AnimeCornerHistoryManager


def test_overview_chart_supports_rows_without_mal_ids():
    df = pd.DataFrame({
        "date": pd.to_datetime(["2026-03-02", "2026-03-09", "2026-03-16"]),
        "rank": [1, 2, 1],
        "name": ["Anime A", "Anime B", "Anime B"],
        "mal_id": [None, None, None],
    })
    view = HistoryView(
        df,
        {
            "season": "spring",
            "year": 2026,
            "season_start": datetime(2026, 3, 2),
            "title": "Anime of Spring 2026",
        },
    )

    result = view.build_overview_graph()

    assert result is not None
    image, plotted = result
    assert image.getbuffer().nbytes > 0
    assert set(plotted["name"]) == {"Anime A", "Anime B"}


@pytest.mark.asyncio
async def test_paginator_excludes_next_season_boundary(monkeypatch):
    history = pd.DataFrame({
        "date": pd.to_datetime(["2026-03-02", "2026-06-01"]),
        "rank": [1, 2],
        "name": ["Anime A", "Anime B"],
        "mal_id": [None, None],
    })

    async def fetch_for_chart(since):
        return history

    async def skip_base_start(self, ctx):
        return None

    monkeypatch.setattr(AnimeCornerHistoryManager, "fetch_for_chart", fetch_for_chart)
    monkeypatch.setattr(Paginator, "start", skip_base_start)
    paginator = AnimeCornerHistoryPaginator(
        datetime(2026, 3, 2),
        datetime(2026, 6, 1),
        object(),
    )
    monkeypatch.setattr(paginator, "_build_overview_graph", lambda: None)

    await paginator.start()

    assert list(paginator.df["date"]) == [pd.Timestamp("2026-03-02")]


def test_top_20_button_only_appears_on_overview():
    paginator = AnimeCornerHistoryPaginator(
        datetime(2026, 3, 2),
        datetime(2026, 6, 1),
        object(),
    )
    paginator._pages = [Embed(title="Overview"), Embed(title="Anime")]
    overview = paginator.build_default_components(0)
    anime_page = paginator.build_default_components(1)

    assert any(
        component.custom_id == "anime_corner_top_20"
        for component in overview[0].components
    )
    assert not any(
        component.custom_id == "anime_corner_top_20"
        for component in anime_page[0].components
    )


@pytest.mark.asyncio
async def test_top_20_button_opens_anime_paginator_with_mal_ids(monkeypatch):
    nested_pag = SimpleNamespace()
    nested_pag.started_with = None
    nested_pag.started_results = None

    async def start_nested(ctx, anime_name=None, results=None):
        nested_pag.started_with = ctx
        nested_pag.started_results = results

    nested_pag.start = start_nested
    monkeypatch.setattr(
        "inu.utils.paginators.anime_corner_history.AnimePaginator",
        lambda: nested_pag,
    )
    monkeypatch.setattr(
        "inu.utils.paginators.anime_corner_history.ComponentInteraction",
        object,
    )
    paginator = AnimeCornerHistoryPaginator(
        datetime(2026, 3, 2),
        datetime(2026, 6, 1),
        object(),
    )
    paginator._author_id = 1
    paginator._message = SimpleNamespace(id=10)
    paginator.df = pd.DataFrame({
        "date": pd.to_datetime(["2026-03-02", "2026-03-02", "2026-03-09"]),
        "rank": [1, 2, 1],
        "name": ["Anime A", "Anime B", "Anime C"],
        "mal_id": [101, 102, 103],
    })
    ctx = SimpleNamespace(_interaction=None, _responded=True)
    monkeypatch.setattr(
        paginator,
        "set_context",
        lambda interaction=None: setattr(paginator, "ctx", ctx),
    )
    monkeypatch.setattr(paginator, "interaction_pred", lambda interaction: True)
    interaction = SimpleNamespace(
        custom_id="anime_corner_top_20",
        user=SimpleNamespace(id=1),
        message=SimpleNamespace(id=10),
    )
    tasks = []

    def capture_task(coro):
        tasks.append(coro)
        return coro

    monkeypatch.setattr(asyncio, "create_task", capture_task)
    await paginator.on_component_interaction.callback(
        paginator,
        SimpleNamespace(interaction=interaction),
    )

    assert len(tasks) == 1
    await tasks[0]
    assert nested_pag.started_with is ctx
    assert nested_pag.started_results == [{"node": {"id": 103}}]
    assert nested_pag.started_with._interaction is interaction


def test_top_20_mal_ids_use_latest_week_and_first_20_ranks():
    paginator = AnimeCornerHistoryPaginator(
        datetime(2026, 3, 2),
        datetime(2026, 6, 1),
        object(),
    )
    latest_ranks = list(range(1, 21)) + [22, 30, 45, 60]
    paginator.df = pd.DataFrame({
        "date": pd.to_datetime(["2026-03-09"] * len(latest_ranks)),
        "rank": latest_ranks,
        "name": [f"Anime {rank}" for rank in latest_ranks],
        "score": [1.0] * len(latest_ranks),
        "mal_id": list(range(1, len(latest_ranks) + 1)),
    })

    mal_ids = paginator._top_20_mal_ids()

    assert mal_ids == list(range(1, 21))
    assert all(isinstance(mal_id, int) for mal_id in mal_ids)


def test_week_indexes_are_whole_numbers_across_dst():
    df = pd.DataFrame({
        "date": pd.to_datetime(
            [
                "2026-03-02 00:00+01:00",
                "2026-03-09 00:00+01:00",
                "2026-03-15 23:00+02:00",
            ],
            format="mixed",
            utc=True,
        ),
    })
    berlin = ZoneInfo("Europe/Berlin")
    view = HistoryView(
        df,
        {
            "season": "spring",
            "year": 2026,
            "season_start": datetime(2026, 3, 2, tzinfo=berlin),
        },
    )

    week_indexes, label = view._label_week_axis(df)

    assert list(week_indexes) == [1, 2, 3]
    assert label == "Week in Spring 2026"
