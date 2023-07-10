from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from pprint import pprint
import re
import asyncio
from typing import *
import selenium_async


REGEX = r"(\d+)(th|st|nd|rd) (.+) ([\d\.]+)%"


class AnimeMatch(TypedDict):
    rank: int
    rank_suffix: str
    name: str
    score: float


async def main():
    return await selenium_async.run_sync(
        fetch_anime_matches
    )


def fetch_anime_matches(_) -> List[AnimeMatch]:
    anime_corner_url ='https://animecorner.me/spring-2023-anime-rankings-week-12/'
    opts = Options()
    opts.add_argument('--headless')
    browser = selenium_async.Firefox(opts)
    browser.get(anime_corner_url)
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
    browser.close()
    return matches

if __name__ == '__main__':
    matches = asyncio.run(main())
    pprint(matches)