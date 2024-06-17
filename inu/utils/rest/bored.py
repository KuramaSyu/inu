from typing import *
import aiohttp
import hikari

from utils import Colors
{
  "activity": "Make a couch fort",
  "type": "recreational",
  "participants": 1,
  "price": 0,
  "link": "",
  "key": "2352669",
  "accessibility": 0.08
}
class BoredIdea:
    def __init__(self, response: Dict[str, Union[str, float, int]]):
        self.response = response
        self.activity: str = response["activity"]
        self.type: str = response["type"]
        self.participants: int = response["participants"]
        self.price: int = response["price"]
        self.link: str = response["link"]
        self.key: str = response["key"]
        self.accessibility: float = response["accessibility"]

    @property
    def embed(self) -> hikari.Embed:
        return hikari.Embed(
            title=f"{self.activity}",
            description=f"{self.type} | {self.participants} participants | {self.price}€ | accessibility: {self.accessibility}",
            color=Colors.random_blue(),
        )

class BoredAPI:
    Endpoint = "https://bored-api.appbrewery.com/random"
    @classmethod
    async def fetch_idea(cls, ssl: bool = True) -> BoredIdea:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(cls.Endpoint, ssl=ssl) as resp:
                    json_resp = await resp.json()
            return BoredIdea(json_resp)
        except aiohttp.ClientConnectorCertificateError as e:
            if not ssl:
                raise e
            else:
                return await cls.fetch_idea(ssl=False)

