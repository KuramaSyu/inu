import asyncio
from typing import *
from urllib.parse import urlencode
from datetime import datetime
from pprint import pformat as pf
import logging
logging.basicConfig(format='%(asctime)s %(message)s')
import jikanpy
from enum import Enum

import aiohttp
import dotenv
import asyncio
from fuzzywuzzy import fuzz

from core import getLogger

log = getLogger(__name__)

class MALRatings(Enum):
    g = "G - All Ages"
    pg = "PG - Children"
    pg_13 = "PG-13 - Teens 13 or older"
    r = "R - 17+ (violence & profanity) "
    r_plus = "R+ - Mild Nudity 17+"
    rx = "Rx - Hentai 18+"




class MALTypes(Enum):
    ANIME = 1
    MANGA = 2

class MyAnimeListAIOClient:
    """Wrapper for MyAnimeList API Endpoint"""
    client_id: str = ""


    def __init__(
        self,
        client_id: str = None,
    ):
        """A wrapper for the Non-user based mal api endpoints (-> no oauth needed)"""
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.INFO)
        self._id = client_id or self.client_id or dotenv.dotenv_values()["ID"]
        if not self._id and not self.client_id:
            raise RuntimeError(
                "Client id has to be passed into the constructor or in the .env file under key `ID`. Consider calling `set_credentails`"
            )
        self._base_url = r"https://api.myanimelist.net/v2"
        self._session = aiohttp.ClientSession()

    @classmethod
    def set_credentials(cls, client_id: str):
        """"set the client id"""
        cls.client_id = client_id

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get AioHTTP session by creating it if it doesn't already exist"""
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _make_request(
        self,
        endpoint: str,
        value: Optional[str] = None,
        optional_query: Dict[str, str] = None,
    ):
        query = None
        if value and not value.startswith("/"):
            value = "/" + value
        if optional_query:
            query = f"?{urlencode(optional_query)}"
        url = f"{self._base_url}/{endpoint}{value or ''}{query or ''}"
        async with self.session.get(url, headers=self.headers) as resp:
            json = await resp.json(encoding="utf-8")
        await self._session.close()
        self.log.debug(f"request: {url}")
        self.log.debug(f"response: {pf(json)}")
        if not resp.ok:
            raise RuntimeError(f"{url} returned status code {resp.status}")
        return json

    @property
    def headers(self) -> Dict[str, str]:
        if not self._id:
            raise RuntimeError("Client id has to be passed into the constructor or in the .env file under key `ID`")
        return {"X-MAL-CLIENT-ID": self._id}

    async def fetch_anime(
        self,
        id: int
    ) -> Dict[str, Any]:
        """fetch an Anime by it's ID
        
        Args:
        -----
        id : int
            the mal ID of that anime
        """
        fields = (
            "id,title,main_picture,alternative_titles,"
            "start_date,end_date,synopsis,mean,rank,popularity,"
            "num_list_users,num_scoring_users,nsfw,created_at,"
            "updated_at,media_type,status,genres,my_list_status,"
            "num_episodes,start_season,broadcast,source,"
            "average_episode_duration,rating,pictures,background,"
            "related_anime,related_manga,recommendations,studios,statistics,"
            "average_episode_duration,opening_themes,ending_themes"
        )
        resp = await self._make_request(
            endpoint="anime",
            value=str(id),
            optional_query={"fields": fields}
        )
        return resp

    async def _search(self):
        pass

    async def search_anime(self, query: str, include_nsfw=True) -> Dict[str, Any]:
        """search for anime by name

        Args:
        -----
        query : str
            the query to search for
        include_nsfw : bool
            whether to include nsfw results
        
        Returns:
        --------
        Dict[str, Any]
            the response json
        """
        fields = (
            "id,title,main_picture,alternative_titles,"
            "start_date,end_date,synopsis,mean,rank,popularity,"
            "num_list_users,num_scoring_users,nsfw,created_at,"
            "updated_at,media_type,status,genres,my_list_status,"
            "num_episodes,start_season,broadcast,source,"
            "average_episode_duration,rating,pictures,background,"
            "related_anime,related_manga,recommendations,studios,statistics,"
            "average_episode_duration,opening_themes,ending_themes"
        )
        a = datetime.now()
        kwargs = {"nsfw": "true" if include_nsfw else "false"}
        resp = await self._make_request(endpoint="anime", optional_query={"q": query, "fields":fields, "limit":"50", **kwargs})
        log.info(f"fetched {len(resp['data'])} anime in {(datetime.now() - a).total_seconds():.2f}s")
        return resp





