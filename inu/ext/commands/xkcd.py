import asyncio
from typing import *
from datetime import datetime
import hikari
import lightbulb

from fuzzywuzzy import fuzz
from hikari import (
    Embed,
    ResponseType, 
    TextInputStyle,
)
from hikari.impl import MessageActionRowBuilder
from lightbulb import commands, context


from utils import (
    Colors, 
    Human, 
    Paginator, 
    crumble,
    xkcdAPI
)
from core import (
    BotResponseError, 
    Inu, 
    Table, 
    getLogger,
    InuContext,
    get_context
)

log = getLogger(__name__)

plugin = lightbulb.Plugin("Name", "Description")
bot: Inu

@plugin.listener(hikari.InteractionCreateEvent)
async def on_interaction(event: hikari.InteractionCreateEvent):
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return

    # check if ckcd event
    strip_id = ""
    if event.interaction.custom_id.startswith("xkcd_"):
        strip_id = event.interaction.custom_id.replace("xkcd_", "")
    
    if not strip_id:
        return
    ctx = get_context(event)
    await ctx.defer(update=True)
    if strip_id == "random":
        comic = await xkcdAPI.fetch_comic(
            comic_url=xkcdAPI.random_comic_endpoint()
        )
        await send_comic(ctx, comic)
        return


@plugin.command
@lightbulb.command("xkcd", "Commands to access the xkcd comics")
@lightbulb.implements(commands.SlashCommandGroup)
async def xkcd_group(ctx: context.Context):
    ...

@xkcd_group.child
@lightbulb.command("random", "Get a random xkcd comic")
@lightbulb.implements(commands.SlashSubCommand)
async def xkcd_current(ctx: context.Context):
    ctx = get_context(ctx.event)
    comic = await xkcdAPI.fetch_comic(
        comic_url=xkcdAPI.random_comic_endpoint()
    )
    await send_comic(ctx, comic)

async def send_comic(ctx: InuContext, comic: dict):
    embed = Embed(
        title=(
            f"{comic['title']}"
        ),
        description=(
            f"{comic['alt']}"
        ),
        color=Colors.random_color()
    )
    embed.add_field("Link", f"[Click Here]({comic['link']})", inline=True)
    embed.add_field("Explanation", f"[Click Here]({comic['explanation_url']})", inline=True)
    embed.add_field("Date", f"{comic['year']}-{comic['month']}-{comic['day']}", inline=True)
    embed.set_image(comic["img"])
    embed.set_footer(text=f"XKCD #{comic['num']}")
    await ctx.respond(
        embed=embed,
        components=[
            MessageActionRowBuilder()
            .add_interactive_button(
                hikari.ButtonStyle.SECONDARY, 
                "xkcd_random",
                emoji="🎲"
            )
        ]
    )




def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)

