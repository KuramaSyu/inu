from ast import alias
import traceback
import typing
from typing import (
    Union,
    Optional,
    List,
    Callable,
    Mapping,
    Any
)
import asyncio
import logging

import hikari
from hikari import ComponentInteraction, InteractionCreateEvent, NotFoundError, events, ResponseType, Embed
from hikari.messages import ButtonStyle
from hikari.impl import ActionRowBuilder
import lightbulb
from lightbulb import MemberConverter, GuildConverter, UserConverter
from lightbulb.context import Context

from utils import TagIsTakenError
from .base import (
    Paginator,
    EventListener,
    EventObserver,
    listener,
)
import asyncpg

from utils import crumble, TagManager
from utils.language import Human

from core import Inu

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

class Tag():
    def __init__(self, owner: Optional[hikari.User] = None, channel_id: Optional[hikari.Snowflakeish] = None):
        """
        Members:
        --------
            - is_local: (bool) if tag is local or global. default=True if invoked from guild else default=False
            - owner: (User | Member) the owner of the Tag
            - name: (str) the key of the tag
            - is_local_available: (bool) whether or not the tag can be stored local
            - is_global_available: (bool) whter or not the tag can be stored global
            - is_stored: (bool) wether or not the tag is already in the db stored
        NOTE:
        -----
            - the owner should be an instace of `Member`, to be able, to store an tag locally
            otherwise the tag have to be stored globally
        """
        self.owners: List[hikari.Snowflake] = [owner.id] if owner else []
        self._name: Optional[str] = None
        self.value: Optional[str] = None
        self.is_local_available: bool
        self.is_global_available: bool
        self._is_local: bool = True
        self.is_stored: bool
        self._id: Optional[int] = None
        self.aliases: List[str] = []
        self.guild_ids: List[int] = []
        if isinstance(owner, hikari.Member):
            self.guild_ids.append(owner.guild_id)
            self._is_local = True
        else:
            if channel_id:
                self.guild_ids.append(channel_id)
                self._is_local = True
            else:
                self.guild_ids.append(0)
                self._is_local = False

    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, value):
        
        if len(str(value)) > 256:
            raise RuntimeError("Can't store a tag with a name bigger than 256 chars")
        self._name = value

    @property
    def is_local(self) -> bool:
        return self._is_local


    @property
    def id(self) -> int:
        if not self._id:
            raise RuntimeError("Can't store an ID without a number")
        return self._id
    
    @id.setter
    def id(self, value):
        self._id = value

    @property
    def to_do(self) -> Optional[str]:
        """returns a string with things which have to be done before storing the tag"""
        to_do_msg = ""
        if self.name is None:
            to_do_msg += "- Enter a name\n"
        if self.value is None:
            to_do_msg += "- Enter a value\n"
        if (
            not self.is_stored
            and self._is_local
            and not self.is_local_available
        ):
            to_do_msg += "- Your tag isn't local available -> change the name\n"
        if (
            not self.is_stored
            and not self._is_local
            and not self.is_global_available
        ):
            to_do_msg += "- Your tag isn't global available -> change the name\n"
        return to_do_msg or None
        

    async def save(self):
        """
        Saves the current tag.

        Raises:
        -------
            - TagIsTakenError
        """
        if not self.name or not self.value:
            raise RuntimeError("I can't store a tag without a name and value")
        if self.is_stored:
            await TagManager.edit(
                key=self.name,
                value=self.value,
                author_ids=self.owners,
                tag_id=self.id,
                guild_ids=self.guild_ids,
                aliases=self.aliases,
            )
        else:
            tag_id = await TagManager.set(
                key=self.name,
                value=self.value,
                author_ids=self.owners,
                guild_ids=self.guild_ids,
                aliases=self.aliases,
            )
            self.id = tag_id
        self.is_stored = True

    @classmethod
    async def from_record(cls, record: Mapping[str, Any], author: hikari.User) -> "Tag":
        # """
        # loads an existing tag in form of a dict like object into self.tag (`Tag`)
        # Args:
        # -----
        #     - tag: (Mapping[str, Any]) the tag which should be loaded
        #     - author: (Member, User) the user which stored the tag
        # """
        # guild_id = self.owner.guild_id if isinstance(self.owner, hikari.Member) else 0
        # local_taken, global_taken = await TagManager.is_taken(key=self.tag.name, guild_id = guild_id or 0)
        # self.name = tag["tag_key"]
        # self.value = tag["key_value"]
        # self.is_stored = True
        # self.id = tag["tag_id"]
        # self.is_global_available = not global_taken
        # self.is_local_available = not local_taken

        """
        loads an existing tag in form of a dict like object into self.tag (`Tag`)
        Args:
        -----
            - record: (Mapping[str, Any]) the tag which should be loaded
            - author: (Member, User) the user which stored the tag
        """
        local_taken, global_taken = await TagManager.is_taken(key=record["tag_key"], guild_ids=record["guild_ids"])
        new_tag = cls(author)
        new_tag.name = record["tag_key"]
        new_tag.value = record["tag_value"]
        new_tag.is_stored = True
        new_tag.id = record["tag_id"]
        new_tag.guild_ids = record["guild_ids"]
        new_tag.aliases = record["aliases"]
        new_tag.owners = record["author_ids"]
        if (
            isinstance(author, hikari.Member)
            and not 0 in record["guild_ids"]
            and author.guild_id in record["guild_ids"]
        ):
            new_tag._is_local = True
        else:
            new_tag._is_local = False
        new_tag.is_global_available = not global_taken
        new_tag.is_local_available = not local_taken
        return new_tag

    def get_embed(self) -> hikari.Embed:
        embed = Embed()
        embed.title = self.tag.name
        embed.description = self.tag.value
        embed.add_field(name="Status", value=str(self))
        return embed

    async def prepare_new_tag(self, author: Union[hikari.Member, hikari.User]):
        """
        creates a new tag in form of `Tag`
        Args:
        -----
            - author: (Member, User) the user which stored the tag
        """
        tag = Tag()
        tag.owners = self.owners
        tag.name = None
        tag.value = None
        tag.is_stored = False
        if isinstance(author, hikari.Member):
            tag._is_local = True
        else:
            tag._is_local = False
        tag.is_global_available = False
        tag.is_local_available = False
        self.tag = tag

        self.embed = Embed()
        self.embed.title = self.tag.name or "Name - Not set"
        self.embed.description = self.tag.value or "Value - Not set"
        self.embed.add_field(name="Status", value=str(self.tag))
        self._pages = [self.embed]

    def __str__(self) -> str:
        msg = (
            f"your tag is: {'local' if self._is_local else 'global'}\n"
            f"the owners are: {', '.join(f'<@{o}>' for o in self.owners)}\n"
            f"is the tag stored: {Human.bool_(self.is_stored)}\n"
            f"available for guilds: {', '.join(str(id) for id in self.guild_ids)}\n"
            f"is the tag name local available: {Human.bool_(self.is_local_available)}\n"
            f"is the tag name global available: {Human.bool_(self.is_global_available)}\n"
        )
        if self.aliases:
            msg += f"aliases: {', '.join(self.aliases)}\n"
        if to_do := self.to_do:
            msg += (
                f"\n**TO DO:**\n{to_do}"
            )
        return msg

    async def update(self) -> None:
        """
        Updates self.is_global_available and self.is_local_available
        - is a coroutine
        """
        self.is_global_available = True
        self.is_local_available = True
        local_taken, global_taken = await TagManager.is_taken(self.name, self.guild_ids)
        if local_taken:
            self.is_local_available = False
        if global_taken:
            self.is_global_available = False

    async def delete(self):
        """Deletes this tag from the database if it is already stored"""
        if not self.is_stored:
            return
        await TagManager.remove(self.id)
        self.is_stored = False
        return



