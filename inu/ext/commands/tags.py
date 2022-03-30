import random
import re
import traceback
import typing
from typing import (
    Dict,
    Mapping,
    Optional,
    List,
    Tuple,
    Union,
    Any

)
import logging
from logging import DEBUG
import asyncio
import textwrap

import hikari
from hikari import ComponentInteraction, Embed, InteractionCreateEvent, ResponseType
from hikari.impl import ActionRowBuilder
from hikari.messages import ButtonStyle
import lightbulb
from lightbulb import commands
from lightbulb.commands import OptionModifier as OM
from lightbulb.context import Context
import asyncpg

from core import Inu, Table
from core.bot import BotResponseError
from utils import TagIsTakenError, TagManager, TagType, Human
from utils import crumble
from utils.colors import Colors
from utils import Paginator
from utils.paginators.base import navigation_row
from utils.paginators.tag import TagHandler, Tag

from core import getLogger

log = getLogger(__name__)


async def get_tag_interactive(ctx: Context, key: str = None) -> Optional[asyncpg.Record]:
    """
    Get the tag interactive
    Note:
    -----
        - if there are multiple tags with same name, the user will be asked, which one to use
    """

    if key is None:
        key = ctx.options.name
    key = key.strip()
    raw_results: List[Mapping[str, Any]] = await TagManager.get(key, ctx.guild_id or ctx.channel_id)
    results = []
    for result in raw_results:
        if ctx.author.id in result["author_ids"]:
            results.append(result)
    # case 0: no entry in database
    # case 1: 1 entry in db; check if global or in guild
    # case _: let user select if he wants the global or local one
    if len(results) == 0:
        return None
    elif len(results) == 1:
        return results[0]
    else:
        #  select between global and local - needs to lookup the results if there are tags of author
        records = {}
        for record in results:
            if 0 in record["guild_ids"]:
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
            await ctx.respond("There are multiple tags with this name. Which one do you want?", component=menu)
            event = await tags.bot.wait_for(
                InteractionCreateEvent,
                30,
            )
            if not isinstance(event.interaction, ComponentInteraction):
                return None
            await event.interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
            return records[event.interaction.values[0]]
        except asyncio.TimeoutError:
            return None
            

async def get_tag(ctx: Context, name: str) -> Optional[Dict[str, Any]]:
    """
    Searches the <key> and sends the result into the channel of <ctx>
    NOTE:
    -----
        - tags created in your guild will be prefered sent, in case there is a global tag too
    """
    ctx.raw_options["name"] = ctx.options.name.strip()
    records = await TagManager.get(name, ctx.guild_id or ctx.channel_id)
    record: Optional[Mapping[str, Any]] = None
    # if records are > 1 return the local overridden one
    if len(records) >= 1:
        typing.cast(int, ctx.guild_id)
        for r in records:
            if (ctx.guild_id or ctx.channel_id) in r["guild_ids"]:
                record = r
                break
            elif 0 in r["guild_ids"]:
                record = r
    return record


async def show_record(
    record: asyncpg.Record, 
    ctx: Context, 
    name: Optional[str] = None,
    force_show_name: bool = False,
) -> None:
    """
    Sends the given tag(record) into the channel of <ctx>
    
    Args:
    ----
    record : `asyncpg.Record`
        the record/dict, which should contain the keys `tag_value` and `tag_key`
    ctx : `Context`
        the context, under wich the message will be sent (important for the channel)
    key : `str`
        The key under which the tag was invoked. If key is an alias, the tag key will be
        displayed, otherwise it wont
    """
    media_regex = r"(http(s?):)([/|.|\w|\s|-])*\.(?:jpg|gif|png|mp4|mp3)"
    if record is None:
        await no_tag_found_msg(ctx, ctx.options.name, ctx.guild_id or ctx.channel_id)
        # await ctx.respond(f"I can't find a tag named `{key}` in my storage")
        return
    messages = []
    message = ""
    for value in crumble(record["tag_value"], 1900):
        # if tag isn't just a picture and tag was not invoked with original name,
        # then append original name at start of message
        if (
            not (
                name == record["tag_key"]
                or re.match(media_regex, record["tag_value"].strip())
            )
            or force_show_name
        ):
            message += f"**{record['tag_key']}**\n\n"
        message += value
        messages.append(message)
    pag = Paginator(messages)
    await pag.start(ctx)


