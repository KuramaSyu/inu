from datetime import datetime

import pytest

from inu.ext.tasks.anime_corner import _season_week_index


def test_winter_january_second_week():
    # winter base is Dec 1 of the previous year. 2026-01-05 is 35 days after
    # 2025-12-01, so it's week 6 in the season's index. This documents the
    # current behaviour so a future tweak of the base date is intentional.
    assert _season_week_index("winter", 2026, datetime(2026, 1, 5)) == 6


def test_fall_september_late():
    # Base 2026-09-01; Sep 28 is 27 days later -> 27 // 7 + 1 = 4.
    assert _season_week_index("fall", 2026, datetime(2026, 9, 28)) == 4


def test_summer_late_september_out_of_season():
    # Late-September Mondays tagged "summer" no longer belong to summer.
    assert _season_week_index("summer", 2026, datetime(2026, 9, 21)) is None


def test_fall_august_too_early():
    # 2026-08-30 is before fall starts (Sep 1).
    assert _season_week_index("fall", 2026, datetime(2026, 8, 30)) is None


def test_winter_december_uses_same_year_as_base():
    # December rolls into the next year's winter: base is Dec of the same year.
    assert _season_week_index("winter", 2026, datetime(2026, 12, 7)) == 1


def test_unknown_season_returns_none():
    assert _season_week_index("autumn", 2026, datetime(2026, 9, 1)) is None


def test_index_does_not_exceed_max_week():
    # 14 * 7 = 98 days past the season start. Anything >= 98 returns None
    # so we never probe a week index that doesn't exist.
    assert _season_week_index("spring", 2026, datetime(2026, 6, 7)) is None
