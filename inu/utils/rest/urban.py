from typing_extensions import Self
from urllib import response
from xml.dom import InuseAttributeErr
import requests
import aiohttp
from typing import *
import asyncio
from pprint import *
from collections.abc import Iterable

from core import Inu, BotResponseError, getLogger
log = getLogger(__name__)

class UrbanIterator(Iterable):
    def __init__(
        self,
        orig: str,
        response_json: dict,
    ):
        self.word = orig
        self.json = response_json
        self.json['list'].sort(key=lambda d: d['thumbs_up'], reverse=True)
        self.definitions = [d["definition"] for d in response_json['list']]
        self.examples = [d["example"] for d in response_json['list']]

    def __iter__(self) -> Generator[Dict[str, str], None, None]:
        return (d for d in self.json['list'])

class Urban:
    bot: Inu = None

    def inu(func: "function"):
        '''asserts, that bot is instance of Inu'''
        async def wrapper(*args, **kwargs):
            cls = args[0]
            assert(isinstance(cls.bot, Inu))
            return await func(*args, **kwargs)
        return wrapper



    @classmethod
    def init_bot(cls, bot: Inu):
        cls.bot = bot


    @classmethod
    @inu
    async def fetch(cls, word: str) -> UrbanIterator:
        url = "https://mashape-community-urban-dictionary.p.rapidapi.com/define"

        querystring = {"term":word}

        headers = {
            'x-rapidapi-host': "mashape-community-urban-dictionary.p.rapidapi.com",
            'x-rapidapi-key': cls.bot.conf.KEYS.RAPID
            }
        r = None
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=querystring) as resp:
                r = await resp.json()
        if not r:
            raise RuntimeError(f"no response received from {headers['x-rapidapi-host']}")
        if not r['list']:
            raise BotResponseError(f"Well -- I never heard `{word}`")
        # log.debug(r)
        return UrbanIterator(word, r)



if __name__ == "__main__":
    async def main(w="stfu"):
        urban_resp =  await Urban.fetch(w)
        for a in urban_resp:
            print(a["definition"])
            print("~~~~~~")
            print(a["example"] + "\n\n\n\n")
        pprint(urban_resp.json)

    asyncio.run(main())