from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from pprint import pprint
from datetime import timedelta
import re
import asyncio
import traceback
from typing import *

import selenium_async
from expiring_dict import ExpiringDict
import aiohttp


from inu.core import getLogger, stopwatch
from inu.core.api import PartialAnimeMatch, AnimeMatch


# from utils.db import MyAnimeList

log = getLogger(__name__)

REGEX = r"(\d+)(th|st|nd|rd) (.+) ([\d\.]+)%"

SEASON_LABELS = ("winter", "spring", "summer", "fall")
MAX_WEEK_NUMBER = 14  # anime seasons never run longer than 14 weeks in practice

POLLS_INDEX_URL = "https://animecorner.me/polls/"
POLLS_INDEX_TTL = 60 * 60  # 1 hour; the index changes only when a new poll is published
POLLS_HREF_RE = re.compile(
    r"/polls/vote/w(?P<week>\d{1,2})-(?P<season>winter|spring|summer|fall)(?P<year>\d{4})/"
)


def build_anime_corner_url(
    season: str,
    year: int,
    week_number: int,
    *,
    scheme: str = "old",
    polls_index: Optional[Dict[Tuple[str, int], List[int]]] = None,
) -> str:
    """Build the canonical URL for an Anime Corner weekly ranking.

    Args:
        season: one of winter/spring/summer/fall.
        year: 4-digit calendar year (winter rolls into the next year).
        week_number: 1-based week index inside the season (1..14).
        scheme:
            ``"old"`` -> https://animecorner.me/{season}-{year}-anime-rankings-week-{N}/
            ``"new"`` -> https://animecorner.me/polls/vote/w{N}-{season}{year}/results (N zero-padded)
            ``"auto"`` -> resolve via ``polls_index``; ``"new"`` if
                      ``(season, year)`` is present, otherwise ``"old"``.
        polls_index: optional snapshot from
            :meth:`AnimeCornerAPI.fetch_polls_index`; only consulted when
            ``scheme="auto"``.

    Example: build_anime_corner_url("spring", 2023, 12)
             -> https://animecorner.me/spring-2023-anime-rankings-week-12/
    """
    season = season.lower()
    if season not in SEASON_LABELS:
        raise ValueError(f"Unknown season: {season!r}")
    if not (1 <= week_number <= MAX_WEEK_NUMBER):
        raise ValueError(f"week_number must be 1..{MAX_WEEK_NUMBER}, got {week_number!r}")
    if scheme == "auto":
        scheme = "new" if polls_index and (season, year) in polls_index else "old"
    if scheme == "new":
        return f"https://animecorner.me/polls/vote/w{week_number:02d}-{season}{year}/results"
    if scheme == "old":
        return f"https://animecorner.me/{season}-{year}-anime-rankings-week-{week_number}/"
    raise ValueError(f"Unknown scheme: {scheme!r}")




