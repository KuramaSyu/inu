import re
import traceback
import typing
from typing import (
    Dict,
    Mapping,
    Optional,
    List,
    Union,
    Any

)
import logging
from logging import DEBUG
import asyncio

import hikari
from hikari import ComponentInteraction, Embed, InteractionCreateEvent, ResponseType
from hikari.impl import ActionRowBuilder
from hikari.messages import ButtonStyle
import lightbulb
from lightbulb import commands
from lightbulb.context import Context
import asyncpg
from matplotlib.style import context

from core import Inu
from utils.tag_mamager import TagIsTakenError, TagManager
from utils import crumble
from utils.colors import Colors
from utils import Paginator
from utils.paginators.common import navigation_row
from utils.paginators import TagHandler

log = logging.getLogger(__name__)
log.setLevel(DEBUG)


tags = lightbulb.Plugin("Tags", "Commands all arround tags")

@tags.listener(hikari.ShardReadyEvent)
async def on_ready(_):
    try:
        TagManager.set_db(tags.bot.db)
        log.info("added database to TagManager")
    except Exception:
        log.critical(f"CAN'T ADD DATABASE TO TAGMANAGER: {traceback.format_exc()}")

@tags.command
@lightbulb.option("key", "the name of the tag you want to get", modifier=commands.OptionModifier.CONSUME_REST, default=None) 
@lightbulb.command("tag", "get a stored tag")
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup)
async def tag(ctx: Context):
    """
    Get the tag by `key`
    Args:
    ----

    key: the name of the tag
    if `key` isn't provided I'll start an interactive tag creation menu
    """
    key = ctx.options.key
    if key is None:
        taghandler = TagHandler()
        return await taghandler.start(ctx)
    await get_tag(ctx, key)

async def get_tag(ctx: Context, key: str):
    """
    Searches the <key> and sends the result into the channel of <ctx>
    """
    records = await TagManager.get(key, ctx.guild_id or 0)
    record: Optional[Mapping[str, Any]] = None
    # if records are > 1 return the local overridden one
    if len(records) >= 1:
        typing.cast(int, ctx.guild_id)
        for r in records:
            if r["guild_id"] == ctx.guild_id:
                record = r
                break
            elif r["guild_id"] is None:
                record = r
    if record is None:
        return await ctx.respond(f"I can't found a tag named `{key}` in my storage")
    messages = []
    for value in crumble("\n".join(v for v in record["tag_value"]), 1900):
        message = f"**{key}**\n\n{value}\n\n`created by {tags.bot.cache.get_user(record['creator_id']).username}`"
        messages.append(message)
    pag = Paginator(messages)
    await pag.start(ctx)

@tag.child
@lightbulb.option(
    "value", 
    "the value (text) your tag should return",
     modifier=commands.OptionModifier.CONSUME_REST,
     required=False
)
@lightbulb.option("key", "the name of your tag. Only one word", required=False) 
@lightbulb.command("add", "add a new tag")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def add(ctx: Context):
    """Add a tag to my storage
    
    Args:
    -----
        - key: the name the tag should have
        NOTE: the key is the first word you type in! Not more and not less!!!
        - value: that what the tag should return when you type in the name. The value is all after the fist word
    """
    if ctx.options.value is None or ctx.options.key is None:
        taghandler = TagHandler()
        return await taghandler.start(ctx)
    typing.cast(str, ctx.options.value)
    try:
        await TagManager.set(ctx.options.key, ctx.options.value, ctx.member or ctx.author)
    except TagIsTakenError:
        return await ctx.respond("Your tag is already taken")
    return await ctx.respond(f"Your tag `{ctx.options.key}` has been added to my storage")

