from typing import Union, Optional, List, Dict
import traceback
import logging


import hikari
from hikari.impl import MessageActionRowBuilder
import lightbulb
from lightbulb import context

from .base import PaginatorReadyEvent
from .base import Paginator
from .base import listener

from utils import Colors
from core import get_context, InuContext, BotResponseError

log = logging.getLogger(__name__)
log.setLevel(logging.WARNING)

class MusicHistoryPaginator(Paginator):
    def __init__(
        self,
        *,
        history: List[Dict[str, str]],
        pages: Union[List[hikari.Embed], List[str]],
        items_per_site: int,
        timeout: int = 60,
    ):
        super().__init__(
            page_s=pages,
            timeout=timeout,
            listen_to_events=[hikari.InteractionCreateEvent],
            disable_component=True,
            disable_components=False,
            disable_paginator_when_one_site=False
        )
        self.not_valid = 0
        self.song_list = history
        self.items_per_site = items_per_site
        self.play_command = None
    
    def build_default_components(self, position: int):
        # components = [self.build_default_component(position)]
        components = super().build_default_components(position)
        # add selection menu
        start = self._position * self.items_per_site
        menu = (
            MessageActionRowBuilder()
            .add_text_menu("history menu")
        )
        for x in range(self.items_per_site):
            try:
                menu.add_option(
                    f"{x+start} | {self.song_list[x+start]['title']}"[:100],
                    str(int(x+start))
                )
            except IndexError:
                break
        menu = menu.parent
        components.append(menu)
        return components
    
    async def start(self, ctx: InuContext, play_command):
        self.play = play_command
        self.set_context(ctx)
        await super().start(ctx)

        
    @listener(hikari.ComponentInteractionCreateEvent)
    async def on_component_interaction(self, event: hikari.InteractionCreateEvent):
        if not isinstance(event.interaction, hikari.ComponentInteraction):
            return
        if not event.interaction.custom_id == "history menu":
            return
        if not event.interaction.message.id == self._message.id:
            return
        ctx = get_context(event)
        # play the selected song
        uri = self.song_list[int(event.interaction.values[0])]["url"]
        # await self.ctx.defer()
        try:
            await self.play(ctx, uri)
        except BotResponseError as e:
            # needs to be catched manually
            if (flag := e.kwargs.get("flags")) == hikari.MessageFlag.EPHEMERAL:
                e.kwargs["ephemeral"] = True
                del e.kwargs["flags"]
            await ctx.respond(**e.kwargs)
    
    @listener(hikari.GuildMessageCreateEvent)
    async def on_message(self, event: hikari.MessageCreateEvent):
        message = event.message
        if not message.content:
            return
        if self.not_valid > 2:
            self.timeout = 10
        valid = [str(num) for num in range(10)]
        valid.extend([" ", ","])
        for char in set(message.content):
            if char not in valid:
                self.not_valid += 1
                return
        numbers = []
        number = ""
        for char in message.content:
            if char.isdigit():
                number += char
            elif char in [" ", ","] and number:
                numbers.append(int(number))
                number = ""
        else:
            if number:
                numbers.append(int(number))

            
        if numbers == []:
            return

        links = []
        embed = hikari.Embed()
        embed.title = "Add Songs:"
        embed.description = ""
        embed.color = Colors.from_name('royalblue')
        embed.set_thumbnail(self.ctx.author.avatar_url)
        embed.set_footer(
            text=f"{len(numbers)} {'track is' if len(numbers) <= 1 else 'tracks are'} "\
                 f"added by {self.ctx.member.display_name}"
        )

        for num in numbers:
            d = self.song_list[num]
            embed.description += f"{num} | [{d['title']}]({d['uri']})\n"
            links.append(d["uri"])
        embed.set_author(name="Enter number(s) OR select in the menu")
        await self.ctx.respond(embed=embed)
        for link in links:
            await self.play(self.ctx, query=link, be_quiet=True)


        

    