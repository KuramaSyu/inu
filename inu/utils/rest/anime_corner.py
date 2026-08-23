from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from pprint import pprint
from datetime import timedelta
import re
import asyncio
from typing import *

import selenium_async
from expiring_dict import ExpiringDict


from inu.core import getLogger, stopwatch
from inu.core.api import PartialAnimeMatch, AnimeMatch


# from utils.db import MyAnimeList

log = getLogger(__name__)

REGEX = r"(\d+)(th|st|nd|rd) (.+) ([\d\.]+)%"

SEASON_LABELS = ("winter", "spring", "summer", "fall")
MAX_WEEK_NUMBER = 14  # anime seasons never run longer than 14 weeks in practice


def build_anime_corner_url(season: str, year: int, week_number: int) -> str:
    """Build the canonical URL for an Anime Corner weekly ranking.

    Example: build_anime_corner_url("spring", 2023, 12)
             -> https://animecorner.me/spring-2023-anime-rankings-week-12/
    """
    season = season.lower()
    if season not in SEASON_LABELS:
        raise ValueError(f"Unknown season: {season!r}")
    if not (1 <= week_number <= MAX_WEEK_NUMBER):
        raise ValueError(f"week_number must be 1..{MAX_WEEK_NUMBER}, got {week_number!r}")
    return f"https://animecorner.me/{season}-{year}-anime-rankings-week-{week_number}/"




class AnimeCornerAPI:
    TTL = 60*60*24*7
    ttl_dict = ExpiringDict(ttl=TTL)

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
        """Parse the ranking table on the current page.

        Returns an empty list if the page doesn't contain a ranking — e.g.
        404s, off-season pages, or any other layout the scraper doesn't know
        how to read. Earlier this raised ``IndexError`` on pages where
        ``penci-post-entry-inner`` was missing, which crashed the backfill;
        callers now rely on receiving ``[]`` for "nothing here".
        """
        browser = self.create_browser()
        try:
            browser.get(self.link)
            results = browser.find_elements(by='id', value='penci-post-entry-inner')

            matches: List[PartialAnimeMatch] = []
            # The ranking is wrapped in the first matching container; if the
            # page has no ranking widget (404 / off-season / different layout)
            # we just return an empty list instead of raising.
            if not results:
                return matches

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
        finally:
            # close() closes window; quit() closes browser
            try:
                browser.quit()
            except Exception:
                pass

    async def find_latest_week_with_ranking(
        self,
        season: str,
        year: int,
        max_week_number: int = MAX_WEEK_NUMBER,
    ) -> Optional[int]:
        """Probe URLs for `season`+`year` starting at week 1 and return the
        highest ``week_number`` that actually returns a non-empty ranking.

        Args:
            season: one of winter/spring/summer/fall
            year: calendar year
            max_week_number: upper bound to probe (defaults to
                :data:`MAX_WEEK_NUMBER`)
        Returns:
            The largest week number that returned at least 1 ranking row, or
            ``None`` if no valid week was found (e.g. off-season or the
            scraper is currently broken – a successful scrape is what tells
            us "the season is published", so when no URL produces rows we
            can't tell those two cases apart and the safest answer is
            ``None``).

        Note:
            To avoid hammering Anime Corner when the scraper is broken, the
            loop gives up after ``MAX_CONSECUTIVE_FAILURES`` empty responses
            in a row *without having seen any success first*. Once the first
            successful URL is found we keep probing until we see an empty
            one, then break – because that empty response means "the season
            ended here".
        """
        last_valid: Optional[int] = None
        consecutive_failures = 0
        MAX_CONSECUTIVE_FAILURES = 4  # bail out early if scraping is broken
        for w in range(1, max_week_number + 1):
            url = build_anime_corner_url(season, year, w)
            ranking = await self.fetch_ranking(url)
            if ranking:
                last_valid = w
                consecutive_failures = 0
                continue
            if last_valid is not None:
                # we already saw a ranking, hitting an empty one means the
                # season has ended.
                break
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                # nothing has worked in this window — looks like scraping is
                # down. Bail out instead of paying for `max_week_number`
                # probes worth of Selenium calls.
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