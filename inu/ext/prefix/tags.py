import re
import typing
from typing import (
    Optional,
    List,
    Union,

)
import logging
from logging import DEBUG

import hikari
from hikari import Embed
from hikari.impl import ActionRowBuilder
from hikari.messages import ButtonStyle
import lightbulb
from lightbulb import Context
from lightbulb.converters import Greedy
import asyncpg

from core import Inu
from utils.tag_mamager import TagIsTakenError, TagManager
from utils import crumble
from utils.colors import Colors
from utils import Paginator
from utils.paginators.common import navigation_row

log = logging.getLogger(__name__)
log.setLevel(DEBUG)


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
        elif len(records) == 0:
            return await ctx.respond(f"I can't find a tag with name `{key}` in my storage")
        else:
            record = records[0]
        messages = []

        for value in crumble("\n".join(record["tag_value"])):
            message = f"**{key}**\n\n{value}\n\n`created by {self.bot.cache.get_user(record['creator_id']).username}`"
            messages.append(message)
        pag = Paginator(messages)
        await pag.start(ctx)

    @tag.command()
    async def add(self, ctx: Context, key: str, *, value: str):
        """Add a tag"""
        print(value)
        if value == None:
            return
        typing.cast(str, value)
        try:
            await TagManager.set(key, value, ctx.member or ctx.author)
        except TagIsTakenError:
            return await ctx.respond("Your tag is already taken")
        return await ctx.respond(f"Your tag `{key}` has been added to my storage")
        



    @tag.command(aliases=["del"])
    async def remove(self, key):
        pass

    @tag.command()
    async def edit(self, key):
        pass


    def tag_embed_builder(self) -> List[Embed]:
        start_page = hikari.Embed()
        start_page.title = "Select what you want to do"

    def components_builder(self, position: int) -> List[ActionRowBuilder]:
        start_page = [(
            ActionRowBuilder()
            .add_button(ButtonStyle.PRIMARY, "add_tag")
            .set_label("Add tag")
            .add_to_container()
            .add_button(ButtonStyle.PRIMARY, "edit_tag")
            .set_label("Edit tag")
            .add_to_container()
            .add_button(ButtonStyle.DANGER, "remove_tag")
            .set_label("Remove tag")
            .add_to_container()
        ), navigation_row(position, compact=True, len_pages=0)]
        add_tag = [(
            ActionRowBuilder()
            .add_button(ButtonStyle.PRIMARY, "set_key")
            .set_label("Set a name")
            .add_to_container()
            .add_button(ButtonStyle.PRIMARY, "edit_tag")
            .set_label("Edit tag")
            .add_to_container()
            .add_button(ButtonStyle.DANGER, "remove_tag")
            .set_label("Remove tag")
            .add_to_container()
        ), navigation_row(position, compact=True, len_pages=0)]
        edit_tag = [(
            ActionRowBuilder()
            .add_button(ButtonStyle.PRIMARY, "remove_tag")
            .set_label("Remove tag")
            .add_to_container()
            .add_button(ButtonStyle.PRIMARY, "rename_tag")
            .set_label("Rename tag")
            .add_to_container()
            .add_button(ButtonStyle.DANGER, "change_owner")
            .set_label("Change owner")
            .add_to_container()
            .add_button(ButtonStyle.PRIMARY, "tag_set")
            .set_label("new value")
            .add_to_container()
            .add_button(ButtonStyle.PRIMARY, "tag_append")
            .set_label("extend Value")
            .add_to_container()
        )]

    async def tag_add_i(self, ctx):
        pass


def load(bot: Inu):
    bot.add_plugin(Tags(bot))
