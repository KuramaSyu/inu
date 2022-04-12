import imp
import json
from pprint import pformat
from shutil import which
from typing import *
from datetime import datetime, timedelta
import time
import traceback

import aiohttp
from jikanpy import AioJikan

from core import Database, Table, getLogger
from utils import Multiple, MyAnimeListAIOClient, MALRatings

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
        related: Dict[str, List[Dict[str, Union[Any]]]],
        genres: List[Dict[str, str]],
        type_: str,
        episodes: Optional[int],
        ending_themes: List[str],
        opening_themes: List[str],
        duration: int,
        rating: str,
        rank: Optional[int],
        score: Optional[float],
        popularity: Optional[int],
        source: Optional[str],
        status: str,
        airing_start: Optional[datetime],
        airing_stop: Optional[datetime],
        image_url: str,
        studios: List[Dict[str, str]],
        cached_for: Optional[int] = None,
        cached_until: Optional[datetime] = None,
        response: Dict[str, Any] = None,
        statistics: Dict[str, Union[Dict[str, str], str, int]] = None,
        recommendations: Optional[List[Dict[str, Dict[str, str]]]] = None

    ):
        self.client = MyAnimeListAIOClient()
        self.resp = response or {}
        self._details_loaded: bool = False

        self.mal_id: int = mal_id
        self._title = title
        self.title_english: str = title_english
        self.title_japanese: str = title_japanese
        self.title_synonyms: List[str] = title_synonyms
        self.synopsis: str = synopsis
        self.background: str = background
        self.related: Dict[str, List[Dict[str, Union[Any]]]] = related
        self.genres: List[Dict[str, str]] = genres
        self.type_: str = type_
        self.episodes: Optional[int] = episodes
        self.ending_themes: List[str] = ending_themes
        self.opening_themes: List[str] = opening_themes
        self.duration: int = duration  # average seconds
        self._rating: str = rating
        self.rank: Optional[int] = rank
        self.score: Optional[float] = score
        self.popularity: Optional[int] = popularity
        self._source: Optional[str] = source
        self.status: str = status
        self.airing_start: Optional[datetime] = airing_start
        self.airing_stop: Optional[datetime] = airing_stop
        self.image_url: str = image_url
        self.studios: List[Dict[str, str]] = studios
        self._statistics: Dict[str, Union[Dict[str, str], str, int]] = statistics
        self._recommendations: List[Dict[str, Dict[str, str]]]
        if not recommendations:
            self._recommendations = []
        else:
            self._recommendations = recommendations
        if cached_for:
            self._cached_for: int = cached_for
        else:
            self._cached_for = int(self.cached_until.timestamp()) - int(time.time())

    async def fetch_details(self) -> "Anime":
        """fetches anime details"""
        if self.details_loaded:
            return self
        new_anime = await self.client.fetch_anime(self.id)
        self.__dict__.update(new_anime.__dict__)
        self._details_loaded = True
        return self
    
    # def _load_detail_response(self, response: Dict[str, Any]) -> "Anime":
    #     """deserielizes response into self"""
    #     self.resp = response
    #     self._details_loaded = True
    #     self._title = self.resp.get('title')
    #     self._id = self.resp.get('id')
    #     self.alternative_titles = self.resp.get('alternative_titles')
    #     if self.alternative_titles:
    #         self.title_synonyms = self.alternative_titles.get('synonyms')
    #     self.average_episode_duration = self.resp.get('average_episode_duration')
    #     self.background = self.resp.get('background', "")
    #     self.broadcast = self.resp.get('broadcast')
    #     self._created_at = self.resp.get('created_at')
    #     self._end_date = self.resp.get('end_date')
    #     self.ending_themes = self.resp.get('ending_themes', [])
    #     self.genres = self.resp.get('genres', [])
    #     self._id = self.resp.get('id')
    #     self.main_picture = self.resp.get('main_picture')
    #     self.mean_score = self.resp.get('mean')
    #     self.media_type = self.resp.get('media_type')
    #     self.nsfw= self.resp.get('nsfw')
    #     self.num_episodes= self.resp.get('num_episodes')
    #     self.num_list_users = self.resp.get('num_list_users')
    #     self.num_scoring_users = self.resp.get('num_scoring_users')
    #     self.opening_themes = self.resp.get('opening_themes', [])
    #     self.pictures = self.resp.get('pictures')
    #     self.popularity = self.resp.get('popularity')
    #     self.rank = self.resp.get('rank')
    #     self._rating = self.resp.get('rating', "")
    #     self.recommendations = self.resp.get('recommendations')
    #     self.related_anime = self.resp.get('related_anime')
    #     self.related_manga = self.resp.get('related_manga')
    #     self._source = self.resp['source']
    #     self.start_date = self.resp.get('start_date')
    #     self.start_season = self.resp.get('start_season')
    #     self._statistics = self.resp.get('statistics')
    #     self.status = self.resp['status']
    #     self.studios = self.resp.get('studios', [])
    #     self.synopsis = self.resp.get('synopsis', "")
    #     self._updated_at = self.resp.get('updated_at')
    #     return self


    @property
    def origin_title(self) -> str:
        """returns the original title of the anime"""
        return self._title

    @property
    def completion_rate(self) -> str:
        """returns the completition rate from users watching it of the anime"""
        try:
            ammount = int(self._statistics["status"]["completed"]) + int(self._statistics["status"]["dropped"])
            rate = f"{float(int(self._statistics['status']['completed']) / ammount * 100):.1f}%"
        except (TypeError, ZeroDivisionError):
            log.warning(traceback.format_exc())
            rate = "Unknown"
        return rate

    @property
    def recommendations(self) -> List[Dict[str, Union[str, int]]]:
        """
        Returns:
        --------
        List[Dict[str, Union[str, int]]]:
            List with dicts with keys mal_id and title
        """
        result: List[Dict[str, Union[str, int]]] = []
        for d in self._recommendations:
            node = d["node"]
            result.append(
                {   "mal_id": int(node["id"]),
                    "url": f'https://myanimelist.net/anime/{int(node["id"])}',
                    "title": str(node["title"])
                }
            )
        return result


    @property
    def mal_url(self) -> str:
        """returns the url to the anime on myanimelist"""
        return f"https://myanimelist.net/anime/{self.mal_id}"

    @property
    def rating(self) -> str:
        try:
            r = self._rating.replace("+", "_plus")
            return MALRatings[r].value
        except KeyError:
            return self._rating

    @property
    def source(self):
        if self._source is None:
            return "Unknown"
        return self._source.replace("_", " ")

    @property
    def id(self) -> int:
        return self.mal_id

    @property
    def title(self) -> str:
        """
        Returns:
        -------
            - (`str`) the english title or the original title. English is prefered
        """
        if self.origin_title == self.title_english:
            return self.origin_title
        elif self.title_english:
            return self.title_english
        else:
            return self.origin_title

    @property
    def cached_until(self) -> datetime:
        """
        Note:
        -----
            - it'll cache until 9999/12/31 if the anime is finsished. 
              Otherwise obout 1 month (given from jikan meta data)
         """
        if not self.airing_stop:
            return datetime.now() + timedelta(days=30)
        elif self.airing_stop.year - datetime.now().year > 15:
            return datetime.now() + timedelta(days=180)
        elif self.airing_stop.year - datetime.now().year > 10:
            return datetime.now() + timedelta(days=90)
        else:
            return datetime.now() + timedelta(days=30)
    
    def __str__(self) -> str:
        return f"[{self.mal_id}] {self.title}"

    @staticmethod
    def markup_link_list(list_: List[Dict[str, str]], title_key_name:str = "title"):
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
        return [f"[{x[title_key_name]}]({x['url']})" for x in list_]

    @staticmethod
    def markup_link_str(list_: List[Dict[str, str]], title_key_name: str = "title"):
        """
        Args:
        -----
            - list_ (`List[Dict[str,str]]`) the list which should be converted
                - NOTE: The dict needs the keys: `"url"` and `"name"`

        Returns:
        --------
            - (`str`) the markup string which ", " seperated list entries

        Note:
        -----
            - this function is meant for `self.`|`genres`|`explicit_genres`|`themes`|`studios`|`licensors`|`producers`
        """
        return ", ".join([f"[{x[title_key_name]}]({x['url']})" for x in list_])

    @staticmethod
    def markup_link_str_by_name_id(list_: List[Dict[str, str]], base_url: str, title_key_name: str = "title"):
        """
        Args:
        -----
            - list_ (`List[Dict[str,str]]`) the list which should be converted
                - NOTE: The dict needs the keys: `"id"` and `"name"`

        Returns:
        --------
            - (`str`) the markup string which ", " seperated list entries

        Note:
        -----
            - this function is meant for `self.`|`genres`|`explicit_genres`|`themes`|`studios`|`licensors`|`producers`
        """
        return ", ".join([f"[{x[title_key_name]}]({x['url']})" for x in list_]) 

    @property
    def airing_str(self) -> str:
        """
        Returns:
        -------
            - (`str`) The string from the airing time of the Anime
        """
        if self.airing_start:
            start = f"{self.airing_start.year or '?'}/{f'{self.airing_start.month:02}' or '?'}"
        else:
            start = "?"
        if self.airing_stop:
            stop = f" {self.airing_stop.year or '?'}/{f'{self.airing_stop.month:02}' or '?'}"
        else:
            stop = ""
        return f"{start} {'- ' + stop if stop else ''}"

    @classmethod
    def from_json(cls, resp: Dict[str, Any]) -> "Anime":
        """
        ### build an Anime with the Mal API v2 json response
        Returns:
        --------
            - (`~.Anime`) The coresponding Anime to the json
        """
        airing_start = None
        airing_stop = None
        # example-date = '1999-04-24'
        try:
            airing_start = datetime.strptime(resp["start_date"], '%Y-%m-%d')
        except Exception:
            pass
        try:
            airing_stop = datetime.strptime(resp["end_date"], '%Y-%m-%d')
        except Exception:
            pass
        
        # recreate related
        related: Dict[str, List[Dict[str, Any]]] = {}
        relations = set([r["relation_type"] for r in [*resp["related_anime"], *resp["related_manga"]]])
        for relation in relations:
            related[relation] = []
        for a in resp["related_anime"]:
            related[a["relation_type"]].append(
                {   
                    "title": a["node"]["title"],
                    "url": f"https://myanimelist.net/anime/{a['node']['id']}",
                    "type": "Anime",
                    "mal_id": a["node"]["id"],
                    "relation_type": a["relation_type"],
                    "relation_type_formatted": a["relation_type_formatted"],
                    "picture": a["node"]["main_picture"]["large"],
                }
            )
        for m in resp["related_manga"]:
            related[m["relation_type"]].append(
                {
                    "title": m["node"]["title"],
                    "url": f"https://myanimelist.net/manga/{m['node']['id']}",
                    "type": "Manga",
                    "relation_type": m["relation_type"],
                    "relation_type_formatted": m["relation_type_formatted"],
                    "picture": m["node"]["main_picture"]["large"],
                } 
            )

        anime = cls(
            mal_id=resp["id"],
            title=resp["title"],
            title_english=resp["alternative_titles"].get("en"),
            title_japanese=resp["alternative_titles"].get("ja"),
            title_synonyms=resp["alternative_titles"].get("synonyms", []),
            synopsis=resp["synopsis"],
            background=resp["background"],
            related=related,
            genres=[g["name"] for g in resp["genres"]],
            type_=resp["media_type"],
            episodes=resp["num_episodes"],
            ending_themes=[item["text"] for item in resp.get("ending_themes", [])],
            opening_themes=[item["text"] for item in resp.get("opening_themes", [])],
            duration=resp["average_episode_duration"],
            rating=resp["rating"],
            rank=resp.get("rank", None),
            score=resp.get("mean", None),
            popularity=resp.get("popularity"),
            source=resp.get("source"),
            status=resp["status"],
            airing_start=airing_start,
            airing_stop=airing_stop,
            image_url=resp["main_picture"]["large"],
            studios=[s["name"] for s in resp["studios"]],
            statistics=resp["statistics"],
            recommendations=resp["recommendations"],
        )
        anime._details_loaded = True
        return anime
    
    @property
    def details_loaded(self) -> bool:
        return self._details_loaded

    @property
    def links(self) -> Dict[str, str]:
        """
        Returns:
        -------
            - (`Dict[str, str]`) mapping from site + dub/dub and the link, where the anime COULD be
        Note:
        -----
            - through cloudflare protection, checking if link is valid is not possbile
            - The link could return 404
        """
        title = self.origin_title.lower()
        title = Multiple.repalce_(title, ".;,: ", "-")
        title = title.replace("--", "-")
        while title.endswith("-"):
            title = title[:-1]
        links = {}
        links_temp = {}
        links_temp["animeheaven"] = f"https://animeheaven.ru/detail/{title}"
        for k, v in links_temp.items():

            links[f"{k}-sub"] = f"{v}"
            links[f"{k}-dub"] = f"{v}-dub"
        return links


    @classmethod
    def from_db_record(cls, resp: Dict[str, Any]) -> "Anime":
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
        anime = cls(
            mal_id=resp["mal_id"],
            title=resp["title"],
            title_english=resp["title_english"],
            title_japanese=resp["title_japanese"],
            title_synonyms=resp["title_synonyms"],
            synopsis=resp["synopsis"],
            background=resp["background"],
            related=json.loads(resp["related"]),
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
            source=resp["source"],
            status=resp["status"],
            airing_start=resp["airing_start"],
            airing_stop=resp["airing_stop"],
            image_url=resp["image_url"],
            studios=[json.loads(x) for x in resp["studios"]],
            cached_until=resp["cached_until"],
            statistics=json.loads(resp["statistics"]),
            recommendations=[json.loads(x) for x in resp["recommendations"]]
        )
        anime._details_loaded = True
        return anime
    
    @property
    def needs_update(self) -> bool:
        """
        ### wether or not the anime needs an update (related to `cached_until`)
        """
        if self.cached_until < datetime.now():
            return True
        return False



