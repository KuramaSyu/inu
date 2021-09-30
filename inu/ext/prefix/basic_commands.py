import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio
import logging

from hikari import ActionRowComponent, Embed, MessageCreateEvent, embeds
from hikari.messages import ButtonStyle
from hikari.impl.special_endpoints import ActionRowBuilder
from hikari.events import InteractionCreateEvent
import lightbulb
from lightbulb.context import Context
import hikari

from core import Inu
from utils.tree import tree
from utils import Paginator
from utils.db import Database
from utils.tag_mamager import TagManager
from utils.paginators.tag import TagHandler


# from utils.logging import LoggingHandler
# logging.setLoggerClass(LoggingHandler)

log = logging.getLogger(__name__)

class Basics(lightbulb.Plugin):
    def __init__(self, bot: Inu) -> None:
        self.bot = bot
        super().__init__()#name="Basic Commands"

    @lightbulb.listener(hikari.StartedEvent)
    async def start(self, event: hikari.StartedEvent):
        await self.bot.db.connect()
        TagManager.set_db(self.bot.db)

    @lightbulb.group()
    async def ping(self, ctx: Context) -> None:
        embed = hikari.Embed()
        embed.title = "Ping"
        embed.description = "hikari built inu is alive"
        # buttons = (
        #     ActionRowBuilder()
        #     .add_select_menu("menu")
        #     .add_option("T1", "t1").add_to_menu()
        #     .add_option("T2", "t2").add_to_menu()
        #     .add_to_container()
        # )
        component = (
            ActionRowBuilder()
            .add_button(
                ButtonStyle.PRIMARY,
                "test"
            )
            .set_label("test")
            .add_to_container()
        )

        select_menu = (
            ActionRowBuilder()
            .add_select_menu("s1")
            .add_option("lbl1", "1")
            .add_to_menu()
            .add_to_container()
        )
        components = [component, select_menu]
        await ctx.respond(embed=embed, components=components)
        try:
            event = await self.bot.wait_for(
                InteractionCreateEvent,
                20,
            )
            #print(tree(event, 1))
            await event.interaction.create_initial_response( #type: ignore
                4,
                "Button clicked"
            )
        except asyncio.TimeoutError as e:
            log.debug(e)

    @ping.command()
    async def ping_sub1(self, ctx):
        await ctx.respond("ping subcommand 1")

    @ping.command()
    async def ping_sub2(self, ctx):
        await ctx.respond(ctx.guild.name)

    @lightbulb.command()
    async def test(self, ctx: Context) -> None:
        log.warning("called test")
        embeds = []
        for x in range(10):
            embeds.append(hikari.Embed(description=x))
        b = Paginator(page_s = embeds)
        await b.start(ctx)

    @lightbulb.command()
    async def test2(self, ctx: Context):
        t = TagHandler()
        await t.start(ctx)


def load(bot: Inu):
    bot.add_plugin(Basics(bot))
