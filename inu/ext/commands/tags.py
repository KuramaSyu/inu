from ast import Await
import random
import re
import traceback
import typing
from typing import *
import logging
import asyncio
import textwrap

import hikari
from hikari import ComponentInteraction, Embed, InteractionCreateEvent, ResponseType, TextInputStyle
from hikari.impl import ActionRowBuilder
from hikari.messages import ButtonStyle
import lightbulb
from lightbulb import commands
from lightbulb.commands import OptionModifier as OM
from lightbulb.context import Context
import asyncpg
from fuzzywuzzy import fuzz

from core import Inu, Table, BotResponseError
from utils import TagIsTakenError, TagManager, TagType, Human
from utils import crumble
from utils.colors import Colors
from utils import Paginator
from utils.paginators.base import navigation_row
from utils.paginators.tag import TagHandler, Tag

from core import getLogger, BotResponseError

log = getLogger(__name__)



class TagPaginator(Paginator):
    def __init__(self, tag: Tag, **kwargs):
        self.tag = tag
        super().__init__(
            **kwargs,
            timeout=15*60,
        )
    async def post_start(self: Paginator, ctx: Context):
        if self.tag.tag_links:
            asyncio.create_task(show_linked_tag(ctx=ctx, tag=self.tag, message_id=self._message.id))
        await super().post_start(ctx)


async def get_tag_interactive(ctx: Context, key: str = None) -> Optional[Mapping[str, Any]]:
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
            

