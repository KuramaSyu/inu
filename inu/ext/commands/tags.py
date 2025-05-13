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
from hikari import (
    ComponentInteraction, 
    Embed, 
    InteractionCreateEvent,
    MessageCreateEvent, 
    ResponseType,
    Snowflake, 
    TextInputStyle,
    ApplicationContextType
)
from hikari.impl import MessageActionRowBuilder
from hikari import ButtonStyle
import lightbulb
from lightbulb import AutocompleteContext, Context, Loader, Group, SubGroup, SlashCommand, invoke
import asyncpg
from fuzzywuzzy import fuzz
from utils import (
    TagIsTakenError, TagManager, TagScope, Human, get_guild_or_channel_id, 
    guild_name_or_id, TagType, crumble, ListParser, Paginator, StatelessPaginator, 
    TagHandler, Tag, TagViewPaginator, add_row_when_filled, TagCustomID, mockup_action_row
)
from core import (
    Inu, BotResponseError, getLogger, BotResponseError, ComponentContext, 
    get_context, InuContext
)

log = getLogger(__name__)
loader = lightbulb.Loader()



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



@loader.listener(hikari.InteractionCreateEvent)
async def on_tag_paginator_interaction(event: hikari.InteractionCreateEvent):
    """
    Handler for all tag paginator related interactions
    
    Notes:
    ------
    Keyword: `stl-tag`
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
    pag = TagViewPaginator(tag).set_custom_id(event.interaction.custom_id)
    await pag.rebuild(interaction=event.interaction)



async def get_tag_interactive(ctx: InuContext, key: str) -> Optional[Mapping[str, Any]]:
    """
    Get the tag interactive via message menues and interactions


    Note:
    -----
    - if there are multiple tags with same name, the user will be asked, which one to use
    """

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
            event = await ctx.bot.wait_for(
                InteractionCreateEvent,
                30,
            )
            if not isinstance(event.interaction, ComponentInteraction):
                return None
            await event.interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
            return records[event.interaction.values[0]]
        except asyncio.TimeoutError:
            return None
            


async def get_tag(ctx: InuContext, name: str) -> Optional[Mapping[str, Any]]:
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
    record: Mapping[str, Any] | None, 
    ctx: InuContext, 
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
    if not (record or tag):
        return await no_tag_found_msg(ctx, name or "<not given>", ctx.guild_id or ctx.channel_id)
    if not tag:
        try:
            tag = await Tag.from_record(record,  db_checks=False)
        except RuntimeError as e:
            raise BotResponseError(e.args[0], ephemeral=True)
    pag = TagViewPaginator(tag=tag)
    await tag.used_now()
    await pag.start(ctx, force_show_name=force_show_name, name=tag.name or name or "<not given>")
        
    

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
    ctx: InuContext,
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


async def tag_name_auto_complete(
    ctx: AutocompleteContext
) -> None:
    """Autocomplete for tag names"""
    log.debug(f"Autocompleting tags")
    option = ctx.focused
    res = await TagManager.tag_name_auto_complete(option, ctx.interaction)
    log.debug(f"Autocompleted tags: {res}")
    await ctx.respond(res)

async def guild_auto_complete(
    ctx: AutocompleteContext
) -> None:
    """Autocomplete for guild IDs"""
    try:
        log.debug(f"Autocompleting guilds")
        value = str(ctx.get_option(ctx.focused.name))
        guilds: List[Dict[str, str | int]] = []
        for gid, name in ctx.client.app.cache.get_available_guilds_view().items():  # type: ignore
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
        
        await ctx.respond([f"{guild['id']} | {guild['name']}" for guild in guilds]) 
    except Exception as e:
        log.error(f"Error in guild autocomplete: {e}")


def guild_autocomplete_get_id(value: str) -> int:
    return int(value[:value.find("|")])



@loader.listener(hikari.InteractionCreateEvent)
async def on_tag_link_interaction(event: hikari.InteractionCreateEvent):
    """
    Handler for Button/Menu Interactions with tag links
    """
    # menus dont work
    i = event.interaction
    log = getLogger(__name__, "tag link interaction")
    if not isinstance(i, hikari.ComponentInteraction):
        return
    ctx = get_context(event)
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
    await show_record(tag=tag, ctx=ctx, record=None)



@loader.listener(hikari.InteractionCreateEvent)  # type: ignore
async def on_tag_edit_interaction(event: hikari.InteractionCreateEvent):
    """Handler for Tag edit one time paginator"""
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return
    pag = TagHandler().set_custom_id(event.interaction.custom_id)
    try:
        if not pag.custom_id.type == "stl-tag-edit": return
    except:
        return
    log.debug(f"Custom ID is of type stl-tag-edit: {pag.custom_id}")
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
        answ, new_ctx = await ctx.ask(
            "You've no permission to edit this tag. Should I ask the owner to grant you the permission?",
            button_labels=["Yes", "No"],
            ephemeral=True,
            timeout=60*10,
        )
        if new_ctx is None:
            return
        asked_user = new_ctx.author

        if answ == "No":
            return await new_ctx.respond(
                update=True,
                components=[mockup_action_row(["Yes", "No"], True, [ButtonStyle.SECONDARY, ButtonStyle.PRIMARY])]
            )
        else:
            await new_ctx.respond(
                update=True,
                components=[mockup_action_row(["Yes", "No"], True, [ButtonStyle.PRIMARY, ButtonStyle.SECONDARY])]
            )

        answ, ctx = await new_ctx.ask(
            f"{Human.list_([f'<@{owner}>' for owner in tag.owners], with_a_or_an=False)}, should I grant {asked_user.mention} the permission to edit this tag?",
            button_labels=["Yes", "No"],
            timeout=60*10,
            ephemeral=False,
            allowed_users=tag.owners
        )

        if ctx is None:
            return
        
        mockup = {
            "button_labels": ["Yes", "No"],
            "is_disabled": True,
            "colors": [ButtonStyle.PRIMARY, ButtonStyle.SECONDARY]
        }

        if answ == "No":
            # mark no as pressed
            mockup["colors"].reverse()

        await ctx.respond(
            update=True, 
            components=[mockup_action_row(**mockup)]
        )
        if answ == "No":
            return
        else:
            await ctx.respond(
                update=True, 
                components=[mockup_action_row(
                        ["Yes", "No"], 
                        True, 
                        [ButtonStyle.PRIMARY, ButtonStyle.SECONDARY]
                )]
            )
            tag.owners.add(asked_user.id)
            await tag.save()
            await ctx.respond(f"{asked_user.mention} you got the permission to edit this tag now")
        return

    
    await tag.used_now()
    pag.set_tag(tag)
    log.debug("Starting stl-tag-edit")
    await pag.rebuild(event)


tags = Group(name="tag", description="Tags - simple digital sticky notes")

@tags.register
class TagAdd(
    SlashCommand,
    name="add",
    description="description",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    name = lightbulb.string("name", "The tags name", default=None)
    value = lightbulb.string("content", "the text your tag should return", default=None)

    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        """Add a tag to my storage
        
        Args:
        -----
            - name: the name the tag should have
            NOTE: the key is the first word you type in! Not more and not less!!!
            - value: that what the tag should return when you type in the name. The value is all after the fist word
        """
        await _tag_add(ctx, name=self.name, value=self.value)
    
    
async def _tag_add(
    ctx: InuContext, 
    name: str | None, 
    value: str | None, 
    tag_type: type[TagType] | None = None
) -> str | None:
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
        name = name.strip()
        value = value.strip()
    
    except Exception:
        # get args with modal
        try:
            answers, new_ctx = await ctx.ask_with_modal(
                "Tag", 
                ["Name:", "Value:"], 
                input_style_s=[TextInputStyle.SHORT, TextInputStyle.PARAGRAPH],
                placeholder_s=["The name of your tag", "What you will see, when you do /tag get <name>"],
                pre_value_s=[name or "", value or ""],
            )
        except asyncio.TimeoutError:
            return
        assert(new_ctx is not None and answers is not None)
        name, value = answers
        name = name.strip()
        
        ctx = new_ctx
    try:
        tag = Tag(
            owner=ctx.author,
            channel_id=ctx.guild_id or ctx.channel_id,
        )

        tag.name = name
        tag.value = [value]
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
    component=MessageActionRowBuilder().add_interactive_button(
            ButtonStyle.SECONDARY, 
            tag.link,
            label=tag.name
        )
    log.debug(f"Send message with component: {component}")
    await ctx.respond(
        f"Your tag `{name}` has been added to my storage",
        component=component
    )
    return name


@tags.register
class TagGet(
    SlashCommand,
    name="get",
    description="show a tag",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    name = lightbulb.string("name", "The tags name", autocomplete=tag_name_auto_complete)

    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        """Add a tag to my storage
        
        Args:
        -----
            - key: the name the tag should have
            NOTE: the key is the first word you type in! Not more and not less!!!
            - value: that what the tag should return when you type in the name. The value is all after the fist word
        """
        # TODO: record -> Tag; prevent typing issues with record
        record = await get_tag(ctx, self.name)
        await show_record(record, ctx, self.name)

@tags.register
class TagEdit(
    SlashCommand,
    name="edit",
    description="edit a tag you own",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    name = lightbulb.string("name", "The tags name", autocomplete=tag_name_auto_complete)

    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        """Add a tag to my storage
        
        Args:
        -----
            - key: the name the tag should have
            NOTE: the key is the first word you type in! Not more and not less!!!
            - value: that what the tag should return when you type in the name. The value is all after the fist word
        """
        record = await get_tag_interactive(ctx, key=self.name)
        if not record:
            return
        taghandler = TagHandler()
        await taghandler.start(ctx, record)


@tags.register
class TagRemove(
    SlashCommand,
    name="remove",
    description="remove a tag you own",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    name = lightbulb.string("name", "The tags name", autocomplete=tag_name_auto_complete)
    
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        """Remove a tag to my storage
        
        Args:
        -----
            - key: the name of the tag which you want to remove
        """
        name = self.name
        record = await get_tag_interactive(ctx, key=name)
        if not record:
            return
        
        await TagManager.remove(record['tag_id'])
        await ctx.respond(
            f"I removed the {'global' if 0 in record['guild_ids'] else 'local'} tag `{name}`"
        )


@tags.register
class TagOverview(
    SlashCommand,
    name="overview",
    description="get an overview of all tags",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):    
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
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
        # TODO: use ctx for the following
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

# TODO: reimplement
# @tag.child
# @lightbulb.add_checks(lightbulb.owner_only)
# @lightbulb.option(
#     "name", 
#     "the name of your tag", 
#     modifier=commands.OptionModifier.CONSUME_REST, 
#     required=True, 
#     autocomplete=True
# ) 
# @lightbulb.command("execute", "executes a tag with Python\nNOTE: owner only", aliases=["run", "exec"])
# @lightbulb.implements(commands.PrefixSubCommand, commands.SlashSubCommand)
# async def tag_execute(ctx: Context):
#     record = await get_tag(ctx, ctx.options.name)
#     if not record:
#         raise BotResponseError(bot_message=f"I can't find a tag with called `{ctx.options.name}`")
#     ctx._options["code"] = "\n".join(record["tag_value"])  # tag value is a list
#     ext = tags.bot.get_plugin("Owner")
#     for cmd in ext.all_commands:
#         if cmd.name == "run":
#             return await cmd.callback(ctx)


@loader.listener(hikari.InteractionCreateEvent)
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
    assert(tag is not None)
    ctx = get_context(event)
    if not tag.is_authorized_to_write(event.interaction.user.id):
        await ctx.respond("You don't own this tag hence you can't append to it", ephemeral=True)
        return
    await append_to_tag(ctx, tag, additional_flag, new_page, None)

yes = lightbulb.Choice("Yes", "Yes")  # value returned
no = lightbulb.Choice("No", "No")


@tags.register
class TagAppend(
    SlashCommand,
    name="append",
    description="append text to a tag you own",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    name = lightbulb.string("name", "The name of your tag", autocomplete=tag_name_auto_complete)
    text = lightbulb.string("text", "The text you want to append to the current value", default=None)
    new_page = lightbulb.boolean("new-page", "Whether to write the tag on a new page or the last page", default=False)
    silent_message = lightbulb.string("silent-message", "Only you see the success message", choices=[yes, no], default=no)

    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        """Append text to a tag you own
        
        Args:
        -----
            - name: the name of the tag to append to
            - text: the text to append to the tag
            - new_page: whether to write the tag on a new page or the last page
            - silent_message: only you see the success message
        """
        additional_flag = self.silent_message == "Yes"
        new_page = self.new_page
        name = self.name.strip()
        record = await get_tag_interactive(ctx, key=name)
        if not record:
            return
        tag: Tag = await Tag.from_record(record, ctx.author)
        await append_to_tag(ctx, tag, additional_flag, new_page, self.text)

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
        to_add, new_ctx = await ctx.ask_with_modal(
            "tag append",
            "What do you want to append to the tag?",
            timeout=30*60,
        )
        if not to_add:
            return
        if new_ctx is not None:
            ctx = new_ctx
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



@tags.register
class TagChangeName(
    SlashCommand, 
    name="change-name",
    description="Change the key (name) of a tag",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    old_name = lightbulb.string("old-name", "The old name from the tag", autocomplete=tag_name_auto_complete)
    new_name = lightbulb.string("new-name", "The new name for the tag")
    
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        """Change the name of a tag
        
        Args:
        -----
            old_name: the current name of the tag
            new_name: what the tag should be called afterwards
        """
        record = await get_tag_interactive(ctx, self.old_name)
        if not record:
            return
        tag: Tag = await Tag.from_record(record, ctx.author)
        tag.name = self.new_name
        await tag.save()
        await ctx.respond(
            f"Changed name from `{self.old_name}` to `{tag.name}`"
        )



@tags.register
class TagInfo(
    SlashCommand,
    name="info",
    description="get info to a tag",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    name = lightbulb.string("name", "The name of your tag", autocomplete=tag_name_auto_complete)
    
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        """Get info about a tag
        
        Args:
        -----
            name: the name of the tag to get info about
        """
        record = await get_tag(ctx, self.name)
        tag = await Tag.from_record(record, ctx.author, db_checks=False)
        if record is None:
            return await no_tag_found_msg(ctx, self.name, ctx.guild_id or ctx.channel_id, ctx.author.id)
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

    

@tags.register
class TagAddAlias(
    SlashCommand,
    name="add-alias",
    description="Add an alias (optional name) to a tag you own",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    name = lightbulb.string("name", "The name of your tag", autocomplete=tag_name_auto_complete)
    alias = lightbulb.string("alias", "The optional name you want to add")

    @invoke 
    async def callback(self, _: Context, ctx: InuContext):
        """Add an alias to a tag
        
        Args:
        -----
            name: the name of the tag to add an alias to
            alias: the alias to add
        """
        record = await get_tag_interactive(ctx, self.name)
        if not record:
            return
        tag: Tag = await Tag.from_record(record, ctx.author)
        tag.aliases.add(self.alias.strip())
        await tag.save()
        await ctx.respond(
            f"Added `{self.alias.strip()}` to optional names of `{tag.name}`",
            ephemeral=True
        )

@tags.register
class TagRemoveAlias(
    SlashCommand,
    name="remove-alias",
    description="Remove an alias (optional name) from a tag you own",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    name = lightbulb.string("name", "The name of your tag", autocomplete=tag_name_auto_complete)
    alias = lightbulb.string("alias", "The optional name you want to remove")

    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        """Remove an alias from a tag
        
        Args:
        -----
            name: the name of the tag to remove an alias from  
            alias: the alias to remove
        """
        record = await get_tag_interactive(ctx, self.name)
        if not record:
            return
        tag: Tag = await Tag.from_record(record, ctx.author)
        try:
            tag.aliases.remove(self.alias.strip())
        except ValueError:
            return await ctx.respond(
                f"This tag doesn't have an alias called `{self.alias.strip()}` which I could remove", 
                ephemeral=True
            )
        await tag.save()
        await ctx.respond(
            f"Removed `{self.alias.strip()}` from optional names of `{tag.name}`",
            ephemeral=True
        )

@tags.register
class TagAddAuthor(
    SlashCommand,
    name="add-author",
    description="add an author to your tag",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    name = lightbulb.string("name", "the name of your tag", autocomplete=tag_name_auto_complete)
    author = lightbulb.user("author", "The @person you want to add as author")
    
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        """Add an author to a tag
        
        Args:
        -----
            name: the name of the tag to add an author to
            author: the @person to add as author
        """
        record = await get_tag_interactive(ctx, self.name)
        if not record:
            return
        tag: Tag = await Tag.from_record(record, ctx.author)
        tag.owners.add(Snowflake(self.author.id))
        await tag.save()
        await ctx.respond(
            f"Added {self.author.username} as an author of `{tag.name}`",
            **EPHEMERAL
        )



@tags.register
class TagRemoveAuthor(
    SlashCommand,
    name="remove-author",
    description="remove an author from your tag",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    name = lightbulb.string("name", "The name of your tag", autocomplete=tag_name_auto_complete)
    author = lightbulb.user("author", "The @person you want to remove as author")

    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        """Remove an author from a tag
        
        Args:
        -----
            name: the name of the tag to remove an author from
            author: the @person to remove as author
        """
        record = await get_tag_interactive(ctx, self.name)
        if not record:
            return
        tag: Tag = await Tag.from_record(record, ctx.author)
        try:
            tag.owners.remove(Snowflake(self.author.id))
        except ValueError:
            return await ctx.respond(f"{self.author.username} was never an author", **EPHEMERAL)
        await tag.save()
        await ctx.respond(
            f"Removed {self.author.username} from the authors of `{tag.name}`",
            **EPHEMERAL
        )



@tags.register
class TagAddGuild(
    SlashCommand,
    name="add-guild",
    description="add a guild to your tag",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    guild = lightbulb.string("guild", "The guild/server ID you want to add", autocomplete=guild_auto_complete)
    name = lightbulb.string("name", "the name of your tag", autocomplete=tag_name_auto_complete)

    async def fetch_all_sub_tags(self, ctx: InuContext, tag: Tag, tags: List[Tag], max_depth: int = 2, current_depth: int = 0) -> List[Tag]:
        """fetches all tags from links in a tag recursively"""
        current_depth += 1
        tag_link_list = [tag.link for tag in tags]        
        for link in tag.tag_links:
            if link in tag_link_list:
                continue
            sub_tag = await Tag.fetch_tag_from_link(link, current_guild=ctx.guild_id or ctx.channel_id)
            if not sub_tag:
                continue
            tags.append(sub_tag)
            if sub_tag.tag_links and current_depth <= max_depth:
                tags.extend(await self.fetch_all_sub_tags(ctx, sub_tag, tags, max_depth=max_depth, current_depth=current_depth))
        return tags
        
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        """Add a guild to your tag
        
        Args:
        -----
            guild: The guild ID you want to add the tag to
            name: The name of the tag to add to the guild
        """
        guild_id = guild_autocomplete_get_id(value=self.guild)
        record = await get_tag_interactive(ctx, self.name)
        if not record:
            return
        main_tag: Tag = await Tag.from_record(record, ctx.author)
        if not main_tag.is_authorized_to_write(ctx.author.id):
            return await ctx.respond(
                f"You are lacking permissions to edit this tag",
                ephemeral=True
            )


            
        sub_tags = await self.fetch_all_sub_tags(ctx, main_tag, [main_tag])
        sub_tags.remove(main_tag)
        if sub_tags:
            label, new_ctx = await ctx.ask(
                f"Your tag `{main_tag.name}` has following sub-tags: {Human.list_([tag.name for tag in sub_tags if tag.name], '`', with_a_or_an=False)}. Do you want to add all of them to the guild `{self.guild}`?",
            )
            if new_ctx is None:
                return
            if label == "Yes":
                failed_tags: List[str] = []
                success_tags: List[str] = []
                for tag in sub_tags:
                    if not tag.is_authorized_to_write(new_ctx.author.id):
                        failed_tags.append(tag.name)
                        continue
                    tag.guild_ids.add(guild_id)
                    await tag.save()
                    success_tags.append(tag.name)
                response = ""
                if success_tags:
                    response += f"Added the following tags to the guild `{self.guild}`: {Human.list_(success_tags, '`', with_a_or_an=False)}\n"
                if failed_tags:
                    response += f"Failed to add the following tags to the guild `{self.guild}`: {Human.list_(failed_tags, '`', with_a_or_an=False)} because of lacking permissions"
                await new_ctx.respond(
                    response,
                    ephemeral=True
                )
        main_tag.guild_ids.add(guild_id)
        await main_tag.save()
        await ctx.respond(
            f"You will now be able to see `{main_tag.name}` in the guild `{self.guild}`",
            ephemeral=True
        )

@tags.register
class TagRemoveGuild(
    SlashCommand,
    name="remove-guild",
    description="remove a guild/server from your tag",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    guild = lightbulb.string("guild", "The guild/server ID you want to remove", autocomplete=guild_auto_complete)
    name = lightbulb.string("name", "the name of your tag", autocomplete=tag_name_auto_complete)

    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        """Remove a guild from a tag
        
        Args:
        -----
            guild: The guild ID you want to remove the tag from
            name: The name of the tag to remove from the guild
        """
        guild_id = guild_autocomplete_get_id(value=self.guild)
        record = await get_tag_interactive(ctx, self.name)
        if not record:
            return
        tag: Tag = await Tag.from_record(record, ctx.author)
        try:
            tag.guild_ids.remove(guild_id) 
        except KeyError:
            return await ctx.respond(
                f"Your tag was never actually available in `{self.guild}`",
                ephemeral=True
            )
        await tag.save()
        await ctx.respond(
            f"You won't see `{tag.name}` in the guild `{self.guild}` anymore",
            ephemeral=True
        )


@tags.register
class TagRandom(
    SlashCommand,
    name="random",
    description="Get a random tag from all tags available",
    contexts=[ApplicationContextType.GUILD | ApplicationContextType.PRIVATE_CHANNEL],
):
    @invoke
    async def callback(self, _: Context, ctx: InuContext):
        """Get a random tag from all available tags"""
        available_tags = await TagManager.get_tags(
            TagScope.SCOPE,
            guild_id=ctx.guild_id,
            author_id=ctx.author.id,
        )
        if not available_tags:
            raise BotResponseError(f"No tags found for the random command")
        random_tag = random.choice(available_tags)
        await show_record(random_tag, ctx, force_show_name=True)


loader.command(tags)