def records_to_embed(
    records: List[asyncpg.Record], 
    value_length: int = 80, 
    tags_per_page: int = 15
) -> List[hikari.Embed]:
    desc = ""
    embeds = [hikari.Embed(title="tag_overview")]
    for i, record in enumerate(records):
        embeds[-1].add_field(record["tag_key"], f'```{textwrap.shorten(record["tag_value"].replace("```", ""), value_length)}```', inline=False)
        #embeds[-1].add_field(record["tag_key"][:255], f'{record["tag_value"][0][:1000]} {"..." if len(record["tag_value"][0]) > 999 else ""}', inline=False)
        if i % tags_per_page == 0 and len(records) > i+1 and i != 0:
            embeds.append(hikari.Embed(title="tag_overview"))
    return embeds


async def no_tag_found_msg(
    ctx: Context,
    tag_name: str, 
    guild_id: Optional[int], 
    creator_id: Optional[int] = None
):
    """Sends similar tags, if there are some, otherwise a inform message, that there is no tag like that"""
    similar_records = await TagManager.find_similar(tag_name, guild_id, creator_id)
    if not similar_records:
        await ctx.respond(f"I can't find a tag or similar ones with the name `{tag_name}`")
    else:
        answer = (
            f"can't find a tag with name `{tag_name}`\n"
            f"Maybe it's one of these?\n"
        )
        answer += "\n".join(f"`{sim['tag_key']}`" for sim in similar_records)
        await ctx.respond(answer)


tags = lightbulb.Plugin("Tags", "Commands all arround tags")

@tags.listener(hikari.ShardReadyEvent)
async def on_ready(_):
    pass

@tags.command
@lightbulb.option("name", "the name of the tag you want to get", modifier=commands.OptionModifier.CONSUME_REST, default=None) 
@lightbulb.command("tag", "get a stored tag")
@lightbulb.implements(commands.PrefixCommandGroup, commands.SlashCommandGroup) 
async def tag(ctx: Context):
    """
    Get the tag by `name`
    Args:
    ----

    key: the name of the tag
    if `key` isn't provided I'll start an interactive tag creation menu
    """
    try:
        ctx.raw_options["name"] = ctx.options.name.strip()
    except:
        pass
    name = ctx.options.name
    if name is None:
        taghandler = TagHandler()
        return await taghandler.start(ctx)
    record = await get_tag(ctx, name)
    await show_record(record, ctx, name)




@tag.child
@lightbulb.option(
    "value", 
    "the value (text) your tag should return",
     modifier=commands.OptionModifier.CONSUME_REST,
     required=False
)
@lightbulb.option("name", "the name of your tag. Only one word", required=False) 
@lightbulb.command("add", "add a new tag")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def add(ctx: Context):
    """Add a tag to my storage
    
    Args:
    -----
        - name: the name the tag should have
        NOTE: the key is the first word you type in! Not more and not less!!!
        - value: that what the tag should return when you type in the name. The value is all after the fist word
    """
    ctx.raw_options["name"] = ctx.options.name.strip()
    if ctx.options.value is None or ctx.options.name is None:
        taghandler = TagHandler()
        return await taghandler.start(ctx)
    typing.cast(str, ctx.options.value)
    try:
        await TagManager.set(
            ctx.options.name, 
            ctx.options.value, 
            [ctx.member or ctx.author],
            [ctx.guild_id or ctx.channel_id],
            [],
        )
    except TagIsTakenError:
        return await ctx.respond("Your tag is already taken")
    return await ctx.respond(f"Your tag `{ctx.options.name}` has been added to my storage")

@tag.child
@lightbulb.option("name", "the name of your tag. Only one word") 
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
    ctx.raw_options["name"] = ctx.options.name.strip()
    record = await get_tag_interactive(ctx)
    if not record:
        return await ctx.respond(f"I can't find a tag with the name `{ctx.options.name}` where you are the owner :/")
    taghandler = TagHandler()
    await taghandler.start(ctx, record)






    # selection menu here
        
    
