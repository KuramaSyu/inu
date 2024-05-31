import random
import re
import traceback
import typing
from typing import *
import logging
import asyncio
import textwrap
import json

import hikari
from hikari import ComponentInteraction, Embed, InteractionCreateEvent, ResponseType, TextInputStyle
from hikari.impl import MessageActionRowBuilder
from hikari import ButtonStyle
import lightbulb
from lightbulb import commands
from lightbulb.commands import OptionModifier as OM
from lightbulb.context import Context
import asyncpg
from fuzzywuzzy import fuzz

from core import Inu, Table, BotResponseError
from utils import TagIsTakenError, TagManager, TagScope, Human, get_guild_or_channel_id, guild_name_or_id, TagType
from utils import crumble, ListParser
from utils.colors import Colors
from utils import Paginator, StatelessPaginator
from utils.paginators.base import navigation_row
from utils.paginators.tag import TagHandler, Tag

from core import getLogger, BotResponseError, InteractionContext, get_context, InuContext

log = getLogger(__name__)


tags = lightbulb.Plugin("Tags", "Commands all arround tags")
bot: Inu
EPHEMERAL = {"flags": hikari.MessageFlag.EPHEMERAL}



class CheckForTagType:
    """Checks for a Tag Type and applies it"""
    def __init__(self, tag_value: str):
        self.queue = tag_value

    @property
    def is_media(self) -> bool:
        """Check for Youtube and Soundcloud links"""
        return bool(re.match(r"(https?://)?(www|music)?(\.)?(youtube|soundcloud)\.com", self.queue))
    
    @property
    def is_list(self) -> bool:
        return ListParser.check_if_list(self.queue)
        

    def check(self) -> Optional[TagType]:
        if self.is_media:
            return TagType.MEDIA
        if self.is_list:
            return TagType.LIST
        return None
    
    def _get_question(self) -> str:
        tag_type = self.check()
        if tag_type is None:
            raise RuntimeError("No type found which could match the tag value.")
        if tag_type == TagType.MEDIA:
            return "Your tag contains a Youtube or Soundcloud link. Do you want to use this tag for `/play`?"
        if tag_type == TagType.LIST:
            return "Your tag contains a list. Do you want to use this tag for `/random list`?"
        raise RuntimeError(f"TagType not implemented to ask for: {tag_type}")

    async def ask(self, ctx: InuContext, tag: Tag) -> Optional[InuContext]:
        """
        Ask, if the type should be applied.
        If yes, then type is applied.

        Args:
        -----
        ctx : InuContext
            The context, under which the question will be asked

        Returns:
        --------
        InuContext | None
            The context, if the type should be applied. None, if not.
    
        Raises:
        -------
        TimeoutError:
            If the user doesn't respond in 30 minutes
        """
        question = self._get_question()
        answer, ctx = await ctx.ask(
            title=question, 
            button_labels=["Yes", "No"],
            timeout=30*60
        )
        if ctx is None:
            return None
        if answer == "Yes":
            tag.tag_type = self.check()
            await tag.save()
            return ctx
        return ctx


class TagPaginator(StatelessPaginator):
    def __init__(self, tag: Tag, **kwargs):
        self.tag = tag
        super().__init__(
            **kwargs,
            timeout=15*60,
            additional_components=tag.components,
        )

    def _get_custom_id_kwargs(self) -> Dict[str, int | str]:
        return {"tid": self.tag.id}

    async def _rebuild(self, event: hikari.Event, force_show_name: bool = False, name: str = ""):
        self.set_context(event=event)
        self._build_pages(force_show_name=force_show_name, name=name)

    def _build_pages(self, force_show_name: bool = False, name: str = ""):
        media_regex = r"(http(s?):)([/|.|\w|\s|-])*\.(?:jpg|gif|png|mp4|mp3)"
        messages = []
        add_title = True
        for page in self.tag.value:
            for value in crumble(page, 2000):
                message = ""
                # if tag isn't just a picture and tag was not invoked with original name,
                # AND it's the first page of the tag
                # then append original name at start of message
                if (
                    (not (
                        name == self.tag.name
                        or re.match(media_regex, "\n".join(self.tag.value).strip())
                    )
                    or force_show_name) and add_title
                ):
                    message += f"**{self.tag.name}**\n\n"
                    add_title = False
                message += value
                messages.append(message)
        self.set_pages(messages)

    async def start(self, ctx: Context, force_show_name: bool = False, name: str = ""):
        self._build_pages(force_show_name=force_show_name, name=name)
        await super().start(ctx)

    @property
    def custom_id_type(self) -> str:
        return "stl-tag"  # stateless tag paginator



