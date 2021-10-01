import typing
from typing import (
    Union,
    Optional,
    List,
    Callable,
)
import asyncio

import hikari
from hikari import ComponentInteraction, events, ResponseType, Embed
from hikari.messages import ButtonStyle
from hikari.impl import ActionRowBuilder
import lightbulb
from lightbulb.converters import WrappedArg
from lightbulb.converters import user_converter
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


class NewTagHandler(Paginator):
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

    async def start(self, ctx: lightbulb.Context, tag: dict = None):
        """
        Starts the paginator and initializes the tag
        Args:
            ctx: (lightbulb.Context) the Context
            tag: (dict, default=None) the tag which should be
                initialized. Creates new tag, if tag is None 
        """
        if not tag:
            await self.prepare_new_tag(ctx)
        else:
            await self.load_tag(tag, ctx.guild_id)
            
        await super().start(ctx)
    def options_to_string(self) -> str:
        return (
            f"global or local: {'local' if self._options['is local'] else 'global'}\n"
            f"owner: {self._options['owner']}\n"
            f"tag stored: {Human.bool_(self._options['is stored'])}\n"
            f"tag name local available: {Human.bool_(self._options['is local available'], True)}\n"
            f"tag name global available: {Human.bool_(self._options['is global available'], True)}\n"
        )

    async def update_options(self) -> None:
        local_taken, global_taken = await TagManager.is_taken(self._name, self.ctx.guild_id or 0)
        self._options["owner"] = self.ctx.author.username
        self._options["is local available"] = not local_taken
        self._options["is global available"] = not global_taken

    async def update_page(self, update_value: bool = False):
        """Updates the embed, if the interaction wasn't for pagination"""
        self.embed.title = self._name or "Name your Tag (not set)"

        if update_value:
            pages = []
            for page in crumble(str(self._value), 2048):
                pages.append(Embed(
                    title=self._name or "Name of your tag (not set)",
                    description=page
                ))
            self._pages.extend(pages)

        await self.update_options()

        self.embed.edit_field(0, "Status", self.options_to_string())
        await self._message.edit(
            embed=self.embed, 
            components=self.components
        )


    @listener(events.InteractionCreateEvent)
    async def on_interaction(self, event: events.InteractionCreateEvent):
        if not isinstance(event.interaction, ComponentInteraction):
            return
        custom_id = event.interaction.custom_id or None
        print(custom_id)
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
            await self.finish()


    async def set_name(self, interaction: ComponentInteraction):
        embed = Embed(title="Enter a name for your tag:", description=f"You have {self.timeout}s")
        await interaction.create_initial_response(
            ResponseType.MESSAGE_CREATE, 
            embed=embed
        )
        try:
            message = await self.bot.wait_for(
                events.MessageCreateEvent, 
                self.timeout,
                lambda m: m.author_id == interaction.user.id and m.channel_id == interaction.channel_id
            )
        except asyncio.TimeoutError:
            return
        self._name = message.content
        await self.update_page()


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

        
        if append:
            self._value += event.message.content
        else:
            self._value = event.message.content
        await self.update_page(update_value=True)
        if self.ctx.channel:
            await self.ctx.channel.delete_messages(bot_message, event.message)

    async def extend_value(self, interaction: ComponentInteraction):
        await self.set_value(interaction, append=True)

    async def change_visibility(self, interaction: ComponentInteraction):
        if self._options["is local"]:
            self._options["is local"] = False
            return
        self._options["is local"] = True

    async def finish(self):
        pass

    async def change_owner(self, interaction: ComponentInteraction):
        embed = Embed(title="Enter the value for your tag:").set_footer(text=f"timeout after {self.timeout}s")
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
        user = await user_converter(WrappedArg(event.message.content, self.ctx))
        if not user:
            return await self.ctx.respond(
                "I'm sorry, with your given text I can't found anyone", 
                reply=event.message
            )
        if user and self.ctx.channel:
            await self.ctx.channel.delete_messages(bot_message, event.message)
        self._options.owner
        
        

    def build_default_components(self, position) -> List[ActionRowBuilder]:
        navi = super().build_default_component(position)
        disable_remove_when = lambda self: self._name is None or self._value is None
        tag_specific = (
            ActionRowBuilder()
            .add_button(ButtonStyle.PRIMARY, "set_name")
            .set_label("edit name")
            .add_to_container()
            .add_button(ButtonStyle.PRIMARY, "set_value")
            .set_label("edit value")
            .add_to_container()
            .add_button(ButtonStyle.PRIMARY, "extend_value")
            .set_label("append to value")
            .add_to_container()
            .add_button(ButtonStyle.PRIMARY, "change_visibility")
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
            .add_button(ButtonStyle.PRIMARY, "finish")
            .set_label("Finish")
            .add_to_container()
        )
        if self.pagination:
            return [navi, tag_specific, danger_tags, finish] #type: ignore
        return [tag_specific, finish]

    async def load_tag(self, tag: asyncpg.Record, guild_id: Optional[int] = None):
        self._name = tag["tag_key"]
        self._value = tag["key_value"]
        self._options["is stored"] = True
        self._options["owner"] = tag["creator_id"]
        self._options["is local"] = True if tag["guild_id"] == guild_id and guild_id is not None else False
        local_taken, global_taken = await TagManager.is_taken(key=self._name, guild_id = guild_id or 0)
        self._options["local available"] = not local_taken
        self._options["global available"] = not global_taken

        self.embed = Embed()
        self.embed.title = self._name
        self.embed.description = self._value
        self.embed.add_field(name="Status", value="Unknown - Will be loaded after settig a name")
        self._pages = [self.embed]

    async def prepare_new_tag(self, ctx: lightbulb.Context):
        tag = Tag(ctx.author)
        tag.name = None
        tag.value = None
        ctx = ctx or self.ctx
        self._options = {
            "is local": True if ctx.guild_id else False,
            "owner": None,
            "is local available": False,
            "is global available": False,
            "is stored": False,
        }
        tag.is_local = True if tag.guild_id else False
        self.embed = Embed()
        self.embed.title = "Name of your tag (not set)"
        self.embed.description = self._value
        self.embed.add_field(name="Status", value="Unknown - Will be loaded after settig a name")
        self._pages.append(self.embed)

    async def save(self) -> bool:
        """
        Saves the current tag
        Returns:
            bool: wether successfull or not
        """


class Tag():
    def __init__(self, owner: hikari.User):
        self.owner: hikari.User = owner
        self.name: Optional[str] = None
        self.value: Optional[str] = None
        self.is_local_available: bool
        self.is_global_available: bool
        self.is_local: bool
        self.is_stored: bool

    @property
    def is_local(self) -> bool:
        return self.owner.g