@tag.child
@lightbulb.option("name", "the name of your tag. Only one word") 
@lightbulb.command("remove", "remove a tag you own")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def remove(ctx: Context):
    """Remove a tag to my storage
    
    Args:
    -----
        - key: the name of the tag which you want to remove
    """
    ctx.raw_options["name"] = ctx.options.name.strip()
    name = ctx.options.name
    record = await get_tag_interactive(ctx)
    if not record:
        await ctx.respond(f"I can't find a tag with the name `{ctx.options.name}` where you are the owner :/")
    await TagManager.remove(record['tag_id'])
    await ctx.respond(
        f"I removed the {'global' if 0 in record['guild_ids'] else 'local'} tag `{name}`"
    )


@tag.child
@lightbulb.option(
    "name", 
    "the name of your tag. Only one word", 
    modifier=commands.OptionModifier.CONSUME_REST, 
    required=True, 
    autocomplete=True
) 
@lightbulb.command("get", "get a tag by key|name",)
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_get(ctx: Context):
    """get a tag to my storage
    
    Args:
    -----
        - name: the name the tag should have
    """
    record = await get_tag(ctx, ctx.options.name)
    await show_record(record, ctx, ctx.options.name)



@tag_get.autocomplete("name")
async def tag_name_auto_complete(
    option: hikari.AutocompleteInteractionOption, interaction: hikari.AutocompleteInteraction
) -> List[str]:
    try:
        if len(option.value) > 2:
            tags = await TagManager.find_similar(option.value, guild_id=interaction.guild_id)
            return [tag['tag_key'] for tag in tags]
        else:
            tags = await TagManager.startswith(option.value, guild_id=interaction.guild_id)
            return [
                name for name in 
                [
                    *[name for tag in tags for name in tag["aliases"]], 
                    *[tag['tag_key'] for tag in tags]
                ] 
                if name.startswith(option.value) ]

    except:
        log.error(traceback.format_exc())
    
    
