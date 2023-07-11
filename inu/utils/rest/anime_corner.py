from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from pprint import pprint
import re
import asyncio
from typing import *
import selenium_async
from core import stopwatch


REGEX = r"(\d+)(th|st|nd|rd) (.+) ([\d\.]+)%"


class AnimeMatch(TypedDict):
    rank: int
    rank_suffix: str
    name: str
    score: float


class AnimeCornerAPI:
    def __init__(self) -> None:
        self.link = "https://animecorner.me/spring-2023-anime-rankings-week-12/"

    @stopwatch("Scraping AnimeCorner")
    async def fetch_ranking(self, link: str) -> List[AnimeMatch]:
        self.link = link
        return await selenium_async.run_sync(
            self._fetch_ranking
        )
    
    def _fetch_ranking(self, browser) -> List[AnimeMatch]:
        opts = Options()
        opts.add_argument('--headless')
        #browser = selenium_async.Firefox(opts)
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
        print("done")
        return matches

if __name__ == '__main__':
    anime_corner = AnimeCornerAPI()
    matches = asyncio.run(anime_corner.test())
    pprint(matches)