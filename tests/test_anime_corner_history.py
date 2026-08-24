from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

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
