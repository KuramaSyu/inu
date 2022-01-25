import json
from typing import Optional, Dict, Mapping, Union, Any, TypeVar
from urllib.parse import urlencode
import requests
from pprint import pformat

import aiohttp
from jikanpy.exceptions import APIException, DeprecatedEndpoint
import simplejson

from core import getLogger
log = getLogger(__name__)


BASE_URL = "https://api.jikan.moe/v4"


def add_jikan_metadata(
    response: Union[requests.Response, aiohttp.ClientResponse],
    response_dict: Dict[str, Any],
    url: str,
) -> Dict[str, Any]:
    """Adds the response headers and jikan endpoint url to response dictionary."""
    response_dict["jikan_url"] = url

    # We need this if statement so that static type checking can determine what the type
    # of response is
    if isinstance(response, aiohttp.ClientResponse):
        # Convert from CIMultiDictProxy[str] for aiohttp.ClientResponse
        response_dict["headers"] = dict(response.headers)
    else:
        # Convert from CaseInsensitiveDict[str] for requests.Response
        response_dict["headers"] = dict(response.headers)

    return response_dict


class AioJikanv4:
    def __init__(
        self,
        base: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ):

        self.session = session
        self.base = (
            BASE_URL if base is None else base.rstrip("/ ")
        )

    async def getAnimeSearch(self, query: str) -> Dict:
        url = self._build_search_url(
            endpoint="/anime",
            query=query.lower(),
            sort="desc",
            order_by="score",
        )
        # kwargs = {"search type": search_type, "query": query}
        resp = await self._request(url)
        log.debug(pformat(resp))
        log.info(f"{url=}")
        return resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *excinfo: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close AioHTTP session"""
        if self.session is not None:
            await self.session.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get AioHTTP session by creating it if it doesn't already exist"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def _wrap_response(
        self,
        response: aiohttp.ClientResponse,
        url: str,
        **kwargs: Union[int, Optional[str]],
    ) -> Dict[str, Any]:
        """Parses the response as json, then runs check_response and
        add_jikan_metadata
        """
        json_response: Dict[str, Any] = {}
        try:
            json_response = await response.json()
            if not isinstance(json_response, dict):
                json_response = {"data": json_response}
        except (json.decoder.JSONDecodeError, simplejson.JSONDecodeError):
            json_response = {"error": await response.text()}
        if response.status >= 400:
            raise APIException(response.status, json_response, **kwargs)
        return add_jikan_metadata(response, json_response, url)

    async def _request(
        self, url: str, **kwargs: Union[int, Optional[str]]
    ) -> Dict[str, Any]:
        """Makes a request to the Jikan API given the url and wraps the response."""
        session = await self._get_session()
        response = await session.get(url)
        return await self._wrap_response(response, url, **kwargs)

    def _build_search_url(self, endpoint: str, query: str, **additional) -> str:
        query = query.lower()
        partial_url = dict(q=query)
        partial_url.update(additional)
        query = urlencode(partial_url)
        return f"{self.base}{endpoint}?{query}"