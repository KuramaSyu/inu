from ast import alias
import typing
from typing import (
    Optional,
    List,
    Union,

)

import hikari
import lightbulb

from core import Inu

class Tags(lightbulb.Plugin):

    def __init__(self, bot: Inu):
        self.bot = bot
        super().__init__(name=self.__class__.__name__)

    @lightbulb.group()
    async def tag(self, key):
        """Get the tag by `key`"""
        pass

    @tag.command()
    async def add(self, key, value: Optional[str] ):
        if value == None:
            pass

    @tag.command(aliases=["del"])
    async def remove(self, key):
        pass

    @tag.command()
    async def edit(self, key):
        pass
