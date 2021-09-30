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

from utils import crumble
from utils.tag_mamager import TagManager
from utils.language import Human


class TagHandler(Paginator):
    """An interactive handler for tags"""
    def __init__(
        self,
        page_s: Union[List[Embed], List[str]],
        timeout: int = 15*60,
        component_factory: Callable[[int], ActionRowBuilder] = None,
        components_factory: Callable[[int], List[ActionRowBuilder]] = None,
        disable_pagination: bool = False,
        disable_component: bool = True,
        disable_components: bool = False,
        disable_paginator_when_one_site: bool = False,
    ):
        super().__init__(
            page_s=page_s,
            timeout=timeout,
            component_factory=component_factory,
            components_factory=components_factory,
            disable_pagination=disable_pagination,
            disable_component=disable_component,
            disable_components=disable_components,
            disable_paginator_when_one_site=disable_paginator_when_one_site,  
        )
        self._name = None
        self._value = None
        self._options = {
            "is local": True,
            "owner": None,
            "is tag name available": None,
        }
        self.embed = Embed()
        self.embed.title = "Name of your tag (not set)"
        self.embed.description = "Value of your tag (not set)"
        self._pages = [self.embed]

    async def update_page(self, update_value: bool = False):
        """to_update: N"""
        self.embed.title = self._name or "Name your Tag (not set)"
        if update_value:
            pages = []
            for page in crumble(str(self._value), 2048):
                pages.append(Embed(
                    title=self._name or "Name of your tag (not set)",
                    description=page
                ))
            self._pages.extend(pages)
        options = (
            f"is local: {Human.bool_(self._options['is local'])}"
        )

        await self._message.edit(
            embed=self.embed, 
            components=self.build_default_components(self._position)
        )


    @listener(events.InteractionCreateEvent)
    async def on_interaction(self, event: events.InteractionCreateEvent):
        if not isinstance(event.interaction, ComponentInteraction):
            return
        custom_id = event.interaction.custom_id or None
        if custom_id == "set_name":
            await self.set_name(event.interaction)
        elif custom_id == "set_value" and isinstance(self._value, str):
            await self.set_value(event.interaction)
        elif custom_id == "extend_value":
            await self.extend_value(event.interaction)
        elif custom_id == "change_visibility":
            await self.change_visibility(event.interaction)
        elif custom_id == "change_owner":
            pass
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
        try:
            message = await self.bot.wait_for(
                events.MessageCreateEvent, 
                self.timeout,
                lambda m: m.author_id == interaction.user.id and m.channel_id == interaction.channel_id
            )
        except asyncio.TimeoutError:
            return
        if not message.content:
            return
        if append and self._name:
            self._name += message.content
        self._name = message.content
        await self.update_page(update_value=True)

    async def extend_value(self, interaction: ComponentInteraction):
        await self.set_value(interaction, True)

    async def change_visibility(self, interaction: ComponentInteraction):
        if self._options["is local"]:
            self._options["is local"] = False
            return
        self._options["is local"] = True

    async def finish(self):
        pass

    def build_default_components(self, position) -> List[ActionRowBuilder]:
        navi = super().build_default_component(position)
        tag_specific = (
            ActionRowBuilder()
            .add_button(ButtonStyle.PRIMARY, "edit_name")
            .set_label("edit name")
            .add_to_container()
            .add_button(ButtonStyle.PRIMARY, "set value")
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



