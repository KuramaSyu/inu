from argparse import Action
from types import TracebackType
import discord
from typing import Union, Optional, List, Dict
import traceback

import hikari
from hikari.impl import ActionRowBuilder
import lightbulb

from .common import PaginatorReadyEvent
from .common import Paginator
from .common import listener
from utils import Color

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
        )
        self.not_valid = 0
        self.song_list = history
        self.items_per_site = items_per_site
    
    def build_default_components(self, position: int):
        components = [self.build_default_component(position)]
        start = self._position * self.items_per_site
        menu = (
            ActionRowBuilder()
            .add_select_menu("history menu")
        )
        for x in range(self.items_per_site):
            menu.add_option(
                f"{x+start} | {self.song_list[x+start]['title']}",
                str(int(x+start))
            ).add_to_menu()
        menu = menu.add_to_container()
        components.append(menu)
        return components

    @listener(PaginatorReadyEvent)
    async def on_start(self):
        print("on_start")
        try:
            ext = self.bot.get_plugin("Music")
            self.play = ext._play
            self.not_valid = 0
        except:
            traceback.print_exc()
        
    @listener(hikari.GuildMessageCreateEvent)
    async def on_message(self, event: hikari.MessageCreateEvent):
        message = event.message
        if not message.content:
            return
        if self.not_valid > 2:
            self.timeout = 10
        print(message.content)
        valid = [str(num) for num in range(10)]
        valid.extend([" ", ","])
        for char in set(message.content):
            if char not in valid:
                self.not_valid += 1
                print("unvalid char ", char)
                return
        numbers = []
        number = ""
        for char in message.content:
            if char.isdigit():
                number += char
            elif char in [" ", ","] and number:
                numbers.append(int(number))
                number = ""
            print(numbers, "X", number)
        else:
            if number:
                numbers.append(int(number))

            
        if numbers == []:
            return

        links = []
        embed = hikari.Embed()
        embed.title = "Add Songs:"
        embed.description = ""
        embed.color = Color.from_name('royalblue')
        embed.set_thumbnail(self.ctx.author.avatar_url)
        embed.set_footer(
            text=f"{len(numbers)} {'track is' if len(numbers) <= 1 else 'tracks are'} "\
                 f"added by {self.ctx.member.display_name}"
        )
        menu = (
            ActionRowBuilder()
            .add_select_menu("music menu")
        )
        for num in numbers:
            d = self.song_list[num]
            embed.description += f"{num} | [{d['title']}]({d['uri']})\n"
            menu = menu.add_option(f"{num} | {d['title']}", str(num)).add_to_menu()
            links.append(d["uri"])
        embed.set_author(name="Enter number(s) OR select in the menu")
        menu.add_to_container()
        await self.ctx.respond(embed=embed, component=menu)
        await self.play(self.ctx, query=links)


        

    