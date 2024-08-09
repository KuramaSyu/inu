from typing import *
from pprint import pformat
from utils import MyAnimeList, Anime
from core import PartialAnimeMatch, AnimeMatch
from expiring_dict import ExpiringDict
from fuzzywuzzy import fuzz


class AnimeCornerView:
    TTL = 60*60*24*7
    ttl_dict = ExpiringDict(ttl=TTL)
    

    @classmethod
    async def fetch_anime_matches(cls, anime_matches: List[PartialAnimeMatch]) -> List[Anime]:
        anime_matches_hash = hash("".join([anime['name'] for anime in anime_matches]))
        if matches := cls.ttl_dict.get(anime_matches_hash):
            return matches

        full_matches: List[AnimeMatch] = []
        for partial_match in anime_matches:
            result = await MyAnimeList.search_anime(partial_match['name'])
            # fuzzy sort the results
            sorted_result = cls._fuzzy_sort_results(result["data"], partial_match['name'])
            # fetch the first result
            anime = await MyAnimeList.fetch_anime_by_id(sorted_result[0]["node"]["id"])
            full_matches.append(anime)
        cls.ttl_dict.ttl(anime_matches_hash, full_matches, cls.TTL)
        return full_matches

    @staticmethod
    def _fuzzy_sort_results(results, compare_name: str) -> List[dict]:
        """fuzzy sort the anime result titles of  `self._results` by given name"""
        close_matches = []
        for anime in results.copy():
            # get all titles
            titles = [anime["node"]["title"]]
            if (alt_titles := anime["node"]["alternative_titles"]) and isinstance(alt_titles, dict):
                for value in alt_titles.values():
                    if isinstance(value, list):
                        titles.extend(value)
                    else:
                        titles.append(value)
                        
            max_ratio = max([fuzz.ratio(title.lower(), compare_name) for title in titles])
            anime["fuzz_ratio"] = max_ratio
            if anime["fuzz_ratio"] >= 80:
                results.remove(anime)
                close_matches.append(anime)
        close_matches.sort(key=lambda anime: anime["fuzz_ratio"], reverse=True)
        return [*close_matches, *results]