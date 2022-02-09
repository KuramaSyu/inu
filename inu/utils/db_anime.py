import imp
import json
from pprint import pformat
from shutil import which
from typing import *
from datetime import datetime, timedelta
import time

from jikanpy import AioJikan

from core import Database, Table, getLogger

log = getLogger(__name__)


class Anime:
    """A data class for Anime"""
    def __init__(
        self,
        mal_id: int,
        title: str,
        title_english: str,
        title_japanese: str,
        title_synonyms: List[str],
        synopsis: str,
        background: str,
        related: Dict[str, str],
        themes: List[Dict[str, str]],
        explicit_genres: List[Dict[str, str]],
        genres: List[Dict[str, str]],
        type_: str,
        episodes: Optional[int],
        ending_themes: List[str],
        opening_themes: List[str],
        duration: str,
        rating: str,
        rank: Optional[int],
        score: Optional[float],
        popularity: Optional[int],
        favorites: int,
        source: str,
        status: str,
        airing: bool,
        airing_start: Optional[datetime],
        airing_stop: Optional[datetime],
        image_url: str,
        mal_url: str,
        trailer_url: str,
        licensors: List[Dict[str, str]],
        producers: List[Dict[str, str]],
        studios: List[Dict[str, str]],
        cached_for: Optional[int] = None,
        cached_until: Optional[datetime] = False,

    ):
        if not cached_for and cached_until == False:
            raise RuntimeError(
                f"to construct an Anime, cached_for or cached until is needed"
            )
        self.mal_id: int = mal_id
        self.origin_title: str = title
        self.title_english: str = title_english
        self.title_japanese: str = title_japanese
        self.title_synonyms: List[str] = title_synonyms
        self.synopsis: str = synopsis
        self.background: str = background
        self.related: Dict[str, str] = related
        self.themes: List[Dict[str, str]] = themes
        self.explicit_genres: List[Dict[str, str]] = explicit_genres
        self.genres: List[Dict[str, str]] = genres
        self.type_: str = type_
        self.episodes: int = episodes
        self.ending_themes: List[str] = ending_themes
        self.opening_themes: List[str] = opening_themes
        self.duration: str = duration
        self.rating: str = rating
        self.rank: Optional[int] = rank
        self.score: Optional[float] = score
        self.popularity: Optional[int] = popularity
        self.favorites: int = favorites
        self.source: str = source
        self.status: str = status
        self.airing: bool = airing
        self.airing_start: Optional[datetime] = airing_start
        self.airing_stop: Optional[datetime] = airing_stop
        self.image_url: str = image_url
        self.mal_url: str = mal_url
        self.trailer_url: str = trailer_url
        self.licensors: List[Dict[str, str]] = licensors
        self.producers: List[Dict[str, str]] = producers
        self.studios: List[Dict[str, str]] = studios
        if cached_until:
            self._cached_for = cached_until.timestamp() - int(time.time())
        elif cached_until is None:
            self._cached_for = None
        else:
            self._cached_for = cached_for
    
    @property
    def title(self) -> str:
        """
        Returns:
        -------
            - (str) the english title or the original title. English is prefered
        """
        if self.origin_title == self.title_english:
            return self.origin_title
        elif self.title_english:
            return self.title_english
        else:
            return self.origin_title

    @property
    def cached_until(self) -> Optional[int]:
        """
        Note:
        -----
            - it'll cache until 9999/12/31 if the anime is finsished. 
              Otherwise obout 1 month (given from jikan meta data)
         """
        if not self.is_finished and self._cached_for:
            # if self._chached_for is None, than it don't need an update
            return datetime.now() + timedelta(seconds=self._cached_for+600)
        # update not needed. Maybe None/Null would be better here
        else:
            None
    
    def __str__(self) -> str:
        return f"[{self.mal_id}] {self.title}"

    @staticmethod
    def markup_link_list(list_: List[Dict[str, str]]):
        """
        Args:
        -----
            - list_ (List[Dict[str,str]]) the list which should be converted
                - NOTE: The dict needs the keys: `"url"` and `"name"`

        Returns:
        --------
            - (List[str, str]) the list with markup strings

        Note:
        -----
            - this function is meant for `self.`|`genres`|`explicit_genres`|`themes`|`studios`|`licensors`|`producers`
        """
        return [f"[{x['name']}]({x['url']})" for x in list_]

    @staticmethod
    def markup_link_str(list_: List[Dict[str, str]]):
        """
        Args:
        -----
            - list_ (List[Dict[str,str]]) the list which should be converted
                - NOTE: The dict needs the keys: `"url"` and `"name"`

        Returns:
        --------
            - (str) the markup string which ", " seperated list entries

        Note:
        -----
            - this function is meant for `self.`|`genres`|`explicit_genres`|`themes`|`studios`|`licensors`|`producers`
        """
        return ", ".join([f"[{x['name']}]({x['url']})" for x in list_])
    
    @property
    def all_genres(self) -> List[Dict[str, str]]:
        """
        Returns:
        --------
            - (List[Dict[str, str]]) a list with all genres and explicit genres
        """
        return [*self.genres, *self.explicit_genres]

    @property
    def is_finished(self) -> bool:
        """
        ### wether or not the anime is finished
        """
        return (
            (
                self.airing_stop 
                and self.airing_start 
                and self.episodes 
                and self.airing_stop < datetime.now()
            ) 
            or self.status == 'Finished Airing'
        )

    @property
    def airing_str(self) -> str:
        if self.airing_start:
            start = f"{self.airing_start.year or '?'}/{f'{self.airing_start.month:02}' or '?'}"
        else:
            start = "?"
        if self.airing_stop:
            stop = f" {self.airing_stop.year or '?'}/{f'{self.airing_stop.month:02}' or '?'}"
        else:
            stop = ""
        return f"{start} {'- ' + stop or ''}"
    @classmethod
    def from_json(cls, resp: Dict[str, str]) -> "Anime":
        """
        ### build an Anime with the jikan v3 json response
        Returns:
        --------
            - (Anime) The coresponding Anime to the json
        """
        airing_start = None
        airing_stop = None
        try:
            if (date := resp["aired"]["prop"]["from"]):
                airing_start = datetime(
                    year=date["year"],
                    month=date["month"],
                    day=date["day"]
                )
        except Exception:
            airing_start = None
        try:
            if (date := resp["aired"]["prop"]["to"]):
                airing_stop = datetime(
                    year=date["year"],
                    month=date["month"],
                    day=date["day"]
                )
        except Exception:
            airing_stop = None
        return cls(
            mal_id=resp["mal_id"],
            title=resp["title"],
            title_english=resp["title_english"],
            title_japanese=resp["title_japanese"],
            title_synonyms=resp["title_synonyms"],
            synopsis=resp["synopsis"],
            background=resp["background"],
            related=resp["related"],
            themes=resp["themes"],
            explicit_genres=resp["explicit_genres"],
            genres=resp["genres"],
            type_=resp["type"],
            episodes=resp["episodes"],
            ending_themes=resp["ending_themes"],
            opening_themes=resp["opening_themes"],
            duration=resp["duration"],
            rating=resp["rating"],
            rank=resp["rank"],
            score=resp["score"],
            popularity=resp["popularity"],
            favorites=resp["favorites"],
            source=resp["source"],
            status=resp["status"],
            airing=resp["airing"],
            airing_start=airing_start,
            airing_stop=airing_stop,
            image_url=resp["image_url"],
            mal_url=resp["url"],
            trailer_url=resp["trailer_url"],
            licensors=resp["licensors"],
            producers=resp["producers"],
            studios=resp["studios"],
            cached_for=resp["request_cache_expiry"],
        )

    @classmethod
    def from_db_record(cls, resp: Dict[str, str]) -> "Anime":
        """
        ### build an `Anime` with a db record
        Args:
        -----
            - resp: (`Dict[str, str]` | `asyncpg.Record`) the db record

        Returns:
        --------
            - (Anime) the coresponding `Anime` the the db record

        Note:
        -----
            - for more information to the db record look: `{cwd}/inu/data/bot/sql/script.sql (table: myanimelist)` 
        """ 
        return cls(
            mal_id=resp["mal_id"],
            title=resp["title"],
            title_english=resp["title_english"],
            title_japanese=resp["title_japanese"],
            title_synonyms=resp["title_synonyms"],
            synopsis=resp["synopsis"],
            background=resp["background"],
            related=json.loads(resp["related"]),
            themes=[json.loads(x) for x in resp["themes"]],
            explicit_genres=[json.loads(x) for x in resp["explicit_genres"]],
            genres=[json.loads(x) for x in resp["genres"]],
            type_=resp["type"],
            episodes=resp["episodes"],
            ending_themes=resp["ending_themes"],
            opening_themes=resp["opening_themes"],
            duration=resp["duration"],
            rating=resp["rating"],
            rank=resp["rank"],
            score=resp["score"],
            popularity=resp["popularity"],
            favorites=resp["favorites"],
            source=resp["source"],
            status=resp["status"],
            airing=resp["airing"],
            airing_start=resp["airing_start"],
            airing_stop=resp["airing_stop"],
            image_url=resp["image_url"],
            mal_url=resp["mal_url"],
            trailer_url=resp["trailer_url"],
            licensors=[json.loads(x) for x in resp["licensors"]],
            producers=[json.loads(x) for x in resp["producers"]],
            studios=[json.loads(x) for x in resp["studios"]],
            cached_until=resp["cached_until"],
        )
    
    @property
    def needs_update(self) -> bool:
        """
        ### wether or not the anime needs an update
        """
        if self.is_finished:
            return False
        return datetime.now() > self.cached_until

