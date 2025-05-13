import asyncio
import logging
import typing
from datetime import datetime
from typing import *
from numpy import full, isin

import aiohttp
import hikari
from hikari import TextInputComponent, ButtonStyle, ApplicationContextType
import lightbulb
from lightbulb import AutocompleteContext, commands, SlashCommand, invoke

import hikari


from utils import (
    Colors, 
    Human, 
    Paginator, 
    Reddit, 
    Urban, 
    crumble,
    TagManager,
    Tag,
    VocabularyPaginator
)
from .tags import get_tag_interactive
from core import (
    BotResponseError, 
    Inu, 
    Table, 
    getLogger,
    get_context,
    InuContext
)

log = getLogger(__name__)

loader = lightbulb.Loader()
bot: Inu

async def tag_name_auto_complete(
    ctx: AutocompleteContext
) -> None:
    """autocomplete for tag keys"""
    await ctx.respond(await TagManager.tag_name_auto_complete(ctx.focused, ctx.interaction)
) 

@loader.command
class VocabularyTraining(
    SlashCommand,
    name="vocabulary",
    description="train vocabulary",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL]
):
    vocabulary_tag = lightbulb.string(
        "vocabulary-tag", 
        "a tag which contains the vocabulary", 
        autocomplete=tag_name_auto_complete
    )

    @invoke
    async def callback(self, _: lightbulb.Context, ctx: InuContext):
        record = await get_tag_interactive(ctx, key=self.vocabulary_tag)
        if not record:
            return await ctx.respond(f"I can't find a tag with the name `{self.vocabulary_tag}` where you are the owner :/")
        tag: Tag = await Tag.from_record(record, ctx.author)
        pag = VocabularyPaginator(tag)
        await pag.start(ctx)

