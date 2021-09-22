import typing
from typing import (
    Union,
    Optional,
    List,
)
import asyncio

from hikari import ActionRowComponent, embeds
from hikari.messages import ButtonStyle
from hikari.impl.special_endpoints import ActionRowBuilder
from hikari.events import InteractionCreateEvent
import lightbulb
from lightbulb.context import Context
import hikari

from core import Inu
from utils import build_logger
from utils.tree import tree

log = build_logger(__name__)

class Basics(lightbulb.Plugin):
    def __init__(self, bot: Inu) -> None:
        self.bot = bot
        super().__init__(name="Basic Commands")


    @lightbulb.command()
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
            print(tree(event, 1))
            await event.interaction.create_initial_response( #type: ignore
                4,
                "Button clicked"
            )
        except asyncio.TimeoutError as e:
            log.debug(e)



    @lightbulb.command()
    async def test(self, ctx: Context) -> None:
        await ctx.respond(self.bot.me)

def load(bot):
    bot.add_plugin(Basics(bot))
