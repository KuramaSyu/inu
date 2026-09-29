from datetime import datetime

import pytest

from inu.utils.rest.anime_corner import (
    MAX_WEEK_NUMBER,
    SEASON_LABELS,
    AnimeCornerAPI,
    build_anime_corner_url,
)


def test_old_scheme_unchanged():
    assert (
        build_anime_corner_url("summer", 2026, 12, scheme="old")
        == "https://animecorner.me/summer-2026-anime-rankings-week-12/"
    )


def test_old_scheme_is_default():
    assert (
        build_anime_corner_url("summer", 2026, 12)
        == "https://animecorner.me/summer-2026-anime-rankings-week-12/"
    )


def test_new_scheme_zero_pads_week():
    assert (
        build_anime_corner_url("summer", 2026, 12, scheme="new")
        == "https://animecorner.me/polls/vote/w12-summer2026/results"
    )


def test_new_scheme_pads_single_digit_weeks():
    assert (
        build_anime_corner_url("fall", 2026, 4, scheme="new")
        == "https://animecorner.me/polls/vote/w04-fall2026/results"
    )


def test_new_scheme_does_not_pad_above_max_week():
    assert (
        build_anime_corner_url("winter", 2027, 14, scheme="new")
        == "https://animecorner.me/polls/vote/w14-winter2027/results"
    )


def test_auto_resolves_to_new_when_index_has_season():
    index = {("summer", 2026): [12]}
    assert (
        build_anime_corner_url("summer", 2026, 12, scheme="auto", polls_index=index)
        == "https://animecorner.me/polls/vote/w12-summer2026/results"
    )


def test_auto_resolves_to_old_when_index_missing_season():
    index = {("summer", 2026): [12]}
    assert (
        build_anime_corner_url("winter", 2024, 5, scheme="auto", polls_index=index)
        == "https://animecorner.me/winter-2024-anime-rankings-week-5/"
    )


def test_auto_resolves_to_old_when_index_empty():
    assert (
        build_anime_corner_url("winter", 2024, 5, scheme="auto", polls_index={})
        == "https://animecorner.me/winter-2024-anime-rankings-week-5/"
    )


def test_auto_falls_back_to_old_without_index():
    # Without an index, "auto" must default to the old (safe) URL.
    assert (
        build_anime_corner_url("winter", 2024, 5, scheme="auto")
        == "https://animecorner.me/winter-2024-anime-rankings-week-5/"
    )


@pytest.mark.parametrize("season", ["autumn", "FOO", ""])
def test_invalid_season_raises(season):
    with pytest.raises(ValueError):
        build_anime_corner_url(season, 2026, 1)


@pytest.mark.parametrize("week", [0, -1, MAX_WEEK_NUMBER + 1, 99])
def test_invalid_week_raises(week):
    with pytest.raises(ValueError):
        build_anime_corner_url("summer", 2026, week)


def test_unknown_scheme_raises():
    with pytest.raises(ValueError):
        build_anime_corner_url("summer", 2026, 1, scheme="nope")


def test_every_season_is_supported():
    # belt-and-braces: every season label must round-trip cleanly under the
    # new scheme so future seasons don't silently break.
    for season in SEASON_LABELS:
        url = build_anime_corner_url(season, 2026, 1, scheme="new")
        assert season in url
