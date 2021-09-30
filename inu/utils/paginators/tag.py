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
from .common import (
    Paginator,
    EventListener,
    EventObserver,
    listener,
)

from utils import crumble
from utils.tag_mamager import TagManager


class TagHandler(Paginator):
    """An interactive handler for tags"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name = None
        self._value = None
        self.embed = Embed()
        self.embed.title = "Creating a tag"
        self.embed.add_field("Name of your tag", "Not set", inline=False)
        self.embed.add_field("Value of your tag", "Not set", inline=False)
        self._pages = [self.embed]

    async def update_page(self, to_update: str):
        if to_update == "name":
            self.embed.edit_field(0, "Name of your tag", f"{self._name or 'Not set'}")
        elif to_update == "value":
            values = crumble(str(self._value))
            self.embed.edit_field(1, "Value of your tag", f"{self._value or 'Not set'}")
        await self._message.edit(embed=self.embed)


    @listener(events.InteractionCreateEvent)
    async def on_interaction(self, event: events.InteractionCreateEvent):
        if not isinstance(event.interaction, ComponentInteraction):
            return
        custom_id = event.interaction.custom_id or None
        if custom_id == "set_name":
            await self.set_name(event.interaction)
        elif custom_id == "set_value" and isinstance(self._value, str):

            await self.set_value(event.interaction)

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
        await self.update_page("name")


    async def set_value(self, interaction: ComponentInteraction):
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
        self._name = message.content
        await self.update_page("value")

    async def edit_value(self):
        pass

    async def edit_title(self):
        pass

    async def exit(self):
        pass


