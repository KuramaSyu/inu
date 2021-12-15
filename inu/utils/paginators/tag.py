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
from lightbulb.context import Context

from utils.tag_mamager import TagIsTakenError
from .common import (
    Paginator,
    EventListener,
    EventObserver,
    listener,
)
import asyncpg

from utils import crumble
from utils.tag_mamager import TagManager
from utils.language import Human

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

class Tag():
    def __init__(self, owner: hikari.User):
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
        self.owner: Union[hikari.User, hikari.Member] = owner
        self._name: Optional[str] = None
        self.value: Optional[str] = None
        self.is_local_available: bool
        self.is_global_available: bool
        self._is_local: bool = True
        self.is_stored: bool
        self._id: Optional[int] = None

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
        if not isinstance(self.owner, hikari.Member):
            self._is_local = False
            return False
        return self._is_local

    @property
    def guild_id(self) -> Optional[int]:
        if not isinstance(self.owner, hikari.Member):
            return None
        if not self._is_local:
            return None
        return self.owner.guild_id

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
                author=self.owner,
                tag_id=self.id,
                guild_id=self.guild_id,
            )
        else:
            tag_id = await TagManager.set(
                key=self.name,
                value=self.value,
                author=self.owner,
                guild_id=self.guild_id,
            )
            self.id = tag_id
        self.is_stored = True

    async def load_tag(self, tag: Mapping[str, Any]):
        """
        loads an existing tag in form of a dict like object into self.tag (`Tag`)
        Args:
        -----
            - tag: (Mapping[str, Any]) the tag which should be loaded
            - author: (Member, User) the user which stored the tag
        """
        guild_id = self.owner.guild_id if isinstance(self.owner, hikari.Member) else 0
        local_taken, global_taken = await TagManager.is_taken(key=self.tag.name, guild_id = guild_id or 0)
        self.name = tag["tag_key"]
        self.value = tag["key_value"]
        self.is_stored = True
        self.id = tag["tag_id"]
        if (
            isinstance(self.owner, hikari.Member)
            and tag["guild_id"] is not None
            and self.guild_id == tag["guild_id"]
        ):
            self._is_local = True
        else:
            self._is_local = False
        self.is_global_available = not global_taken
        self.is_local_available = not local_taken

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
        tag = Tag(self.owner)
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
            f"the owner is: {self.owner.username}\n"
            f"is the tag stored: {Human.bool_(self.is_stored)}\n"
            f"is the tag name local available: {Human.bool_(self.is_local_available)}\n"
            f"is the tag name global available: {Human.bool_(self.is_global_available)}\n"
        )
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
        local_taken, global_taken = await TagManager.is_taken(self.name, self.guild_id or 0)
        self.is_global_available = not global_taken
        self.is_local_available = not local_taken

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
                or not event.interaction.user.id == self.tag.owner.id):
                return
            custom_id = event.interaction.custom_id or None
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
        except Exception:
            self.log.error(traceback.format_exc())

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
        await self.update_page(update_value=True)

    async def set_name(self, interaction: ComponentInteraction):
        embed = Embed(title="Enter a name for your tag:", description=f"You have {self.timeout}s")
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
            return

        if event.message.content is None:
            return

        if (l := len(event.message.content)) > 256:
            return await event.message.respond(
                f"Your name is {l - 256} letters too long"
            )
        self.tag.name = event.message.content
        await self.update_page()
        if (channel := self.ctx.get_channel()):
            await channel.delete_messages(bot_message, event.message)


    async def set_value(self, interaction: ComponentInteraction, append: bool = False):
        embed = Embed(title="Enter the value for your tag:", description=f"You have {self.timeout}s")
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

        if not event.message.content:
            await interaction.delete_initial_response()
            return

        
        if append and self.tag.value:
            self.tag.value += event.message.content
        else:
            self.tag.value = event.message.content
        await self.update_page(update_value=True)
        if (channel := self.ctx.get_channel()):
            await channel.delete_messages(bot_message, event.message)

    async def extend_value(self, interaction: ComponentInteraction):
        await self.set_value(interaction, append=True)

    async def change_visibility(self, interaction: ComponentInteraction):
        if self.tag._is_local:
            self.tag._is_local = False
        else:
            self.tag._is_local = True
        await interaction.create_initial_response(ResponseType.DEFERRED_MESSAGE_UPDATE)
        await self.update_page()

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
        await self.update_page()

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
        danger_tags = (
            ActionRowBuilder()
            .add_button(ButtonStyle.DANGER, "remove_tag")
            .set_label("remove tag")
            .set_is_disabled(disable_remove_when(self))
            .add_to_container()
            .add_button(ButtonStyle.DANGER, "change_owner")
            .set_label("change tag owner")
            .add_to_container()
        )
        finish = (
            ActionRowBuilder()
            .add_button(intelligent_button_style(self.tag.is_stored), "finish")
            .set_label("save")
            .set_is_disabled(disable_save_when(self))
            .add_to_container()
        )
        if self.pagination:
            return [navi, tag_specific, danger_tags, finish] #type: ignore
        return [tag_specific, finish]

    async def load_tag(self, tag: Mapping[str, Any], author: Union[hikari.Member, hikari.User]):
        """
        loads an existing tag in form of a dict like object into self.tag (`Tag`)
        Args:
        -----
            - tag: (Mapping[str, Any]) the tag which should be loaded
            - author: (Member, User) the user which stored the tag
        """
        guild_id = author.guild_id if isinstance(author, hikari.Member) else 0
        local_taken, global_taken = await TagManager.is_taken(key=tag["tag_key"], guild_id = guild_id or 0)
        new_tag: Tag = Tag(author)
        new_tag.name = tag["tag_key"]
        new_tag.value = tag["tag_value"][0]
        new_tag.is_stored = True
        new_tag.id = tag["tag_id"]
        if (
            isinstance(author, hikari.Member)
            and tag["guild_id"] is not None
            and author.guild_id == tag["guild_id"]
        ):
            new_tag._is_local = True
        else:
            new_tag._is_local = False
        new_tag.is_global_available = not global_taken
        new_tag.is_local_available = not local_taken
        self.tag = new_tag

        self.embed = Embed()
        self.embed.title = self.tag.name
        self.embed.description = self.tag.value
        self.embed.add_field(name="Status", value=self.tag.__str__())
        self._pages = [self.embed]

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