@tags.listener(event=hikari.InteractionCreateEvent)
async def on_tag_paginator_interaction(event: hikari.InteractionCreateEvent):
    """
    Handler for all tag paginator related interactions
    """
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    tag_id: Optional[int] = None
    try:
        custom_id = json.loads(event.interaction.custom_id)
        if not custom_id["t"] == "stl-tag": return
        if not (tag_id := custom_id.get("tid")) is not None: return
    except:
        return
    
    tag = await Tag.from_id(
        tag_id, 
        user_id=event.interaction.user.id, 
        guild_or_channel_id=get_guild_or_channel_id(event.interaction)
    )
    if tag is None:
        return await no_tag_found_msg(
            ctx=get_context(event),
            tag_name=f"id: {tag_id}",
            guild_id=get_guild_or_channel_id(event.interaction),
        )
    pag = TagPaginator(tag).set_custom_id(event.interaction.custom_id)
    await pag.rebuild(
        event=event,
    )



async def get_tag_interactive(ctx: Context, key: str = None) -> Optional[Mapping[str, Any]]:
    """
    Get the tag interactive via message menues and interactions


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
            
    if len(results) == 0:
        # no entry in database
        await ctx.respond(f"I can't find a tag named `{key}` where you are the owner :/", **EPHEMERAL)
        return None
    elif len(results) == 1:
        # 1 entry in db; check if global or in guild
        return results[0]
    else:
        # let user select if he wants the global or local one
        #  select between global and local - needs to lookup the results if there are tags of author
        records = {}
        for record in results:
            if 0 in record["guild_ids"]:
                records["global"] = record
            else:
                records["local"] = record
        menu = (
            MessageActionRowBuilder()
            .add_text_menu("menu")
            .add_option(f"{key} - global / everywhere", "global")
            .add_option(f"{key} - local / guild only", "local")
            .parent
        )
        try:
            await ctx.respond("There are multiple tags with this name. Which one do you want?", component=menu, **EPHEMERAL)
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
    event: hikari.Event | None = None,
) -> None:
    """
    Sends the given tag(record) into the channel of <ctx>.
    If record is None, similar tags will be searched and sent into the channel of <ctx>.
    
    Args:
    ----
    record : `asyncpg.Record`
        - the record/dict, which should contain the keys `tag_value` and `tag_key`
        - needed, if `<tag>` is not given

    ctx : `Context`
        the context, under wich the message will be sent (important for the channel)
    name : Optional[str]
        - the name of the tag
        - used to distingluish if called with alias or real name

    force_show_name : bool = False
        wether or not the tag name will be in the embed. Default is, that name is removed, if tag is some sort of media like png

    tag : Optional[Tag] = None
        Tag object, if it was already fetched. Dict is not needed in this case

    event : Optional[hikari.Event] = None
        The event which will be fired in the StatelessTagPaginator. Default is None, to create the Paginator


    Raises:
    -------
    BotResponseError:
        when the tag creation raises an RuntimeError
    """
    if record is None and tag is None:
        return await no_tag_found_msg(ctx, name, ctx.guild_id)
    if not tag:
        try:
            tag = await Tag.from_record(record,  db_checks=False)
        except RuntimeError as e:
            raise BotResponseError(e.args[0], ephemeral=True)
    if not ctx:
        ctx = get_context(event)
    pag = TagPaginator(
        tag=tag
    )
    await tag.used_now()
    await pag.start(ctx, force_show_name=force_show_name, name=name)
        
    

def records_to_embed(
    records: List[asyncpg.Record], 
    value_length: int = 80, 
    tags_per_page: int = 15
) -> List[hikari.Embed]:
    embeds = [hikari.Embed(title="tag_overview")]
    for i, record in enumerate(records):
        embeds[-1].add_field(record["tag_key"], f'```{textwrap.shorten(", ".join(record["tag_value"]).replace("```", ""), value_length)}```', inline=False)
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



@tags.listener(hikari.InteractionCreateEvent)
async def on_tag_link_interaction(event: hikari.InteractionCreateEvent):
    """
    Handler for Button/Menu Interactions with tag links
    """
    # menus dont work
    i = event.interaction
    log = getLogger(__name__, "tag link interaction")
    if not isinstance(i, hikari.ComponentInteraction):
        return
    ctx = InteractionContext(event, app=bot)
    try:
        if not (
            ctx.custom_id.startswith("tag://")  # button
            or (ctx.custom_id == "tag-link-menu" and ctx.values[0].startswith("tag://"))  # menu
        ):
            return
    except IndexError:
        return
    try:
        tag_link = ctx.custom_id if ctx.custom_id.startswith("tag://") else ctx.values[0]
        tag = await Tag.fetch_tag_from_link(link=tag_link, current_guild=ctx.guild_id or ctx.channel_id)
    except BotResponseError as e:
        # inform the user about the mistake
        await ctx.respond(**e.kwargs)
        return
    await show_record(tag=tag, record={}, ctx=ctx)



@tags.listener(hikari.InteractionCreateEvent)
async def on_tag_edit_interaction(event: hikari.InteractionCreateEvent):
    """Handler for Tag edit one time paginator"""
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    pag = TagHandler().set_custom_id(event.interaction.custom_id)
    try:
        if not pag.custom_id.type == "stl-tag-edit": return
    except:
        return
    tag: Tag | None = await Tag.from_id(
        pag.custom_id._kwargs["tid"], 
        user_id=event.interaction.user.id, 
        guild_or_channel_id=event.interaction.guild_id
    )
    ctx = get_context(event)
    if not tag:
        return await ctx.respond("Seems like this tag doesn't exist anymore", ephemeral=True)
    if not tag.is_authorized_to_write(ctx.author.id):   
        # ask owner if asked user should get the permission  
        answ, ctx = await ctx.ask(
            "You've no permission to edit this tag. Should I ask the owner to grant you the permission?",
            button_labels=["Yes", "No"],
            ephemeral=True,
            timeout=60*10,
        )
        if ctx is None:
            return
        asked_user = ctx.author
        if answ == "No":
            await ctx.respond("Okay :)", ephemeral=True)
            return
        answ, ctx = await ctx.ask(
            f"{Human.list_([f'<@{owner}>' for owner in tag.owners], with_a_or_an=False)}, should I grant {asked_user.mention} the permission to edit this tag?",
            button_labels=["Yes", "No"],
            timeout=60*10,
            ephemeral=False,
            allowed_users=tag.owners
        )
        if ctx is None:
            return
        if answ == "No":
            await ctx.respond("Okay :)", ephemeral=True)
        else:
            tag.owners.add(asked_user.id)
            await tag.save()
            await ctx.respond(f"{asked_user.mention} you got the permission to edit this tag now")
        return
        #await ctx.respond("REJECTED - Not your navigator. Did you thought you can trick me? ", ephemeral=True)
        return
    
    await tag.used_now()
    pag.set_tag(tag)
    await pag.rebuild(event)



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
async def _tag_add(ctx: Union[lightbulb.SlashContext, lightbulb.PrefixContext]):
    """Add a tag to my storage
    
    Args:
    -----
        - name: the name the tag should have
        NOTE: the key is the first word you type in! Not more and not less!!!
        - value: that what the tag should return when you type in the name. The value is all after the fist word
    """
    await _tag_add(get_context(ctx.event, options=ctx.raw_options))
    
    
async def _tag_add(ctx: InuContext, tag_type: Optional[TagType] = None) -> str | None:
    """
    Adds a tag to the storage.

    Args:
        ctx (InuContext): The context object representing the command invocation.
        tag_type (Optional[TagType]): The type of the tag. Defaults to None.

    Returns:
        str | None: The name of the added tag, or None if the operation was cancelled.

    Raises:
        BotResponseError: If the tag is already taken or if there is a runtime error.
    """
    # get args with command
    try:
        name = ctx.options.name.strip()
        value = ctx.options.value.strip()
    # get args with modal
    except:
        try:
            answers, ctx = await ctx.ask_with_modal(
                "Tag", 
                ["Name:", "Value:"], 
                input_style_s=[TextInputStyle.SHORT, TextInputStyle.PARAGRAPH],
                placeholder_s=["The name of your tag", "What you will see, when you do /tag get <name>"],
                pre_value_s=[ctx.options.name or "", ctx.options.value or ""],
            )
        except asyncio.TimeoutError:
            return
        name, value = answers
        name = name.strip()
    try:
        tag = Tag(
            owner=ctx.author,
            channel_id=ctx.guild_id or ctx.channel_id,
        )
        tag.name = name
        tag.value = [value]
        if tag_type is not None:
            tag.tag_type = tag_type
        await tag.save()
    except TagIsTakenError:
        raise BotResponseError("Your tag is already taken", ephemeral=True)
    except RuntimeError as e:
        raise BotResponseError(bot_message=e.args[0], ephemeral=True)

    check = CheckForTagType("\n".join(tag.value))
    if check.check() is not None and not tag_type:
        try:
            maybe_ctx = await check.ask(ctx, tag)
            if maybe_ctx is not None:
                ctx = maybe_ctx
        except asyncio.TimeoutError:
            pass
    await ctx.respond(
        f"Your tag `{name}` has been added to my storage",
        component=MessageActionRowBuilder().add_interactive_button(
            ButtonStyle.SECONDARY, 
            tag.link,
            label=tag.name
        )
    )
    return name



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
        return
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
        # await #ctx.respond(f"I can't find a tag with the name `{ctx.options.name}` where you are the owner :/")
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
    await show_record(record, ctx, ctx.options.name, event=ctx.event)


    
@tag.child
@lightbulb.command("overview", "get an overview of all tags", aliases=["ov"])
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def overview(ctx: Context):
    """get an overview of all tags

    """
    menu = (
        MessageActionRowBuilder()
        .add_text_menu("overview_menu")
        .add_option("all tags you can use", "all")
        .add_option("guild tags", "guild")
        .add_option("your tags", "your")
        .add_option("global tags (all guilds)", "global")
        .parent
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
    new_ctx = get_context(event)
    await new_ctx.defer()
    result = event.interaction.values[0]
    type_ = {
        "guild": TagScope.GUILD,
        "all": TagScope.SCOPE,
        "global": TagScope.GLOBAL,
        "your": TagScope.YOUR,
    }.get(result)
    if type_ is None:
        raise RuntimeError("Can't get Tags, when Tag Scope is None")
    records = await TagManager.get_tags(type_, guild_id=ctx.guild_id or ctx.channel_id, author_id=ctx.author.id)
    if records is None:
        return
    embeds = records_to_embed(records)
    pag = Paginator(page_s=embeds, timeout=10*60)
    await pag.start(new_ctx)



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
    ctx._options["code"] = "\n".join(record["tag_value"])  # tag value is a list
    ext = tags.bot.get_plugin("Owner")
    for cmd in ext.all_commands:
        if cmd.name == "run":
            return await cmd.callback(ctx)


@tags.listener(event=hikari.InteractionCreateEvent)
async def on_tag_append(event: hikari.InteractionCreateEvent):
    """Listener for tag append button"""
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    if not event.interaction.custom_id.startswith("tag-append_"):
        return
    _, tag_id, additional_flag, new_page = event.interaction.custom_id.split("_")
    additional_flag, new_page = bool(int(additional_flag)), bool(int(new_page))
    tag = await Tag.from_id(
        int(tag_id), 
        user_id=event.interaction.user.id, 
        guild_or_channel_id=get_guild_or_channel_id(event.interaction)
    )
    ctx = get_context(event)
    if not tag.is_authorized_to_write(event.interaction.user.id):
        await ctx.respond("You don't own this tag hence you can't append to it", ephemeral=True)
        return
    await append_to_tag(ctx, tag, additional_flag, new_page, None)
    

@tag.child
@lightbulb.option("silent-message", "only you see the sucess message", choices=["Yes", "No"], default="No")
@lightbulb.option("new-page", "wether to write the tag on a new page or the last page", choices=["Yes", "No"], default="No")
@lightbulb.option("text", "the text, you want to append to the current value", type=str, default=None, modifier=OM.CONSUME_REST)
@lightbulb.option("name", "the name of your tag", autocomplete=True)  
@lightbulb.command("append", "remove a tag you own")
@lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
async def tag_append(_ctx: Context):
    """Remove a tag to my storage
    
    Args:
    -----
        - key: the name of the tag which you want to remove
    """
    ctx = get_context(_ctx.event, options=_ctx._options)
    additional_flag = True if ctx.options["silent-message"] == "Yes" else False
    new_page = True if ctx.options["new-page"] == "Yes" else False
    ctx.raw_options["name"] = ctx.options.name.strip()
    record = await get_tag_interactive(ctx)
    if not record:
        return
    tag: Tag = await Tag.from_record(record, ctx.author)
    await append_to_tag(ctx, tag, additional_flag, new_page, ctx.options.text)

async def append_to_tag(
    ctx: InuContext, 
    tag: Tag, 
    additional_flag: bool, 
    new_page: bool, 
    text: str | None
):
    to_add = ""
    if text:
        to_add = text.strip()
    else:
        to_add, ctx = await ctx.ask_with_modal(
            "tag append",
            "What do you want to append to the tag?",
            timeout=30*60,
        )
        if not to_add:
            return
    if new_page:
        tag.value.append("")
    tag.value[-1] += f"\n{to_add}"
    await tag.save()
    await ctx.respond(
        f"""Added\n```\n{to_add.replace("`", "")}``` to `{tag.name}`""",
        component=(
            hikari.impl.MessageActionRowBuilder()
            .add_interactive_button(
                ButtonStyle.SECONDARY,
                tag.link,
                label=tag.name
            )
            .add_interactive_button(
                ButtonStyle.SECONDARY,
                f"tag-append_{tag.id}_{int(additional_flag)}_{int(new_page)}",
                label="Append more",
                emoji="➕"
            )
        ),
        ephemeral=additional_flag
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
        return
    tag: Tag = await Tag.from_record(record, ctx.author)
    tag.name = ctx.options.new_name
    await tag.save()
    await ctx.respond(
        f"Changed name from `{old_key}` to `{tag.name}`"
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
    value = "\n".join(record['tag_value'])
    message = (
        f"**{record['tag_key']}**\n\n"
        f"tag {Human.plural_('author', len(record['author_ids']), with_number=False)}: "
        f"{Human.list_(record['author_ids'], '', '<@', '>', with_a_or_an=False)}\n"
        f"tag guilds/channels: {Human.list_([guild_name_or_id(gid) for gid in record['guild_ids']], with_a_or_an=False)}\n"
        f"tag aliases: {Human.list_(record['aliases'], '`', with_a_or_an=False)}\n"
        f"tag content: ```{Human.short_text(value, 1000).replace('`', '')}```\n"
        f"tag ID: {record['tag_id']}\n"
        f"link for this tag: `{tag.link}`"
    )
    await ctx.respond(
        message,
        component=MessageActionRowBuilder().add_interactive_button(
            ButtonStyle.SECONDARY, 
            tag.link,
            label="show tag"    
        )
    )

    

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
        return
    tag: Tag = await Tag.from_record(record, ctx.author)
    tag.aliases.add(f"{ctx.options.alias.strip()}")
    await tag.save()
    await ctx.respond(
        f"Added `{ctx.options.alias.strip()}` to optional names of `{tag.name}`",
        **EPHEMERAL
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
        return
    tag: Tag = await Tag.from_record(record, ctx.author)
    try:
        tag.aliases.add(f"{ctx.options.alias.strip()}")
    except ValueError:
        return await ctx.respond(f"This tag don't have an ailias called `{ctx.options.alias.strip()}` which I could remove", **EPHEMERAL)
    await tag.save()
    await ctx.respond(
        f"Added `{ctx.options.alias.strip()}` to optional names of `{tag.name}`",
        **EPHEMERAL
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
        return
    tag: Tag = await Tag.from_record(record, ctx.author)
    tag.owners.add(int(ctx.options.author.id))
    await tag.save()
    await ctx.respond(
        f"Added {ctx.options.author.username} as an author of `{tag.name}`",
        **EPHEMERAL
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
        return
    tag: Tag = await Tag.from_record(record, ctx.author)
    try:
        tag.owners.remove(int(ctx.options.author.id))
    except ValueError:
        return await ctx.respond(f"{ctx.options.author.username} was never an author", **EPHEMERAL)
    await tag.save()
    await ctx.respond(
        f"Removed {ctx.options.author.username} from the author of `{tag.name}`",
        **EPHEMERAL
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
async def tag_add_guild(_ctx: Context):
    """Remove a tag to my storage
    
    Args:
    -----
        - key: the name of the tag which you want to remove
    """
    options = _ctx.options
    ctx = get_context(_ctx.event)
    guild_id = guild_autocomplete_get_id(value=options.guild)
    record = await get_tag_interactive(ctx, options.name)
    if not record:
        return
    main_tag: Tag = await Tag.from_record(record, ctx.author)
    if not main_tag.is_authorized_to_write(ctx.author.id):
        return await ctx.respond(
            f"You are lacking on permissions to edit this tag",
            ephemeral=True
        )

    async def fetch_all_sub_tags(tag: str, tags: List[Tag], max_depth: int = 2, current_depth: int = 0) -> List[Tag]:
        """fetches all tags from  links in a tag recursively"""
        current_depth += 1
        tag_link_list = [tag.link for tag in tags]        
        for link in tag.tag_links:
            if link in tag_link_list:
                continue
            sub_tag = await Tag.fetch_tag_from_link(link, current_guild=_ctx.guild_id or _ctx.channel_id)
            if not sub_tag:
                continue
            tags.append(sub_tag)
            if sub_tag.tag_links and current_depth <= max_depth:
                tags.extend(await fetch_all_sub_tags(sub_tag, tags, max_depth=max_depth, current_depth=current_depth))
        return tags
            
    sub_tags = await fetch_all_sub_tags(main_tag, [main_tag])
    sub_tags.remove(main_tag)
    if sub_tags:
        label, ctx = await ctx.ask(
            f"Your tag `{main_tag.name}` has following sub-tags: {Human.list_([tag.name for tag in sub_tags], '`', with_a_or_an=False)}. Do you want to add all of them to the guild `{options.guild}`?",
        )
        if ctx is None:
            return
        if label == "Yes":
            failed_tags: List[str] = []
            success_tags: List[str] = []
            for tag in sub_tags:
                if not tag.is_authorized_to_write(ctx.author.id):
                    failed_tags.append(tag.name)
                    continue
                tag.guild_ids.add(guild_id)
                await tag.save()
                success_tags.append(tag.name)
            response = ""
            if success_tags:
                response += f"Added the following tags to the guild `{options.guild}`: {Human.list_(success_tags, '`', with_a_or_an=False)}\n"
            if failed_tags:
                response += f"Failed to add the following tags to the guild `{options.guild}`: {Human.list_(failed_tags, '`', with_a_or_an=False)} because of lacking permissions"
            await ctx.respond(
                response,
                ephemeral=True
            )
    main_tag.guild_ids.add(guild_id)
    await main_tag.save()
    await ctx.respond(
        f"You will now be able to see `{main_tag.name}` in the guild `{options.guild}`",
        ephemeral=True
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
        return #await ctx.respond(f"I can't find a tag with the name `{ctx.options.name}` where you are the owner :/")
    tag: Tag = await Tag.from_record(record, ctx.author)
    try:
        tag.guild_ids.remove(guild_id)
    except KeyError:
        return await ctx.respond(
            f"Your tag was never actually available in `{ctx.options.guild}`"
        )
    await tag.save()
    await ctx.respond(
        f"You won't see `{tag.name}` in the guild `{ctx.options.guild}` anymore",
        **EPHEMERAL
    )



@tag.child
@lightbulb.command("random", "Get a random tag from all tags available")
@lightbulb.implements(commands.SlashSubCommand, commands.PrefixSubCommand)
async def tag_random(ctx: Context):
    available_tags = await TagManager.get_tags(
        TagScope.SCOPE,
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
    """autocomplete for tag keys"""
    return await TagManager.tag_name_auto_complete(option, interaction)



@tag_remove_guild.autocomplete("guild")
@tag_add_guild.autocomplete("guild")
async def guild_auto_complete(
    option: hikari.AutocompleteInteractionOption,
    interaction: hikari.AutocompleteInteraction
) -> List[str]:
    value = option.value or ""
    value = str(value)
    guilds: List[Dict[str, str | int]] = []
    for gid, name in bot.cache.get_available_guilds_view().items():
        guilds.append({'id': gid, 'name': str(name)})
    if len(guilds) >= 1000:
        log.warning("Too many guilds to autocomplete - optimising guild list fast..")
        guilds = [guild for guild in guilds if value.lower() in guild["name"].lower()]
    guilds.append({'id': 000000000000000000, 'name': "Global - Everywhere where I am"})

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
