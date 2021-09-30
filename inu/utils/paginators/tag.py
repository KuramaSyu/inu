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
    """An interactive handler for tags"""
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

        self._name = None
        self._value = "Value of your tag (not set)"
        self._options = {
            "is local": True,
            "owner": None,
            "is tag name available": None,
        }
        self.embed = Embed()
        self.embed.title = "Name of your tag (not set)"
        self.embed.description = self._value
        self.embed.add_field(name="Status", value="Unknown - Will be loaded after settig a name")
        self._pages = [self.embed]
    
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


    async def update_page(self, update_value: bool = False):
        """Updates the embed, if the interaction wasn't for interaction"""
        self.embed.title = self._name or "Name your Tag (not set)"
        if update_value:
            pages = []
            for page in crumble(str(self._value), 2048):
                pages.append(Embed(
                    title=self._name or "Name of your tag (not set)",
                    description=page
                ))
            self._pages.extend(pages)
        local_taken, global_taken = await TagManager.is_taken(self._name, self.ctx.guild_id or 0)
        options = (
            f"global or local: {'local' if self._options['is local'] else 'global'}\n"
            f"owner: {self.ctx.author.username}\n"
            f"tag name local available: {Human.bool_(local_taken, True)}\n"
            f"tag name global available: {Human.bool_(global_taken, True)}"
        )
        self.embed.edit_field(0, "Status", options)
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

        
        if append and self._value:
            self._value += event.message.content
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

    def build_default_components(self, position) -> List[ActionRowBuilder]:
        navi = super().build_default_component(position)
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
            return [navi, tag_specific, finish] #type: ignore
        return [tag_specific, finish]





