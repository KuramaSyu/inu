from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from pprint import pprint
from datetime import timedelta
import re
import asyncio
from typing import *
import selenium_async
from core import stopwatch
from expiring_dict import ExpiringDict
REGEX = r"(\d+)(th|st|nd|rd) (.+) ([\d\.]+)%"


class AnimeMatch(TypedDict):
    rank: int
    rank_suffix: str
    name: str
    score: float


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
    async def fetch_ranking(self, link: str) -> List[AnimeMatch]:
        self.link = link
        if not (matches := self.ttl_dict.get(link)):
            # matches = await selenium_async.run_sync(
            #     self._fetch_ranking,
            #     browser="chrome"
            # )
            # selenium_async stopped working
            # better solution?
            matches = await asyncio.to_thread(self._fetch_ranking)
            self.ttl_dict.ttl(link, matches, self.TTL)
        return matches

    
    def _fetch_ranking(self) -> List[AnimeMatch]:
        browser = self.create_browser()
        browser.get(self.link)
        results = browser.find_elements(by='id', value='penci-post-entry-inner')#

        matches = []
        for i, line in enumerate(results[0].text.splitlines()):
            match = re.search(REGEX, line)
            if match:
                matches.append(
                    AnimeMatch(
                    rank=int(match.group(1)), 
                    rank_suffix=match.group(2), 
                    name=match.group(3), 
                    score=float(match.group(4))
                    )
                )
        # close() closes window; quit() closes browser
        browser.quit()
        return matches

if __name__ == '__main__':
    anime_corner = AnimeCornerAPI()
    matches = asyncio.run(anime_corner.test())
    pprint(matches)