class MyAnimeList:
    """A class, which stores MyAnimeList data for caching purposes in a Database, or fetches it from jikan"""

    @classmethod
    async def search_anime(cls, query: str) -> Dict[str, Any]:
        resp = await MyAnimeListAIOClient().search_anime(query)
        return resp

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
        client = MyAnimeListAIOClient()
        resp = await client.fetch_anime(mal_id)
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
                "background", "related",
                "genres", "type", "episodes", "ending_themes", 
                "opening_themes", "duration", "rating", "rank", 
                "score", "popularity", "source", 
                "status", "airing_start", "airing_stop", 
                "image_url", "studios", "cached_until", "statistics", "recommendations"
            ],
            values=[
                anime.mal_id, anime.origin_title, anime.title_english, anime.title_japanese,
                anime.title_synonyms, anime.synopsis, anime.background,
                json.dumps(anime.related),
                [json.dumps(x) for x in anime.genres], anime.type_, 
                anime.episodes, anime.ending_themes, anime.opening_themes, anime.duration, 
                anime._rating, anime.rank, anime.score, anime.popularity, anime._source,
                anime.status,
                anime.airing_start, anime.airing_stop, anime.image_url,
                [json.dumps(x) for x in anime.studios], 
                anime.cached_until, json.dumps(anime._statistics), 
                [json.dumps(r) for r in anime._recommendations]
            ]
        )
        log.debug(f"cached anime: {anime}")