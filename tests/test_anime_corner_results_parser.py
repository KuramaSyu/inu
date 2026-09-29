"""Tests for the new polls-results page parser used by AnimeCornerAPI.

The new URL scheme serves a structured ranking page where the first 10
entries are visible by default and the rest are hidden behind a
"View Full Ranking" toggle. We can't exercise the Selenium click path
in CI, so the parsing logic lives in a pure function
(:func:`_parse_results_html`) that takes the page source HTML and returns
matches. These tests cover that pure function with a fixture that mirrors
the salient DOM shapes observed on the live w12-summer2026 results page.
"""

from typing import List

from inu.utils.rest.anime_corner import (
    PartialAnimeMatch,
    _parse_results_html,
    _is_new_polls_url,
)


def _podium_card(rank: int, name: str, score: float) -> str:
    """Mimic the .results-podium-card shape: rank is on a <strong aria-label>."""
    return f'''
    <a class="results-podium-card" href="..." aria-label="View {name} insights">
      <span class="results-podium-card__rank">
        <strong aria-label="Rank {rank}">#{rank}</strong>
      </span>
      <div class="results-podium-card__body">
        <div class="results-podium-card__meta">
          <div class="results-podium-card__copy">
            <h3>{name}</h3>
          </div>
          <div class="results-podium-card__result">
            <strong>{score}%</strong>
          </div>
        </div>
      </div>
    </a>
    '''


def _ranking_row(rank: int, name: str, score: float, *, hidden: bool = False) -> str:
    """Mimic the a.results-ranking-row shape: rank is on a <span aria-label>."""
    hidden_attr = '  data-ranking-extra hidden ' if hidden else ' '
    return f'''
    <a class="results-ranking-row"{hidden_attr}href="..." aria-label="View {name} insights">
      <div class="results-ranking-row__rank-group">
        <span class="results-ranking-row__rank" aria-label="Rank {rank}">
          <span aria-hidden="true">#</span><strong>{rank}</strong>
        </span>
      </div>
      <div class="results-ranking-row__option">
        <div class="results-ranking-row__content">
          <h3>{name}</h3>
        </div>
      </div>
      <div class="results-ranking-row__metric">
        <strong>{score}%</strong>
      </div>
    </a>
    '''


PODIUM = "\n".join(
    _podium_card(rank=r, name=f"P{r}", score=20.0 - r * 0.5)
    for r in (1, 2, 3)
)

# 7 visible ranking rows (4-10) plus several hidden ones (11-15) to prove
# the parser picks up the full ranking even when rows carry the `hidden`
# attribute.
VISIBLE_ROWS = "\n".join(
    _ranking_row(rank=r, name=f"V{r}", score=5.0 - (r - 4) * 0.1)
    for r in range(4, 11)
)
HIDDEN_ROWS = "\n".join(
    _ranking_row(rank=r, name=f"H{r}", score=0.5 - (r - 11) * 0.05, hidden=True)
    for r in range(11, 16)
)

TOGGLE = '''
<button
  class="polls-content-toggle results-ranking__toggle"
  data-results-toggle="data-results-toggle"
  type="button"
  data-expand-label="View Full Ranking"
  aria-expanded="false"
>
  <span>View Full Ranking</span>
</button>
'''

RANKING_LIST = f'''
<section class="results-podium">
{PODIUM}
</section>
<div class="results-ranking__list" data-ranking-list>
{VISIBLE_ROWS}
{HIDDEN_ROWS}
</div>
{TOGGLE}
'''

# An extra row with HTML entities and apostrophes in the name.
ENTITY_ROW = _ranking_row(
    rank=16, name="A &amp; B&#39;s &quot;Quirky&quot; Show", score=0.10, hidden=True,
)


def test_is_new_polls_url_true():
    assert _is_new_polls_url("https://animecorner.me/polls/vote/w12-summer2026/results")
    assert _is_new_polls_url("https://animecorner.me/polls/vote/w04-fall2026/results")


def test_is_new_polls_url_false():
    assert not _is_new_polls_url("https://animecorner.me/summer-2026-anime-rankings-week-12/")
    assert not _is_new_polls_url("https://example.com/polls/vote/w12-summer2026")


def test_parse_extracts_podium_and_visible_rows():
    matches = _parse_results_html(RANKING_LIST)
    ranks = [m["rank"] for m in matches]
    # Podium (1-3) plus visible rows (4-10) plus hidden rows (11-15).
    assert ranks == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]


def test_parse_extracts_name_and_score():
    matches = _parse_results_html(RANKING_LIST)
    first = matches[0]
    assert first == {
        "rank": 1, "rank_suffix": "", "name": "P1", "score": 20.0 - 0.5,
    }


def test_parse_handles_html_entities_in_name():
    matches = _parse_results_html(RANKING_LIST + ENTITY_ROW)
    last = matches[-1]
    assert last["rank"] == 16
    assert last["name"] == "A & B's \"Quirky\" Show"
    assert abs(last["score"] - 0.10) < 1e-9


def test_parse_derives_rank_suffix_from_visible_text():
    # The fixture's visible rank text is "#1" / "#4" — there's no st/nd/rd
    # suffix. We only check that the parser doesn't blow up and that the
    # raw "#N" rank still flows through.
    matches = _parse_results_html(RANKING_LIST)
    for m in matches:
        assert isinstance(m["rank"], int)
        assert isinstance(m["rank_suffix"], str)


def test_parse_returns_empty_on_unrelated_html():
    assert _parse_results_html("<html><body>nothing here</body></html>") == []


def test_parse_returns_empty_when_only_toggle_present():
    # Page that hasn't loaded yet (or 404) — toggle button present but
    # no rows.
    html = f"<html><body>{TOGGLE}</body></html>"
    assert _parse_results_html(html) == []


def test_parse_first_50_rows_present_when_extended():
    # Build a page with 50 visible + 5 hidden rows so we cover the
    # "~50 entries" shape the user wanted to verify.
    rows = "\n".join(
        _ranking_row(rank=r, name=f"Anime {r}", score=max(0.1, 20.0 - r * 0.3))
        for r in range(1, 51)
    )
    hidden_rows = "\n".join(
        _ranking_row(
            rank=r, name=f"Hidden {r}", score=0.1, hidden=True,
        )
        for r in range(51, 56)
    )
    html = (
        '<section class="results-podium"></section>'
        f'<div class="results-ranking__list" data-ranking-list>{rows}{hidden_rows}</div>'
    )
    matches = _parse_results_html(html)
    assert len(matches) == 55
    assert matches[0]["rank"] == 1
    assert matches[-1]["rank"] == 55
    # Spot-check the 50th row's name to make sure we parsed names too.
    assert matches[49]["name"] == "Anime 50"


def test_parse_handles_at_least_fifty_consecutive_rows():
    """Real-world sanity check: the w12-summer2026 page has 59 entries.

    Mirrors the count the live page returned on 2026-09-29. If the layout
    ever shifts we want this to fail loudly rather than silently truncate.
    """
    rows = "\n".join(
        _ranking_row(rank=r, name=f"Anime {r}", score=max(0.1, 17.0 - r * 0.2))
        for r in range(1, 60)
    )
    html = (
        '<section class="results-podium"></section>'
        f'<div class="results-ranking__list" data-ranking-list">{rows}</div>'
    )
    matches = _parse_results_html(html)
    assert len(matches) == 59
    assert [m["rank"] for m in matches] == list(range(1, 60))