@tag.child
@lightbulb.command("overview", "get an overview of all tags", aliases=["ov"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def overview(ctx: Context):
    """get an overview of all tags

    """
    menu = (
        ActionRowBuilder()
        .add_select_menu("overview_menu")
        .add_option("all tags you can use", "all")
        .add_to_menu()
        .add_option("guild tags", "guild")
        .add_to_menu()
        .add_option("your tags", "your")
        .add_to_menu()
        .add_option("global tags (all guilds)", "global")
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
        "all": TagType.SCOPE,
        "global": TagType.GLOBAL,
        "your": TagType.YOUR,
    }.get(result)
    if type_ is None:
        raise RuntimeError("Can't get Tags, when TagType is None")
    records = await TagManager.get_tags(type_, guild_id=ctx.guild_id or ctx.channel_id, author_id=ctx.author.id)
    if records is None:
        return
    embeds = records_to_embed(records)
    await event.interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
    pag = Paginator(page_s=embeds, timeout=10*60)
    await pag.start(ctx)

@tag.child
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.option("name", "the name of your tag. Only one word", modifier=commands.OptionModifier.CONSUME_REST, required=True) 
@lightbulb.command("execute", "executes a tag with Python\nNOTE: owner only", aliases=["run", "exec"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_execute(ctx: Context):
    record = await get_tag(ctx, ctx.options.name)
    ctx._options["code"] = record["tag_value"]  # tag value is a list
    ext = tags.bot.get_plugin("Owner")
    for cmd in ext.all_commands:
        if cmd.name == "run":
            return await cmd.callback(ctx)

@tag.child
@lightbulb.option("text", "the text, you want to append to the current value", modifier=OM.CONSUME_REST)
@lightbulb.option("name", "the name of your tag. Only one word") 
@lightbulb.command("append", "remove a tag you own")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_append(ctx: Context):
    """Remove a tag to my storage
    
    Args:
    -----
        - key: the name of the tag which you want to remove
    """
    ctx.raw_options["name"] = ctx.options.name.strip()
    key = ctx.options.name
    record = await get_tag_interactive(ctx)
    if not record:
        return await ctx.respond(f"I can't find a tag with the name `{ctx.options.name}` where you are the owner :/")
    tag: Tag = await Tag.from_record(record, ctx.author)
    tag.value += f"\n{ctx.options.text.lstrip()}"
    await tag.save()
    await ctx.respond(
        f"Done."
    )

@tag.child
@lightbulb.option("new_name", "The new name for the tag", modifier=OM.CONSUME_REST)
@lightbulb.option("old_name", "The old name from the tag") 
@lightbulb.command("change-name", "Change the key (name) of a tag")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_change_key(ctx: Context):
    """Remove a tag to my storage
    
    Args:
    -----
        - key: the name of the tag which you want to remove
    """
    old_key = ctx.options.old_name
    record = await get_tag_interactive(ctx, old_key)
    if not record:
        return await ctx.respond(f"I can't find a tag with the name `{old_key}` where you are the owner :/")
    tag: Tag = await Tag.from_record(record, ctx.author)
    tag.name = ctx.options.new_name
    await tag.save()
    await ctx.respond(
        f"Done."
    )

@tag.child
@lightbulb.option("name", "the name of your tag. Only one word", type=str)
@lightbulb.command("info", "get info to a tag")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_info(ctx: Context):
    record = await get_tag(ctx, ctx.options.name)
    if record is None:
        return await no_tag_found_msg(ctx, ctx.options.name, ctx.guild_id or ctx.channel_id, ctx.author.id)
    message = (
        f"**{record['tag_key']}**\n\n"
        f"tag {Human.plural_('author', len(record['author_ids']))}: "
        f"{Human.list_(record['author_ids'], '', '<@', '>', with_a_or_an=False)}\n"
        f"tag guilds/channels: {Human.list_(record['guild_ids'], with_a_or_an=False)}\n"
        f"tag aliases: {Human.list_(record['aliases'], '`', with_a_or_an=False)}\n"
        f"tag content: ```{Human.short_text(record['tag_value'], 800).replace('`', '')}```"
    )
    await ctx.respond(message)

    

@tag.child
@lightbulb.option("alias", "The optional name you want to add", modifier=OM.CONSUME_REST)
@lightbulb.option("name", "the name of your tag. Only one word") 
@lightbulb.command("add-alias", "remove a tag you own")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_add_alias(ctx: Context):
    """Remove a tag to my storage
    
    Args:
    -----
        - key: the name of the tag which you want to remove
    """
    record = await get_tag_interactive(ctx)
    if not record:
        return await ctx.respond(f"I can't find a tag with the name `{ctx.options.name}` where you are the owner :/")
    tag: Tag = await Tag.from_record(record, ctx.author)
    tag.aliases.append(f"{ctx.options.alias.strip()}")
    await tag.save()
    await ctx.respond(
        f"Added `{ctx.options.alias.strip()}` to optional names of `{tag.name}`"
    )

@tag.child
@lightbulb.option("alias", "The optional name you want to remove", modifier=OM.CONSUME_REST)
@lightbulb.option("name", "the name of your tag. Only one word") 
@lightbulb.command("remove-alias", "remove a tag you own", aliases=["rm-alias"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_remove_alias(ctx: Context):
    """Remove a tag to my storage
    
    Args:
    -----
        - key: the name of the tag which you want to remove
    """
    record = await get_tag_interactive(ctx)
    if not record:
        return await ctx.respond(f"I can't find a tag with the name `{ctx.options.name}` where you are the owner :/")
    tag: Tag = await Tag.from_record(record, ctx.author)
    try:
        tag.aliases.append(f"{ctx.options.alias.strip()}")
    except ValueError:
        return await ctx.respond(f"This tag don't have an ailias called `{ctx.options.alias.strip()}` which I could remove")
    await tag.save()
    await ctx.respond(
        f"Added `{ctx.options.alias.strip()}` to optional names of `{tag.name}`"
    )

@tag.child
@lightbulb.option("author", "The @person you want to add as author", type=hikari.User)
@lightbulb.option("name", "the name of your tag. Only one word") 
@lightbulb.command("add-author", "add an author to your tag")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_add_author(ctx: Context):
    """Remove a tag to my storage
    
    Args:
    -----
        - key: the name of the tag which you want to remove
    """
    record = await get_tag_interactive(ctx)
    if not record:
        return await ctx.respond(f"I can't find a tag with the name `{ctx.options.name}` where you are the owner :/")
    tag: Tag = await Tag.from_record(record, ctx.author)
    tag.owners.append(int(ctx.options.author.id))
    await tag.save()
    await ctx.respond(
        f"Added {ctx.options.author.username} as an author of `{tag.name}`"
    )

@tag.child
@lightbulb.option("author", "The @person you want to add as author", type=hikari.User)
@lightbulb.option("name", "the name of your tag. Only one word") 
@lightbulb.command("remove-author", "add an author to your tag", aliases=["rm-author"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_remove_author(ctx: Context):
    """Remove a tag to my storage
    
    Args:
    -----
        - key: the name of the tag which you want to remove
    """
    record = await get_tag_interactive(ctx)
    if not record:
        return await ctx.respond(f"I can't find a tag with the name `{ctx.options.name}` where you are the owner :/")
    tag: Tag = await Tag.from_record(record, ctx.author)
    try:
        tag.owners.remove(int(ctx.options.author.id))
    except ValueError:
        return await ctx.respond(f"{ctx.options.author.username} was never an author")
    await tag.save()
    await ctx.respond(
        f"Removed {ctx.options.author.username} from the author of `{tag.name}`"
    )

@tag.child
@lightbulb.option("guild", "The guild/server ID you want to add", type=hikari.Snowflake)
@lightbulb.option("name", "the name of your tag. Only one word") 
@lightbulb.command("add-guild", "add a guild to your tag")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_add_guild(ctx: Context):
    """Remove a tag to my storage
    
    Args:
    -----
        - key: the name of the tag which you want to remove
    """
    record = await get_tag_interactive(ctx)
    if not record:
        return await ctx.respond(f"I can't find a tag with the name `{ctx.options.name}` where you are the owner :/")
    tag: Tag = await Tag.from_record(record, ctx.author)
    tag.guild_ids.append(int(ctx.options.guild))
    await tag.save()
    await ctx.respond(
        f"You will now be able to see `{tag.name}` in the guild with id `{ctx.options.guild}`"
    )

@tag.child
@lightbulb.option("guild", "The guild/server ID you want to add", type=hikari.Snowflake)
@lightbulb.option("name", "the name of your tag. Only one word") 
@lightbulb.command("remove-guild", "remove a guild/server to your tag", aliases=["rm-guild"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_remove_guild(ctx: Context):
    """Remove a tag to my storage
    
    Args:
    -----
        - key: the name of the tag which you want to remove
    """
    record = await get_tag_interactive(ctx)
    if not record:
        return await ctx.respond(f"I can't find a tag with the name `{ctx.options.name}` where you are the owner :/")
    tag: Tag = await Tag.from_record(record, ctx.author)
    try:
        tag.guild_ids.remove(int(ctx.options.guild))
    except ValueError:
        return await ctx.respond(
            f"There was never a guild with id `{ctx.options.guild}` in your tag"
        )
    await tag.save()
    await ctx.respond(
        f"You won't see `{tag.name}` in the guild with id `{ctx.options.guild}` anymore"
    )

@tag.child
@lightbulb.command("random", "Get a random tag from all tags available")
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def tag_random(ctx: Context):
    available_tags = await TagManager.get_tags(
        TagType.SCOPE,
        guild_id=ctx.guild_id,
        author_id=ctx.author.id,
    )
    if not available_tags:
        raise BotResponseError(f"No tags found for the random command")
    random_tag = random.choice(available_tags)
    await show_record(random_tag, ctx, force_show_name=True)


def load(bot: lightbulb.BotApp):
    bot.add_plugin(tags)
