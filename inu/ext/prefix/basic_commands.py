import typing
from typing import (
    Union,
    Optional,
    List,
)

from hikari import embeds
import lightbulb
from lightbulb.context import Context
import hikari

from core import Inu

class Basics(lightbulb.Plugin):
    def __init__(self, bot: Inu) -> None:
        self.bot = bot
        super().__init__(name="Basic Commands")


    @lightbulb.command()
    async def ping(self, ctx: Context) -> None:
        embed = hikari.Embed()
        embed.title = "Ping"
        embed.description = "hikari built inu is alive"
        await ctx.respond(embed=embed)

    @lightbulb.command()
    async def test(self, ctx: Context) -> None:
        await ctx.respond(self.bot.me)

def load(bot):
    bot.add_plugin(Basics(bot))
