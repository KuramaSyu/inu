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
from numpy import where

from core import Inu
from utils import Table
from utils.tag_mamager import TagIsTakenError, TagManager, TagType
from utils import crumble
from utils.colors import Colors
from utils import Paginator
from utils.paginators.common import navigation_row
from utils.paginators import TagHandler

from core import getLogger

log = getLogger(__name__)


tags = lightbulb.Plugin("Tags", "Commands all arround tags")

@tags.listener(hikari.ShardReadyEvent)
async def on_ready(_):
    pass

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
    record = await get_tag(ctx, key)
    await show_record(record, ctx, key)


async def get_tag(ctx: Context, key: str) -> Optional[asyncpg.Record]:
    """
    Searches the <key> and sends the result into the channel of <ctx>
    NOTE:
    -----
        - tags created in your guild will be prefered sent, in case there is a global tag too
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
    return record

async def show_record(record: asyncpg.Record, ctx: Context, key: str) -> None:
    """Sends the given tag(record) into the channel of <ctx>"""
    if record is None:
        await no_tag_found_msg(ctx, key, ctx.guild_id)
        # await ctx.respond(f"I can't find a tag named `{key}` in my storage")
        return
    messages = []
    for value in crumble("\n".join(v for v in record["tag_value"]), 1900):
        message = f"**{key}**\n\n{value}\n\ncreated by <@{(record['creator_id'])}>"
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
    record = await get_tag(ctx, ctx.options.key)
    await show_record(record, ctx, ctx.options.key)
    
@tag.child
@lightbulb.command("overview", "get an overview of all tags", aliases=["ov"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def overview(ctx: Context):
    """get an overview of all tags

    """
    menu = (
        ActionRowBuilder()
        .add_select_menu("overview_menu")
        .add_option("guild tags", "guild")
        .add_to_menu()
        .add_option("all tags", "global")
        .add_to_menu()
        .add_option("your tags", "your")
        .add_to_menu()
        .add_to_container()
    )
    msg = await ctx.respond("Which overview do you want?", component=menu)
    msg = await msg.message()
    log.debug(msg.id)
    try:
        event = await ctx.bot.wait_for(
            hikari.InteractionCreateEvent,
            60,
            lambda e: isinstance(e.interaction, hikari.ComponentInteraction) and e.interaction.message.id == msg.id
            
        )
    except:
        return
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return

    result = event.interaction.values[0]
    type_ = {
        "guild": TagType.GUILD,
        "global": TagType.GLOBAL,
        "your": TagType.YOUR,
    }.get(result)
    if type_ is None:
        raise RuntimeError("Can't get Tags, when TagType is None")
    records = await TagManager.get_tags(type_, guild_id=ctx.guild_id, author_id=ctx.author.id)
    if records is None:
        return
    embeds = records_to_embed(records)
    await event.interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
    pag = Paginator(page_s=embeds, timeout=10*60)
    await pag.start(ctx)

@tag.child
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.option("key", "the name of your tag. Only one word", modifier=commands.OptionModifier.CONSUME_REST, required=True) 
@lightbulb.command("execute", "executes a tag with Python\nNOTE: owner only", aliases=["run", "exec"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_execute(ctx: Context):
    record = await get_tag(ctx, ctx.options.key)
    ctx._options["code"] = record["tag_value"][0]  # tag value is a list
    ext = tags.bot.get_plugin("Owner")
    for cmd in ext.all_commands:
        if cmd.name == "run":
            return await cmd.callback(ctx)

def records_to_embed(records: List[asyncpg.Record]) -> List[hikari.Embed]:
    desc = ""
    embeds = [hikari.Embed(title="tag_overview")]
    for i, record in enumerate(records):
        embeds[-1].add_field(record["tag_key"][:255], f'{record["tag_value"][0][:1000]} {"..." if len(record["tag_value"][0]) > 999 else ""}', inline=False)
        if i % 10 == 0 and len(records) > i+1 and i != 0:
            embeds.append(hikari.Embed(title="tag_overview"))
    return embeds

async def no_tag_found_msg(
    ctx: Context,
    tag_name: str, 
    guild_id: Optional[int], 
    creator_id: Optional[int] = None
):
    """Sends similar tags, if there are some, otherwise a inform message, that there is no tag like that"""
    similar_records = await find_similar(tag_name, guild_id, creator_id)
    if not similar_records:
        await ctx.respond(f"I can't find a tag or similar ones with the name `{tag_name}`")
    else:
        answer = (
            f"can't find a tag with name `{tag_name}`\n"
            f"Maybe it's one of these?\n"
        )
        answer += "\n".join(f"`{sim['tag_key']}`" for sim in similar_records)
        await ctx.respond(answer)

async def find_similar(
    tag_name: str, 
    guild_id: Optional[int], 
    creator_id: Optional[int] = None
) -> List:
    """
    ### searches similar tags to <`tag_name`>

    Args:
    -----
        - tag_name (`str`) the name of the tag, to search
        - guild_id (`int`) the guild_id, which the returning tags should have
        - creator_id (`int`) the creator_id, which the returning tags should have

    Note:
    -----
        - global tags will shown always (guild_id is None)
    """
    cols = ["guild_id"]
    vals = [guild_id]
    if creator_id:
        cols.append("creator_id")
        vals.append(creator_id)
    table = Table("tags")
    records = await tags.bot.db.fetch(
        f"""
        SELECT *
        FROM tags
        WHERE guild_id=$1 AND tag_key % $2
        ORDER BY similarity(tag_key, $2) > {tags.bot.conf.tags.prediction_accuracy} DESC
        LIMIT 10;
        """,
        guild_id, 
        tag_name

    )
    return records

def load(bot: lightbulb.BotApp):
    bot.add_plugin(tags)