async def get_tag(ctx: Context, name: str) -> Optional[Mapping[str, Any]]:
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
    record: Mapping[str, Any], 
    ctx: Context, 
    name: Optional[str] = None,
    force_show_name: bool = False,
    tag: Optional[Tag] = None,
) -> None:
    """
    Sends the given tag(record) into the channel of <ctx>.
    If record is None, similar tags will be searched and sent into the channel of <ctx>.
    
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
    if record is None and tag is None:
        return await no_tag_found_msg(ctx, name, ctx.guild_id)
    if not tag:
        tag = await Tag.from_record(record,  db_checks=False)
    media_regex = r"(http(s?):)([/|.|\w|\s|-])*\.(?:jpg|gif|png|mp4|mp3)"
    if record is None:
        await no_tag_found_msg(ctx, ctx.options.name, ctx.guild_id or ctx.channel_id)
        # await ctx.respond(f"I can't find a tag named `{key}` in my storage")
        return
    messages = []

    for value in crumble(tag.value, 1900):
        message = ""
        # if tag isn't just a picture and tag was not invoked with original name,
        # then append original name at start of message
        if (
            not (
                name == tag.name
                or re.match(media_regex, tag.value.strip())
            )
            or force_show_name
        ):
            message += f"**{tag.name}**\n\n"
        message += value
        messages.append(message)
    pag = TagPaginator(
        tag=tag,
        page_s=messages,
        compact=True,
        additional_components=tag.components,
        disable_component=True,
    )
    asyncio.create_task(pag.start(ctx))
        

async def show_linked_tag(ctx: Context, tag: Tag, message_id: int | None = None) -> None:
    """
    Is called when:
    -----------
    When a tag is called and it contains a link to another tag, for every link in this tag,
    this function will be called, to wait for the button interaction and then show the linked tag

    Args
    ----
    ctx : `Context`
        The context of the initial interaction from the user. Will be used to filter out the tag link button interaction
    tag : `Tag`
        The tag, which contains the links to other tags
    message_id : `int` | `None`
        an optional message id, which will be used to filter out the tag link button interaction

    Returns:
    -------
    None
    """
    tag_link, event, interaction = await bot.wait_for_interaction(
        custom_ids=tag.component_custom_ids, 
        user_id =ctx.author.id, 
        channel_id=ctx.channel_id,
        message_id=message_id,
    )
    if tag_link is None:
        # timeout
        return None
    # overriding the interaction with the new interaction
    ctx._interaction = interaction
    ctx._responded = False
    try:
        new_tag = await tag.fetch_tag_from_link(tag_link, current_guild=ctx.guild_id or 0)
    except BotResponseError as e:
        # inform the user about the mistake
        await ctx.respond(**e.kwargs)
        return
    finally:
        # wait for other button reactions
        asyncio.create_task(show_linked_tag(ctx=ctx, tag=tag, message_id=message_id))
    # show selected tag
    asyncio.create_task(show_record({}, ctx, new_tag.name, tag=new_tag))
    

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
bot: Inu

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
@lightbulb.option("name", "the name of your tag", required=False) 
@lightbulb.command("add", "add a new tag")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def add(ctx: Union[lightbulb.SlashContext, lightbulb.PrefixContext]):
    """Add a tag to my storage
    
    Args:
    -----
        - name: the name the tag should have
        NOTE: the key is the first word you type in! Not more and not less!!!
        - value: that what the tag should return when you type in the name. The value is all after the fist word
    """
    interaction = ctx.interaction
    try:
        name = ctx.options.name.strip()
        value = ctx.options.value.strip()
    except:
        answers, interaction, _ = await bot.shortcuts.ask_with_modal(
            "Tag", 
            ["Name:", "Value:"], 
            interaction=ctx.interaction,
            input_style_s=[TextInputStyle.SHORT, TextInputStyle.PARAGRAPH],
            placeholder_s=["The name of your tag", "What you will see, when you do /tag get <name>"]
        )
        name, value = answers
        ctx._interaction = interaction
        name = name.strip()
    try:
        tag = Tag(
            owner=ctx.author,
            channel_id=ctx.guild_id or ctx.channel_id,
        )
        tag.name = name
        tag.value = value
        await tag.save()
    except TagIsTakenError:
        raise BotResponseError("Your tag is already taken", ephemeral=True)
    except RuntimeError as e:
        raise BotResponseError(bot_message=e.args[0], ephemeral=True)
    return await ctx.respond(f"Your tag `{name}` has been added to my storage")



@tag.child
@lightbulb.option(
    "name", 
    "the name of your tag",
    autocomplete=True,
) 
@lightbulb.command("edit", "edit a tag you own")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_edit(ctx: Context):
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


    
@tag.child
@lightbulb.option(
    "name", 
    "the name of your tag",
    autocomplete=True,
) 
@lightbulb.command("remove", "remove a tag you own")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_remove(ctx: Context):
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
        return
    await TagManager.remove(record['tag_id'])
    await ctx.respond(
        f"I removed the {'global' if 0 in record['guild_ids'] else 'local'} tag `{name}`"
    )


@tag.child
@lightbulb.option(
    "name", 
    "the name of your tag", 
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
@lightbulb.option(
    "name", 
    "the name of your tag", 
    modifier=commands.OptionModifier.CONSUME_REST, 
    required=True, 
    autocomplete=True
) 
@lightbulb.command("execute", "executes a tag with Python\nNOTE: owner only", aliases=["run", "exec"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_execute(ctx: Context):
    record = await get_tag(ctx, ctx.options.name)
    if not record:
        raise BotResponseError(bot_message=f"I can't find a tag with called `{ctx.options.name}`")
    ctx._options["code"] = record["tag_value"]  # tag value is a list
    ext = tags.bot.get_plugin("Owner")
    for cmd in ext.all_commands:
        if cmd.name == "run":
            return await cmd.callback(ctx)



@tag.child
@lightbulb.option("text", "the text, you want to append to the current value", modifier=OM.CONSUME_REST)
@lightbulb.option("name", "the name of your tag", 
    autocomplete=True
)  
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
@lightbulb.option(
    "old_name", 
    "The old name from the tag",
    autocomplete=True
) 
@lightbulb.command("change-name", "Change the key (name) of a tag")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_change_name(ctx: Context):
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
@lightbulb.option(
    "name", 
    "the name of your tag", 
    autocomplete=True
)
@lightbulb.command("info", "get info to a tag")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_info(ctx: Context):
    record = await get_tag(ctx, ctx.options.name)
    tag = await Tag.from_record(record, ctx.author, db_checks=False)
    if record is None:
        return await no_tag_found_msg(ctx, ctx.options.name, ctx.guild_id or ctx.channel_id, ctx.author.id)
    message = (
        f"**{record['tag_key']}**\n\n"
        f"tag {Human.plural_('author', len(record['author_ids']))}: "
        f"{Human.list_(record['author_ids'], '', '<@', '>', with_a_or_an=False)}\n"
        f"tag guilds/channels: {Human.list_(record['guild_ids'], with_a_or_an=False)}\n"
        f"tag aliases: {Human.list_(record['aliases'], '`', with_a_or_an=False)}\n"
        f"tag content: ```{Human.short_text(record['tag_value'], 800).replace('`', '')}```\n"
        f"link for this tag: `{tag.link}`"
    )
    await ctx.respond(message)

    

@tag.child
@lightbulb.option("alias", "The optional name you want to add", modifier=OM.CONSUME_REST)
@lightbulb.option(
    "name", 
    "the name of your tag", 
    autocomplete=True
) 
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
@lightbulb.option(
    "name", 
    "the name of your tag", 
    autocomplete=True
) 
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
@lightbulb.option(
    "name", 
    "the name of your tag", 
    autocomplete=True
)  
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
    tag.owners.add(int(ctx.options.author.id))
    await tag.save()
    await ctx.respond(
        f"Added {ctx.options.author.username} as an author of `{tag.name}`"
    )


@tag.child
@lightbulb.option("author", "The @person you want to add as author", type=hikari.User)
@lightbulb.option(
    "name", 
    "the name of your tag", 
    autocomplete=True
) 
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
@lightbulb.option(
    "guild", 
    "The guild/server ID you want to add", 
    autocomplete=True
)
@lightbulb.option(
    "name", 
    "the name of your tag", 
    autocomplete=True
)  
@lightbulb.command("add-guild", "add a guild to your tag")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_add_guild(ctx: Context):
    """Remove a tag to my storage
    
    Args:
    -----
        - key: the name of the tag which you want to remove
    """
    guild_id = guild_autocomplete_get_id(value=ctx.options.guild)
    record = await get_tag_interactive(ctx)
    if not record:
        return await ctx.respond(f"I can't find a tag with the name `{ctx.options.name}` where you are the owner :/")
    tag: Tag = await Tag.from_record(record, ctx.author)
    tag.guild_ids.add(guild_id)
    await tag.save()
    await ctx.respond(
        f"You will now be able to see `{tag.name}` in the guild `{ctx.options.guild}`"
    )

@tag.child
@lightbulb.option(
    "guild", 
    "The guild/server ID you want to add", 
    autocomplete=True
)
@lightbulb.option(
    "name", 
    "the name of your tag", 
    autocomplete=True
) 
@lightbulb.command("remove-guild", "remove a guild/server to your tag", aliases=["rm-guild"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_remove_guild(ctx: Context):
    """Remove a tag to my storage
    
    Args:
    -----
        - key: the name of the tag which you want to remove
    """
    guild_id = guild_autocomplete_get_id(value=ctx.options.guild)
    record = await get_tag_interactive(ctx)
    if not record:
        return await ctx.respond(f"I can't find a tag with the name `{ctx.options.name}` where you are the owner :/")
    tag: Tag = await Tag.from_record(record, ctx.author)
    try:
        tag.guild_ids.remove(guild_id)
    except KeyError:
        return await ctx.respond(
            f"Your tag was never actually available in `{ctx.options.guild}`"
        )
    await tag.save()
    await ctx.respond(
        f"You won't see `{tag.name}` in the guild `{ctx.options.guild}` anymore"
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


@tag_remove.autocomplete("name")
@tag_change_name.autocomplete("old_name")
@tag_append.autocomplete("name")
@tag_info.autocomplete("name")
@tag_edit.autocomplete("name")
@tag_remove_alias.autocomplete("name")
@tag_add_alias.autocomplete("name")
@tag_remove_guild.autocomplete("name")
@tag_remove_author.autocomplete("name")
@tag_add_author.autocomplete("name")
@tag_add_guild.autocomplete("name")
@tag_remove.autocomplete("name")
@tag_get.autocomplete("name")
async def tag_name_auto_complete(
    option: hikari.AutocompleteInteractionOption, 
    interaction: hikari.AutocompleteInteraction
) -> List[str]:
    guild_or_channel = interaction.guild_id or interaction.channel_id
    try:
        if option.value and len(str(option.value)) > 2:
            tags = await TagManager.find_similar(option.value, guild_id=guild_or_channel)
            return [tag['tag_key'] for tag in tags][:24]
        elif option.value and len(str(option.value)) in [1, 2]:
            tags = await TagManager.startswith(option.value, guild_id=guild_or_channel)
            return [
                name for name in 
                [
                    *[name for tag in tags for name in tag["aliases"]], 
                    *[tag['tag_key'] for tag in tags]
                ] 
                if name.startswith(option.value) ][:24]
        else:
            tags = await TagManager.get_tags(
                type=TagType.SCOPE,
                guild_id=guild_or_channel,
            )
            return [tag["tag_key"] for tag in tags][:24]

    except:
        log.error(traceback.format_exc())
        return []


@tag_remove_guild.autocomplete("guild")
@tag_add_guild.autocomplete("guild")
async def guild_auto_complete(
    option: hikari.AutocompleteInteractionOption,
    interaction: hikari.AutocompleteInteraction
) -> List[str]:
    value = option.value or ""
    value = str(value)
    guilds: List[Dict[str, str | int]] = [{'id': 000000000000000000, 'name': "Global - Everywhere where I am"}]
    for gid, name in bot.cache.get_available_guilds_view().items():
        # if value.lower() in str(name).lower():
        guilds.append({'id': gid, 'name': str(name)})
    if len(guilds) >= 1000:
        log.warning("Too many guilds to autocomplete - optimising guild list fast..")
        guilds = [guild for guild in guilds if value.lower() in guild["name"].lower()]

    if len(guilds) > 25:
        if len(value) <= 2:
            guilds = guilds[:24]
    if len(value) > 2:
        guilds_sorted: List[Dict[str, Union[int, str]]] = []
        for guild in guilds:
            guild["ratio"] = fuzz.ratio(value, guild["name"])
            guilds_sorted.append(guild)
        guilds_sorted.sort(key=lambda x: x["ratio"], reverse=True)
        guilds = guilds_sorted[:24]
    
    return [f"{guild['id']} | {guild['name']}" for guild in guilds]

def guild_autocomplete_get_id(value: str) -> int :
    return int(value[:value.find("|")])

def load(inu: Inu):
    inu.add_plugin(tags)
    global bot
    bot = inu