class AnimeCornerAPI:
    TTL = 60*60*24*7
    ttl_dict = ExpiringDict(ttl=TTL)
    # Polls-index snapshot shared across instances; one backfill run = one fetch.
    _polls_index_cache: ExpiringDict = ExpiringDict(ttl=POLLS_INDEX_TTL)

    def __init__(self) -> None:
        self.link = "https://animecorner.me/spring-2023-anime-rankings-week-12/"
        opts = Options()
        opts.add_argument('--headless')
        opts.log.level = "trace"

    def create_browser(self) -> Firefox:
        opts = Options()
        opts.add_argument('--headless')
        opts.log.level = "trace"
        return Firefox(opts)

    @stopwatch("Scraping AnimeCorner", cache_threshold=timedelta(milliseconds=200))
    async def fetch_ranking(self, link: str) -> List[PartialAnimeMatch]:
        """Fetch the Anime Corner ranking for ``link``.

        Non-empty results are cached for ``TTL`` seconds. **Empty results are
        intentionally NOT cached** — they usually mean the page returned a
        404 or got scraped at a moment when the widget wasn't on screen.
        Re-probing on the next call lets us transparently recover from
        transient Selenium/browser/network failures during the backfill.
        """
        self.link = link
        cached = self.ttl_dict.get(link)
        if cached is not None:
            return cached
        try:
            matches = await asyncio.to_thread(self._fetch_ranking)
        except Exception:
            # log + swallow so the backfill can continue probing other weeks
            log.warning(
                f"_fetch_ranking crashed for {link!r}; treating as no ranking.",
                prefix="api",
            )
            matches = []
        if matches:
            # only cache successful results; empty results must be retried
            self.ttl_dict.ttl(link, matches, self.TTL)
        return matches

    @staticmethod
    async def _fetch_ranking_details(matches: List[PartialAnimeMatch]) -> List[PartialAnimeMatch]:
        ...

    def _fetch_ranking(self) -> List[PartialAnimeMatch]:
        """Scrape the ranking table on the current page.

        Two URL schemes are supported:
            - Old (e.g. ``.../summer-2026-anime-rankings-week-12/``): parsed
              line by line from the article body using ``REGEX``.
            - New (e.g. ``.../polls/vote/w12-summer2026/results``): parsed
              from the structured ranking list. Only the first 10 entries
              are visible by default — the scraper clicks the "View Full
              Ranking" toggle and waits for the hidden rows to render
              before parsing.

        Returns an empty list if the page doesn't contain a ranking — e.g.
        404s, off-season pages, or any other layout the scraper doesn't know
        how to read. Earlier this raised ``IndexError`` on pages where
        ``penci-post-entry-inner`` was missing, which crashed the backfill;
        callers now rely on receiving ``[]`` for "nothing here".
        """
        browser = self.create_browser()
        try:
            browser.get(self.link)
            if _is_new_polls_url(self.link):
                return _scrape_new_polls(browser)
            return _scrape_old_article(browser)
        finally:
            # close() closes window; quit() closes browser
            try:
                browser.quit()
            except Exception:
                pass

    @classmethod
    async def fetch_polls_index(cls) -> Dict[Tuple[str, int], List[int]]:
        """Fetch https://animecorner.me/polls/ and return {(season, year): [week_indices]}.

        Parses anchor hrefs that match ``/polls/vote/w{N}-{season}{year}/...``
        where ``N`` is 1-14 (zero-padded), ``season`` is one of
        winter/spring/summer/fall, ``year`` is 4 digits. The result is cached
        on the class for ``POLLS_INDEX_TTL`` seconds so a backfill run only
        hits the index page once.

        Returns an empty dict on any failure (network, parse error) — callers
        must treat absence as "no info, fall back to old scheme".
        """
        cached = cls._polls_index_cache.get("index")
        if cached is not None:
            return cached
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(POLLS_INDEX_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    if resp.status != 200:
                        log.warning(
                            f"polls index returned HTTP {resp.status}; "
                            "falling back to old URL scheme",
                            prefix="api",
                        )
                        return {}
                    html = await resp.text()
        except Exception:
            log.warning(
                f"polls index fetch failed; falling back to old URL scheme\n{traceback.format_exc()}",
                prefix="api",
            )
            return {}

        index: Dict[Tuple[str, int], List[int]] = {}
        for m in POLLS_HREF_RE.finditer(html):
            week = int(m.group("week"))
            season = m.group("season")
            year = int(m.group("year"))
            if not (1 <= week <= MAX_WEEK_NUMBER):
                continue
            index.setdefault((season, year), []).append(week)
        # sort weeks ascending so callers don't need to re-sort
        for key in index:
            index[key] = sorted(set(index[key]))
        cls._polls_index_cache.ttl("index", index, POLLS_INDEX_TTL)
        return index


def _is_new_polls_url(url: str) -> bool:
    """Return True for the polls/vote/wNN-.../results scheme."""
    return "animecorner.me/polls/vote/" in url


def _scrape_old_article(browser: Firefox) -> List[PartialAnimeMatch]:
    """Old URL scheme: parse the article body line-by-line."""
    results = browser.find_elements(by='id', value='penci-post-entry-inner')
    if not results:
        return []
    matches: List[PartialAnimeMatch] = []
    container_text = results[0].text if results else ""
    for line in container_text.splitlines():
        match = re.search(REGEX, line)
        if match:
            matches.append(
                PartialAnimeMatch(
                    rank=int(match.group(1)),
                    rank_suffix=match.group(2),
                    name=match.group(3),
                    score=float(match.group(4)),
                )
            )
    return matches


def _scrape_new_polls(browser: Firefox) -> List[PartialAnimeMatch]:
    """New URL scheme: click "View Full Ranking", wait, then parse the list."""
    # The page initially renders only the top 10. Rows past rank 10 are
    # hidden via the [data-ranking-extra hidden] pattern. Click the
    # toggle and wait for the previously-hidden rows to become visible.
    try:
        toggle = browser.find_element(
            by='css selector', value='[data-results-toggle]',
        )
        if toggle.get_attribute('aria-expanded') == 'false':
            toggle.click()
            # Wait until at least one row with data-ranking-extra is no
            # longer hidden. Polling is fine here — Selenium doesn't give
            # us a clean signal for this transition.
            import time as _time
            deadline = _time.time() + 5.0
            while _time.time() < deadline:
                extras = browser.find_elements(
                    by='css selector',
                    value='a.results-ranking-row[data-ranking-extra]',
                )
                if extras and all(not e.get_attribute('hidden') for e in extras):
                    break
                _time.sleep(0.1)
    except Exception:
        # No toggle on the page means the ranking has <= 10 entries and
        # is already fully visible. Carry on.
        pass
    html = browser.page_source
    return _parse_results_html(html)


_PCT_RE = re.compile(r'([0-9]+(?:\.[0-9]+)?)\s*%')
# Matches an aria-label="Rank N" marker. This appears both on the
# <span class="results-ranking-row__rank"> wrapper (ranks 4+) and directly
# on <strong> tags inside podium cards (ranks 1-3).
_RANK_RE = re.compile(r'aria-label="Rank\s*(?P<rank>\d+)"')
# Matches the visible rank text inside a row, e.g. "#3" or "#4". Used to
# derive the rank suffix (st/nd/rd/th) when present.
_VISIBLE_RANK_RE = re.compile(r'<strong[^>]*>\s*(#[^<]+?)\s*</strong>')


def _parse_results_html(html: str) -> List[PartialAnimeMatch]:
    """Parse the new polls-results page into ``PartialAnimeMatch`` rows.

    Top 3 are in ``.results-podium-card``; ranks 4+ are in
    ``a.results-ranking-row`` (after the "View Full Ranking" toggle has
    been clicked). Each row exposes rank via ``aria-label="Rank N"`` and
    score via the first ``<strong>NN.N%</strong>`` inside its metric
    container.

    Pure function (no Selenium) so it can be exercised by fixture-based
    tests against a saved page snapshot.
    """
    matches: List[PartialAnimeMatch] = []
    seen_ranks: set = set()
    for m in _RANK_RE.finditer(html):
        rank = int(m.group('rank'))
        if rank in seen_ranks:
            continue
        # Search for the next <h3>...</h3> as the anime name. The window
        # extends well past the row's end so the percentage regex doesn't
        # pick up a number from a neighbouring comparison arrow.
        rest = html[m.end():m.end() + 4000]
        h3 = re.search(r'<h3[^>]*>(.*?)</h3>', rest, re.DOTALL)
        if not h3:
            continue
        name = _clean_text(h3.group(1))

        # Score: the first "<strong>NN.N%</strong>" after the rank marker.
        pct_match = re.search(r'<strong>\s*' + _PCT_RE.pattern + r'\s*</strong>', rest)
        if not pct_match:
            continue
        try:
            score = float(pct_match.group(1))
        except ValueError:
            continue

        # Derive rank suffix from the visible "#N(st|nd|rd|th)" text if
        # present (podium uses "#3"; ranking-row uses "#4"). The visible
        # text appears immediately around the aria-label marker.
        rank_suffix = ''
        near = html[m.start():m.start() + 400]
        visible = _VISIBLE_RANK_RE.search(near)
        if visible:
            tail = visible.group(1).lstrip('#').strip()
            m2 = re.match(r'^(\d+)(st|nd|rd|th)\b', tail)
            if m2:
                rank_suffix = m2.group(2)

        seen_ranks.add(rank)
        matches.append(PartialAnimeMatch(
            rank=rank,
            rank_suffix=rank_suffix,
            name=name,
            score=score,
        ))
    return matches


_TAG_RE = re.compile(r'<[^>]+>')


def _clean_text(s: str) -> str:
    """Strip tags, normalise whitespace, decode a couple of HTML entities."""
    s = _TAG_RE.sub('', s)
    s = (
        s.replace('&amp;', '&')
         .replace('&lt;', '<')
         .replace('&gt;', '>')
         .replace('&quot;', '"')
         .replace('&#39;', "'")
         .replace('&nbsp;', ' ')
    )
    return re.sub(r'\s+', ' ', s).strip()

    async def find_latest_week_with_ranking(
        self,
        season: str,
        year: int,
        start_week: int = 1,
        max_week_number: int = MAX_WEEK_NUMBER,
        polls_index: Optional[Dict[Tuple[str, int], List[int]]] = None,
    ) -> Optional[int]:
        """Probe URLs for `season`+`year` and return the highest
        ``week_number`` that actually returns a non-empty ranking.

        Args:
            season: one of winter/spring/summer/fall
            year: calendar year
            start_week: 1-based week index to start probing from. Pass the
                highest ``week_index`` the backfill has already recorded
                for this season (e.g. via
                :meth:`AnimeCornerHistoryManager.max_known_week_index`)
                to avoid re-probing every week from 1 on every run – the
                common case is a season that's been rolling for weeks and
                we only need to check whether a new week has been added.
                Defaults to 1 (probe every week).
            max_week_number: upper bound to probe (defaults to
                :data:`MAX_WEEK_NUMBER`)
            polls_index: optional snapshot from
                :meth:`fetch_polls_index`. When supplied and the index
                has entries for ``(season, year)`` the function only
                probes those weeks under the new URL scheme.
        Returns:
            The largest week number that returned at least 1 ranking row, or
            ``None`` if no valid week was found (e.g. off-season or the
            scraper is currently broken – a successful scrape is what tells
            us "the season is published", so when no URL produces rows we
            can't tell those two cases apart and the safest answer is
            ``None``).

        Note:
            Anime Corner migrated to a new URL scheme (polls/vote/wNN-.../results)
            in 2025. Older seasons still serve the old one. When the polls
            index knows about ``(season, year)`` we only probe the new URLs
            for that season. For seasons the index does not list (pre-migration
            and any season whose rankings haven't been published yet) we fall
            back to the old scheme and the
            ``MAX_CONSECUTIVE_FAILURES`` bailout that previously guarded the
            whole function.
        """
        if polls_index is None:
            try:
                polls_index = await self.fetch_polls_index()
            except Exception:
                polls_index = {}

        # New scheme: only probe weeks the polls index actually lists.
        # start_week is honoured (only probe at-or-after it).
        if polls_index and (season, year) in polls_index:
            available_weeks = [
                w for w in polls_index[(season, year)]
                if w >= max(1, start_week) and w <= MAX_WEEK_NUMBER
            ]
            if not available_weeks:
                return None
            last_valid: Optional[int] = None
            for w in available_weeks:
                url = build_anime_corner_url(season, year, w, scheme="new")
                ranking = await self.fetch_ranking(url)
                if ranking:
                    last_valid = w
                    continue
                if last_valid is not None:
                    break
            return last_valid

        # Old scheme: probe 1..max_week_number (clamped). Keep the bailout
        # because here the URL pattern is uniform and an empty run is the
        # only signal that scraping is broken.
        last_valid = None
        consecutive_failures = 0
        MAX_CONSECUTIVE_FAILURES = 4
        start_week = max(1, min(start_week, max_week_number))
        for w in range(start_week, max_week_number + 1):
            url = build_anime_corner_url(season, year, w, scheme="old")
            ranking = await self.fetch_ranking(url)
            if ranking:
                last_valid = w
                consecutive_failures = 0
                continue
            if last_valid is not None:
                break
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                log.warning(
                    f"AnimeCorner scraper failed {consecutive_failures} times "
                    f"in a row for `{season}-{year}` (urL: {url}) – scraping may be "
                    f"down",
                    prefix="api",
                )
                return None
        return last_valid

if __name__ == '__main__':
    anime_corner = AnimeCornerAPI()
    matches = asyncio.run(anime_corner.test())
    pprint(matches)