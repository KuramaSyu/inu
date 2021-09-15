from hikari import embeds
import lightbulb
from lightbulb.context import Context
import hikari


class Basics(lightbulb.Plugin):
    def __init__(self, bot: lightbulb.Bot) -> None:
        self.bot = bot
        super().__init__(name="Basic Commands")


    @lightbulb.command()
    async def ping(self, ctx: Context) -> None:
        embed = hikari.Embed()
        embed.title = "Ping"
        embed.description = "hikari built inu is alive"
        await ctx.respond(embed=embed)


def load(bot):
    bot.add_plugin(Basics(bot))
