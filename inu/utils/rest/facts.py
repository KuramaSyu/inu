from typing import *
from urllib.parse import urlencode
from pprint import pprint
import asyncio

import aiohttp

from core import ConfigProxy, ConfigType

class RESTFacts():
    _key = (ConfigProxy(ConfigType.YAML)).api_ninjas.SECRET
    _base_url = "https://api.api-ninjas.com/v1/"
    _session = None

    @classmethod
    async def fetch_facts(cls, amount: int = 30) -> List[Dict[str, str]]:
        """
        Args:
        -----
            amount : int
                the amount of facts to return. 1 - 30
        """
        json = await cls._make_request(
            endpoint="facts",
            optional_query={"limit": str(amount)}
        )
        return json



    @classmethod
    def session(cls) -> aiohttp.ClientSession:
        """Get AioHTTP session by creating it if it doesn't already exist"""
        if not cls._session or cls._session.closed:
            cls._session = aiohttp.ClientSession()
        return cls._session

    @classmethod
    async def _make_request(
        cls,
        endpoint: str,
        value: Optional[str] = None,
        optional_query: Dict[str, str] = None,
    ):
        query = None
        if value and not value.startswith("/"):
            value = "/" + value
        if optional_query:
            query = f"?{urlencode(optional_query)}"
        url = f"{cls._base_url}/{endpoint}{value or ''}{query or ''}"
        async with cls.session().get(url, headers=cls.headers()) as resp:
            json = await resp.json(encoding="utf-8")
        await cls._session.close()
        if not resp.ok:
            raise RuntimeError(f"{url} returned status code {resp.status}")
        return json

    @classmethod
    def headers(cls) -> Dict[str, str]:
        if not cls._key:
            raise RuntimeError("Client id has to be passed into the constructor or in the .env file under key `ID`")
        return {"X-Api-Key": cls._key}