@tag.child
@lightbulb.option("key", "the name of your tag. Only one word") 
@lightbulb.command("edit", "edit a tag you own")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def edit(ctx: Context):
    """Add a tag to my storage
    
    Args:
    -----
        - key: the name the tag should have
        NOTE: the key is the first word you type in! Not more and not less!!!
        - value: that what the tag should return when you type in the name. The value is all after the fist word
    """

    raw_results: List[Mapping[str, Any]] = await TagManager.get(ctx.options.key, ctx.guild_id)
    results = []
    for result in raw_results:
        if result["creator_id"] == ctx.author.id:
            results.append(result)
    # case 0: no entry in database
    # case 1: 1 entry in db; check if global or in guild
    # case _: let user select if he wants the global or local one
    if len(results) == 0:
        return await ctx.respond(f"I can't find a tag with the name `{ctx.options.key}` where you are the owner :/")
    elif len(results) == 1:
        taghandler = TagHandler()
        return await taghandler.start(ctx, results[0])
    else:
        #  select between global and local - needs to lookup the results if there are tags of author
        records = {}
        for record in results:
            if record["guild_id"] == ctx.guild_id and record["guild_id"] is None:
                records["global"] = record
            else:
                records["local"] = record
        menu = (
            ActionRowBuilder()
            .add_select_menu("menu")
            .add_option(f"{ctx.options.key} - global / everywhere", "global")
            .add_to_menu()
            .add_option(f"{ctx.options.key} - local / guild only", "local")
            .add_to_menu()
            .add_to_container()
        )
        try:
            await ctx.respond("Do you want to edit your local or global tag?", component=menu)
            event = await tags.bot.wait_for(
                InteractionCreateEvent,
                30,
            )
            if not isinstance(event.interaction, ComponentInteraction):
                return
            await event.interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
            taghandler = TagHandler()
            await taghandler.start(ctx, records[event.interaction.values[0]])

        except asyncio.TimeoutError:
            pass
    # selection menu here
        
    
@tag.child
@lightbulb.option("key", "the name of your tag. Only one word") 
@lightbulb.command("remove", "remove a tag you own")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def remove(ctx: Context):
    """Remove a tag to my storage
    
    Args:
    -----
        - key: the name of the tag which you want to remove
    """
    key = ctx.options.key
    raw_results: List[Mapping[str, Any]] = await TagManager.get(key, ctx.guild_id)
    results = []
    for result in raw_results:
        if result["creator_id"] == ctx.author.id:
            results.append(result)
    # case 0: no entry in database
    # case 1: 1 entry in db; check if global or in guild
    # case _: let user select if he wants the global or local one
    if len(results) == 0:
        return await ctx.respond(f"I can't find a tag with the name `{key}` where you are the owner :/")
    elif len(results) == 1:
        tag = results[0]
        await TagManager.remove(tag["tag_id"])
        return await ctx.respond(f"I removed the {'local' if tag['guild_id'] else 'global'} tag `{tag['tag_key']}`")
    else:
        #  select between global and local - needs to lookup the results if there are tags of author
        records = {}
        for record in results:
            if record["guild_id"] == ctx.guild_id and record["guild_id"] is None:
                records["global"] = record
            else:
                records["local"] = record
        menu = (
            ActionRowBuilder()
            .add_select_menu("menu")
            .add_option(f"{key} - global / everywhere", "global")
            .add_to_menu()
            .add_option(f"{key} - local / guild only", "local")
            .add_to_menu()
            .add_to_container()
        )
        try:
            await ctx.respond("Do you want to edit your local or global tag?", component=menu)
            event = await tags.bot.wait_for(
                InteractionCreateEvent,
                30,
            )
            if not isinstance(event.interaction, ComponentInteraction):
                return
            await TagManager.remove(records[event.interaction.values[0]]['tag_id'])
            await event.interaction.create_initial_response(
                ResponseType.MESSAGE_CREATE,
                f"I removed the {event.interaction.values[0]} tag `{key}`"
            )

        except asyncio.TimeoutError:
            pass

@tag.child
@lightbulb.option("key", "the name of your tag. Only one word", modifier=commands.OptionModifier.CONSUME_REST, required=True) 
@lightbulb.command("get", "get a tag by key|name")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def get(ctx: Context):
    """get a tag to my storage
    
    Args:
    -----
        - key: the name the tag should have
    """
    await get_tag(ctx, ctx.options.key)

def load(bot: lightbulb.BotApp):
    bot.add_plugin(tags)
