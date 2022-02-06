from core import Database, Table


class Anime:
    """A data class for Anime"""
    pass


class AnimeManager:
    """A class, which stores MyAnimeList data for caching purposes in a Database"""

    @classmethod
    async def fetch_anime_by_id(
        cls,
        mal_id: int
    ) -> Anime:
        pass