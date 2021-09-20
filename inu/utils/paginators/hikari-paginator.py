import asyncio
import typing
from typing import (
    Optional,
    Union,
    List,
)

import hikari
from hikari.embeds import Embed
import lightbulb
from lightbulb.context import Context

from inu.inu import Inu


class BasePaginator():
    def __init__(
        self,
        page_s: Union[Embed, List[Embed], str, List[str]],
        convert_to_embed = True,
        timeout: int = 120,
    ):
        self.pages: Union[List[Embed], List[str]] = self.create_pages()
        self.bot: Inu
        self.ctx: Context
        self.loop: asyncio.AbstractEventLoop
        self._tasks = None



    def create_pages(self) -> Union[List[str], List[Embed]]:
        return [Embed()]
