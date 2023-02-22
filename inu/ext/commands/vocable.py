import asyncio
import logging
import typing
from datetime import datetime
from typing import *
from numpy import full, isin

import aiohttp
import hikari
from hikari import TextInputComponent, ButtonStyle
import lightbulb
from lightbulb import commands

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
    get_context
)

log = getLogger(__name__)

plugin = lightbulb.Plugin("Name", "Description")
bot: Inu

@plugin.command
@lightbulb.option("vocabulary-tag", "a tag which contains the vocabulary", autocomplete=True)
@lightbulb.command("vocabulary", "train vocabulary")
@lightbulb.implements(commands.SlashCommand)
async def vocabulary_training(ctx: lightbulb.Context):
    ctx.raw_options["name"] = ctx.options["vocabulary-tag"]
    record = await get_tag_interactive(ctx)
    if not record:
        return await ctx.respond(f"I can't find a tag with the name `{ctx.options.name}` where you are the owner :/")
    tag: Tag = await Tag.from_record(record, ctx.author)
    pag = VocabularyPaginator(tag)
    ictx = get_context(ctx.event)
    ictx._responded = ctx._responded
    await pag.start(ctx)
    


@vocabulary_training.autocomplete("vocabulary-tag")
async def tag_name_auto_complete(
    option: hikari.AutocompleteInteractionOption, 
    interaction: hikari.AutocompleteInteraction
) -> List[str]:
    """autocomplete for tag keys"""
    return await TagManager.tag_name_auto_complete(option, interaction)

def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)