class TagHandler(Paginator):
    """An interactive handler for new tags"""
    def __init__(
        self,
        timeout: int = 15*60,
        component_factory: Callable[[int], ActionRowBuilder] = None,
        components_factory: Callable[[int], List[ActionRowBuilder]] = None,
        disable_pagination: bool = False,
        disable_component: bool = True,
        disable_components: bool = False,
        disable_paginator_when_one_site: bool = False,

    ):

        self.tag: Tag
        self._pages: List[Embed] = []
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)
        self.bot: Inu

        super().__init__(
            page_s=self._pages,
            timeout=timeout,
            component_factory=component_factory,
            components_factory=components_factory,
            disable_pagination=disable_pagination,
            disable_component=disable_component,
            disable_components=disable_components,
            disable_paginator_when_one_site=disable_paginator_when_one_site,
        )

    async def start(self, ctx: Context, tag: Mapping = None):
        """
        Starts the paginator and initializes the tag
        Args:
            ctx: (lightbulb.Context) the Context
            tag: (dict, default=None) the tag which should be
                initialized. Creates new tag, if tag is None
        """
        try:
            self.ctx = ctx
            self.bot = ctx.bot
            if not tag:
                await self.prepare_new_tag(ctx.member or ctx.author)
            else:
                await self.load_tag(tag, ctx.member or ctx.author)
                
            await super().start(ctx)
        except Exception:
            self.log.error(traceback.format_exc())

    async def update_page(self, update_value: bool = False):
        """Updates the embed, if the interaction wasn't for pagination"""
        if update_value:
            pages = []
            for index, page in enumerate(crumble(str(self.tag.value), 2000)):
                pages.append(Embed(
                    title="",
                    description=page
                ))
            self._pages = pages
            self._pages[0].add_field(name="Info", value="not set")
        # updating embed titles
        for page in self._pages:
            page.title = self.tag.name or "Name - not set"
        await self.tag.update()

        self._pages[0].edit_field(0, "Info", str(self.tag))
        await self._message.edit(
            embed=self._pages[0],
            components=self.components
        )


    @listener(events.InteractionCreateEvent)
    async def on_interaction(self, event: events.InteractionCreateEvent):
        """
        The starting point of all interactions. 
        The interaction custom_id will be checked,
        and the right method will be called, to handle the event
        Args:
        -----
            - event: (InteractionCreateEvent) the invoked event; passed from the listener
        """
        self.log.info("on interaction")
        try:
            if not isinstance(event.interaction, ComponentInteraction):
                return
            if (not event.interaction.message.id == self._message.id 
                or not event.interaction.user.id == self.ctx.author.id):
                return
            i = event.interaction
            try:
                custom_id = event.interaction.values[0]
            except IndexError:
                # interaction was no menu interaction
                return
            if custom_id == "set_name":
                await self.set_name(event.interaction)
            elif custom_id == "set_value":
                await self.set_value(event.interaction)
            elif custom_id == "extend_value":
                await self.extend_value(event.interaction)
            elif custom_id == "change_visibility":
                await self.change_visibility(event.interaction)
            elif custom_id == "change_owner":
                await self.change_owner(event.interaction)
            elif custom_id == "finish":
                await self.finish(event.interaction)
            elif custom_id == "remove_tag":
                await self.delete(event.interaction)
            elif custom_id == "add_author_id":
                await self.change_creators(i, List.append)
            elif custom_id == "add_alias":
                await self.change_aliases(i, List.append)
            elif custom_id == "add_guild_id":
                await self.change_guild_ids(i, List.append)
            elif custom_id == "remove_author_id":
                await self.change_creators(i, List.remove)
            elif custom_id == "remove_alias":
                await self.change_aliases(i, List.remove)
            elif custom_id == "remove_guild_id":
                await self.change_guild_ids(i, List.remove)
            else:
                log.warning(f"Unknown custom_id: {custom_id} - in {self.__class__.__name__}")
            if self.tag.name and self.tag.value:
                try:
                    await self.tag.save()
                except Exception:
                    pass
            await self.update_page(update_value=custom_id in ["set_value", "extend_value"])
            
        except Exception:
            self.log.error(traceback.format_exc())

    async def change_creators(self, interaction: ComponentInteraction, op: Union[List.append, List.remove]):
        """
        Args:
        -----
            - op (`builtins.function`) the function, where the result of the question will be passed in
        """
        user_str, interaction, event = await self.bot.shortcuts.ask_with_modal(
            "Edit Tag",
            "What is the person you want to add?",
            interaction=interaction,
            placeholder="something like @user, user#0000 or the ID of the user"
        )
        await interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
        try:
            user = await UserConverter(self.ctx).convert(user_str)
        except TypeError:
            return await self.ctx.respond(f"No person like `{user_str}` found.")
        try:
            op(self.tag.owners, user.id)
        except ValueError:
            await self.bot.rest.create_message(interaction.channel_id, "ID's are supposed to be numbers")
            return
        
        #await self.bot.rest.create_message(interaction.channel_id, f"`{user_id}` added to authors of this tag")

    async def change_guild_ids(self, interaction: ComponentInteraction, op: Union[List.append, List.remove]):
        """
        Args:
        -----
            - op (`builtins.function`) the function, where the result of the question will be passed in
        """

        log.debug("ask")
        guild_id, interaction, event = await self.bot.shortcuts.ask_with_modal(
            "Edit Tag",
            "Enter the guild ID you want to add",
            placeholder="something like 1234567890123456789",
            interaction=interaction,
        )

        await interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
        try:
            op(self.tag.guild_ids, int(guild_id))
        except ValueError:
            await self.bot.rest.create_message(interaction.channel_id, "ID's are supposed to be numbers")
            return
        #await interaction.create_initial_response(f"You can use this tag now in `{guild_id}`")

    async def change_aliases(self, interaction: ComponentInteraction, op: Union[List.append, List.remove]):
        """
        Args:
        -----
            - op (`builtins.function`) the function, where the result of the question will be passed in
        """
        # I know this function is redundant, but otherwise it would affect the readability
        alias, interaction, event = await self.bot.shortcuts.ask_with_modal(
            "Edit Tag",
            "What should be the name of the new alias?",
            interaction=interaction,
        )
        await interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
        op(self.tag.aliases, alias)
        #await interaction.create_initial_response(f"`{alias}` is now an alternative name of this tag")
        
        


    async def delete(self, interaction: ComponentInteraction):
        await self.tag.delete()
        await interaction.create_initial_response(
            ResponseType.MESSAGE_CREATE,
            f"I removed {'local' if self.tag.is_local else 'global'} tag `{self.tag.name}`"
        )
        self.tag.name = None
        self.tag.value = None
        self.tag.is_local_available = False
        self.tag.is_global_available = False
        await self.tag.update()

    async def set_name(self, interaction: ComponentInteraction):
        new_name, interaction, event = await self.bot.shortcuts.ask_with_modal(
            "Rename Tag",
            "New name:",
            min_length_s=1,
            max_length_s=256,
            interaction=interaction,
        )
        self.tag.name = new_name
        await interaction.create_initial_response(
            ResponseType.DEFERRED_MESSAGE_UPDATE
        )


    async def set_value(self, interaction: ComponentInteraction, append: bool = False):
        value, interaction, event = await self.bot.shortcuts.ask_with_modal(
            self.tag.name or "Tag",
            "Add to value:" if append else "Value:",
            interaction=interaction,
        )
        await interaction.create_initial_response(
            ResponseType.DEFERRED_MESSAGE_UPDATE
        )
        if append and self.tag.value:
            self.tag.value += value
        else:
            self.tag.value = value

    async def extend_value(self, interaction: ComponentInteraction):
        await self.set_value(interaction, append=True)

    async def change_visibility(self, interaction: ComponentInteraction):
        if self.tag._is_local:
            self.tag._is_local = False
            self.tag.guild_ids.append(0)
        else:
            self.tag._is_local = True
            self.tag.guild_ids.remove(0)
        await interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
        # await self.update_page()

    async def finish(self, interaction: ComponentInteraction):
        try:
            await self.tag.save()
            await self.update_page()
        except TagIsTakenError:
            await interaction.create_initial_response(
                ResponseType.MESSAGE_CREATE,
                f"Your tag name {self.tag.name}` is {'locally' if self.tag._is_local else 'globally'} already taken"
            )
        except Exception:
            tb = traceback.format_exc()
            pages: List[Embed] = []
            for page in crumble(tb):
                embed = Embed()
                embed.title = "Saving the tag failed"
                embed.description = page
                pages.append(embed)
            await interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_CREATE)
            paginator = Paginator(pages)
            await paginator.start(self.ctx)
            return

        await interaction.create_initial_response(
            ResponseType.MESSAGE_CREATE,
            f"Your tag `{self.tag.name}` was successfully added to my storage :)"
        )

    async def change_owner(self, interaction: ComponentInteraction):
        embed = (
            Embed(title="Enter the ID of the new owner or ping him/her/it or enter the complete name with #XXXX")
            .set_footer(text=f"timeout after {self.timeout}s")
        )
        await interaction.create_initial_response(
            ResponseType.MESSAGE_CREATE,
            embed=embed
        )
        bot_message = await interaction.fetch_initial_response()
        try:
            event = await self.bot.wait_for(
                events.MessageCreateEvent,
                self.timeout,
                lambda m: m.author_id == interaction.user.id and m.channel_id == interaction.channel_id
            )
        except asyncio.TimeoutError:
            await interaction.delete_initial_response()
            return

        if event.message.content is None:
            return

        try:
            user = await user_converter(WrappedArg(event.message.content, self.ctx))
        except NotFoundError:
            user = None

        if not user:
            return await event.message.respond(
                "I can't find anyone",
                reply=event.message,
            )
        if user and (channel := self.ctx.get_channel()):
            await channel.delete_messages(bot_message, event.message)
        self.tag.owner = user
        # await self.update_page()

    def build_default_components(self, position) -> List[ActionRowBuilder]:
        navi = super().build_default_component(position)
        disable_remove_when = lambda self: self.tag.name is None or self.tag.value is None
        disable_save_when = lambda self: self.tag.name is None or self.tag.value is None
        intelligent_button_style = lambda value: ButtonStyle.PRIMARY if not (value) else ButtonStyle.SECONDARY
        tag_specific = (
            ActionRowBuilder()
            .add_button(intelligent_button_style(self.tag.name), "set_name")
            .set_label("set name")
            .add_to_container()
            .add_button(intelligent_button_style(self.tag.value), "set_value")
            .set_label("set value")
            .add_to_container()
            .add_button(ButtonStyle.SECONDARY, "extend_value")
            .set_label("append to value")
            .add_to_container()
            .add_button(ButtonStyle.SECONDARY, "change_visibility")
            .set_label("local/global")
            .add_to_container()
        )
        add_options = (
            ActionRowBuilder()
            .add_button(ButtonStyle.SECONDARY, "add_alias")
            .set_label("add an alias").add_to_container()
            # .add_button(ButtonStyle.DANGER, "change_owner")
            # .set_label("change tag owner")
            .add_button(ButtonStyle.SECONDARY, "add_guild_id")
            .set_is_disabled(not self.tag.is_local)
            .set_label("add a guild").add_to_container()
            .add_button(ButtonStyle.SECONDARY, "add_author_id")
            .set_label("add an author").add_to_container()
        )
        danger_tags = (
            ActionRowBuilder()
            .add_button(ButtonStyle.DANGER, "remove_tag")
            .set_label("delete tag")
            .set_is_disabled(not self.tag.is_stored).add_to_container()
            # .add_button(ButtonStyle.DANGER, "change_owner")
            # .set_label("change tag owner")
            .add_button(ButtonStyle.DANGER, "remove_author_id")
            .set_label("remove author").add_to_container()
            .add_button(ButtonStyle.DANGER, "remove_alias")
            .set_label("remove alias").add_to_container()
            .add_button(ButtonStyle.DANGER, "remove_guild_id")
            .set_label("remove server")
            .set_is_disabled(not self.tag.is_local).add_to_container()
        )
        finish = (
            ActionRowBuilder()
            .add_button(intelligent_button_style(self.tag.is_stored), "finish")
            .set_label("save")
            .set_is_disabled(disable_save_when(self))
            .add_to_container()
        )
        menu = (
            ActionRowBuilder()
            .add_select_menu("tag_options")
            .add_option("set name", "set_name").add_to_menu()
            .add_option("set value", "set_value").add_to_menu()
            .add_option("append to value", "extend_value").add_to_menu()
            .add_option("add an alias", "add_alias").add_to_menu()
            .add_option("add a guild", "add_guild_id").add_to_menu()
            .add_option("add an author", "add_author_id").add_to_menu()
            .add_option("remove an author", "remove_author_id").add_to_menu()
            .add_option("remove alias", "remove_alias").add_to_menu()
            .add_option("remove guild", "remove_guild_id").add_to_menu()
            .add_option("local / global", "change_visibility").add_to_menu()
            .add_option("delete tag", "remove_tag").add_to_menu()
            .add_to_container()
        )
        #if self.pagination:
        return [navi, menu] #type: ignore
        #return [tag_specific, finish]

    async def load_tag(self, tag: Mapping[str, Any], author: Union[hikari.Member, hikari.User]):
        """
        loads an existing tag in form of a dict like object into self.tag (`Tag`)
        Args:
        -----
            - tag: (Mapping[str, Any]) the tag which should be loaded
            - author: (Member, User) the user which stored the tag
        """
        # guild_id = author.guild_id if isinstance(author, hikari.Member) else 0
        # local_taken, global_taken = await TagManager.is_taken(key=tag["tag_key"], guild_id = guild_id or 0)
        # new_tag: Tag = Tag(author)
        # new_tag.name = tag["tag_key"]
        # new_tag.value = tag["tag_value"]
        # new_tag.is_stored = True
        # new_tag.id = tag["tag_id"]
        # new_tag.guild_ids = tag["guild_ids"]
        # new_tag.aliases = tag["aliases"]
        # new_tag.owners = tag["author_ids"]
        # if (
        #     isinstance(author, hikari.Member)
        #     and not 0 in tag["guild_ids"]
        #     and author.guild_id in tag["guild_ids"]
        # ):
        #     new_tag._is_local = True
        # else:
        #     new_tag._is_local = False
        # new_tag.is_global_available = not global_taken
        # new_tag.is_local_available = not local_taken
        new_tag = await Tag.from_record(record=tag, author=author)
        self.tag = new_tag

        self.embed = Embed()
        self.embed.title = self.tag.name
        self.embed.description = self.tag.value
        self.embed.add_field(name="Status", value=self.tag.__str__())
        self._pages = [self.embed]
        self._default_site = len(self._pages) - 1

    async def prepare_new_tag(self, author):
        """
        creates a new tag in form of `Tag`
        Args:
        -----
            - author: (Member, User) the user which stored the tag
        """
        tag = Tag(self.ctx.member or self.ctx.author)
        tag.name = None
        tag.value = None
        tag.is_stored = False
        if isinstance(author, hikari.Member):
            tag._is_local = True
        else:
            tag._is_local = False
        tag.is_global_available = False
        tag.is_local_available = False
        self.tag = tag

        self.embed = Embed()
        self.embed.title = self.tag.name or "Name - not set"
        self.embed.description = self.tag.value or "Value - not set"
        self.embed.add_field(name="Status", value=self.tag.__str__())
        self._pages = [self.embed]







