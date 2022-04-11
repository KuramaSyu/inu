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

# from core import ConfigProxy

# conf = ConfigProxy(config_type="yaml")









class MALTypes(Enum):
    ANIME = 1
    MANGA = 2

class MyAnimeListAIOClient:
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

    async def search_anime(self, query: str) -> Dict[str, Any]:
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
        return await self._make_request(endpoint="anime", optional_query={"q": query, "fields":fields})


# class LazyAnimeIterator():
#     """
#     An iterator for the `Anime` class which takes in a List of Anime where Anime.id is needed.
#     All details will be fetched by id when iterated over.
#     """

#     def __init__(self, animes: List[Anime]):
#         """
#         Parameters
#         ----------
#         animes: `List[Anime]`
#             the list of animes
#         """
#         self._animes: List[Anime] = animes
#         self._index = 0

#     def __aiter__(self):
#         return self
        
#     async def __anext__(self):
#         if self._index >= len(self._animes)-1:
#             raise StopAsyncIteration
#         self._index += 1
#         return await self._animes[self._index].fetch_details()

#     async def __aexit__(self):
#         raise StopAsyncIteration



# if __name__ == "__main__":
#     async def main():

#         client = MyAnimeListAIOClient(client_id="3203ce3277af7e71ca5eabb7e8298c7b")
#         animes = await client.search_anime("naruto")
#         i = LazyAnimeIterator(animes)
#         async for a in i:
#             print(a.title)

#     asyncio.run(main())




