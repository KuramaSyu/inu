from ast import alias
import re
import typing
from typing import (
    Optional,
    List,
    Union,

)

import hikari
import lightbulb
from lightbulb import Context
import asyncpg

from core import Inu
from utils.tag_mamager import TagIsTakenError, TagManager
from utils import crumble
from utils.colors import Colors

class Tags(lightbulb.Plugin):

    def __init__(self, bot: Inu):
        self.bot = bot
        super().__init__(name=self.__class__.__name__)

    @lightbulb.group()
    async def tag(self, ctx: Context, key: str):
        """Get the tag by `key`"""
        records = await TagManager.get(key, ctx.guild_id or 0)
        record: asyncpg.Record
        # if records are > 1 return the local overridden one
        if len(records) > 1:
            typing.cast(int, ctx.guild_id)
            for r in records:
                if not r["guild_id"] == ctx.guild_id:
                    continue
                record = r
        else:
            record = records[0]
        embeds = []

        for value in crumble("\n".join(record["tag_value"])):
            tag_embed = hikari.Embed()
            tag_embed.title = f"{key}"
            tag_embed.description = value
            tag_embed.color = Colors.random_color()
            embeds.append(tag_embed)

    @tag.command()
    async def add(self, ctx: Context, key: str, value: Optional[str] = None):
        """Add a tag"""
        if value == None:
            return
        typing.cast(str, value)
        try:
            await TagManager.set(key, value, ctx.author.id)
        except TagIsTakenError:
            return await ctx.respond("Your tag is already taken")
        return await ctx.respond("Your tag `{key}` has been added to my storage")
        



    @tag.command(aliases=["del"])
    async def remove(self, key):
        pass

    @tag.command()
    async def edit(self, key):
        pass

def load(bot: Inu):
    bot.add_plugin(Tags(bot))
