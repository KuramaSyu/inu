import asyncio
from jikanpy import AioJikan
import json
from pprint import pprint, pformat

async def fetch(anime="cowboy bebop"):
    async with AioJikan() as jikan:
        # resp = await jikan.search("anime", anime)
        resp = await jikan.anime(1)
        with open("models/animev3_resp", "w", encoding="utf-8") as f:
            f.write(pformat(resp))

asyncio.run(fetch())