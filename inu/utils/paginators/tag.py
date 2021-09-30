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


class TagAddHandler(Paginator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._name = None
        self._value = None
        self.embed = Embed()
        self.embed.title = "Creating a tag"
        self.embed.add_field("Name of your tag", "Not set", inline=False)
        self.embed.add_field("Value of your tag", "Not set", inline=False)
        self._pages = [embed]

    def update_page(self):


    @listener(events.InteractionCreateEvent)
    async def on_interaction(self, event: events.InteractionCreateEvent):
        if not isinstance(event.interaction, ComponentInteraction):
            return
        custom_id = event.interaction.custom_id or None
        if custom_id == "set_name":
            await self.set_name(event.interaction)
        elif custom_id == "set_value":
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


    async def set_value(self, interaction: ComponentInteraction):
        pass


