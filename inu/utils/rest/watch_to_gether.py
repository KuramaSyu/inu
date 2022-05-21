from typing import Optional


from typing import *
import json

import asyncio
import aiohttp
from matplotlib.pyplot import get

from core import Table, Inu, ConfigProxy, getLogger
from utils import Colors

log = getLogger(__name__)   


class Watch2Gether:
    _headers: Dict[str, str] = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'   
    }
    # Satisfactory OST
    _default_link = "https://www.youtube.com/watch?v=67jNiQ6xhnU"
    _conf: ConfigProxy = ConfigProxy()

    @classmethod
    def _make_body(cls, link: Optional[str]) -> Dict[str, str]:
        b = {
        "w2g_api_key": cls._conf.w2g.ID,
        "share": link or cls._default_link,
        "bg_color": Colors.default_color(0.55, True),
        "bg_opacity": "99"      
        }
        log.debug(f"{b}")
        return b

    @classmethod
    async def fetch_link(cls, link: Optional[str] = None):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://w2g.tv/rooms/create.json", 
                data=json.dumps(cls._make_body(link)), 
                headers=cls._headers
            ) as resp:
                return await resp.json()