class MyAnimeList:
    """A class, which stores MyAnimeList data for caching purposes in a Database, or fetches it from jikan"""

    @classmethod
    async def fetch_anime_by_id(
        cls,
        mal_id: int
    ) -> Anime:
        """
        Returns:
        --------
            - (`Anime`) the coresponding `Anime` to the mal_id
        
        Note:
        -----
            - The `Anime` will be stored in a database for caching puprposes
            - The internal db/cache will be checked first, before making a request to jikan
        """
        anime = await cls._fetch_anime_by_id_db(mal_id)
        if anime:
            if anime.needs_update:
                log.debug(f"update anime: {anime}")
                anime = await cls._fetch_anime_by_id_rest(mal_id)
                await cls._cache_anime(anime)
        else:
            log.debug(f"fetch new anime form REST: {mal_id}")
            anime = await cls._fetch_anime_by_id_rest(mal_id)
            await cls._cache_anime(anime)
        return anime

    @classmethod
    async def _fetch_anime_by_id_rest(
        cls,
        mal_id: int
    ) -> Anime:
        """
        Returns:
        --------
            - (`Anime`) the coresponding `Anime` to the mal_id
        """
        async with AioJikan() as jikan:
            resp = await jikan.anime(mal_id)
            anime = Anime.from_json(resp)
        log.debug(f"fetched anime from REST: {anime}")
        return anime

    @classmethod
    async def _fetch_anime_by_id_db(
        cls,
        mal_id: int
    ) -> Optional[Anime]:
        """
        Returns:
        -------
            - (`Anime` | `None`) the coresponding `Anime` to the id or `None` if not cached
        """
        table = Table("myanimelist")
        record = await table.fetch_by_id("mal_id", mal_id)
        if not record:
            return None
        anime = Anime.from_db_record(record)
        log.debug(f"fetched anime from db: {anime}")
        return anime

    @classmethod
    async def _update_anime_by_id(cls, mal_id: int):
        pass

    @classmethod
    async def _cache_anime(cls, anime: Anime):
        """
        Args:
        ----
            - (`Anime`) the `Anime` which should be stored in the db
        """
        table = Table("myanimelist")
        r = await table.upsert(
            which_columns=[
                "mal_id", "title", "title_english", 
                "title_japanese", "title_synonyms", "synopsis", 
                "background", "related", "themes", "explicit_genres", 
                "genres", "type", "episodes", "ending_themes", 
                "opening_themes", "duration", "rating", "rank", 
                "score", "popularity", "favorites", "source", 
                "status", "airing", "airing_start", "airing_stop", 
                "image_url", "mal_url", "trailer_url", "licensors", 
                "producers", "studios", "cached_until"
            ],
            values=[
                anime.mal_id, anime.title, anime.title_english, anime.title_japanese,
                anime.title_synonyms, anime.synopsis, anime.background,
                json.dumps(anime.related),
                [json.dumps(x) for x in anime.themes], 
                [json.dumps(x) for x in anime.explicit_genres], 
                [json.dumps(x) for x in anime.genres], anime.type_, 
                anime.episodes, anime.ending_themes, anime.opening_themes, anime.duration, 
                anime.rating, anime.rank, anime.score, anime.popularity, 
                anime.favorites, anime.source, anime.status, anime.airing, 
                anime.airing_start, anime.airing_stop, anime.image_url, anime.mal_url, 
                anime.trailer_url,
                [json.dumps(x) for x in anime.licensors], 
                [json.dumps(x) for x in anime.producers], 
                [json.dumps(x) for x in anime.studios], 
                anime.cached_until
            ]
        )
        log.debug(f"cached anime: {anime}")