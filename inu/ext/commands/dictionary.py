import typing
from typing import (
    Union,
    Optional,
    List,
    overload,
)
import asyncio
import logging

from hikari import ActionRowComponent, Embed, MessageCreateEvent, embeds
from hikari.messages import ButtonStyle
from hikari.impl.special_endpoints import ActionRowBuilder
from hikari.events import InteractionCreateEvent
import lightbulb
import lightbulb.utils as lightbulb_utils
from lightbulb import commands, context
import hikari
from numpy import isin

from core import getLogger, BotResponseError
from utils import Urban, Paginator, Colors
# from utils.logging import LoggingHandler
# logging.setLoggerClass(LoggingHandler)



log = getLogger(__name__)

plugin = lightbulb.Plugin("Dictionary", "Extends the commands with urban commands")

@plugin.command
@lightbulb.option("word", "What do you want to search?")
@lightbulb.command("urban", "Search a word in the urban (city) dictionary", aliases=["urban-dictionary"])
@lightbulb.implements(commands.SlashCommand, commands.PrefixCommand)
async def urban_search(ctx: context.Context):
    try:
        pag = Paginator(
            page_s=[
                Embed(
                    title=f"Urban - {ctx.options.word}",
                    description=(
                        f"**description for [{ctx.options.word}]({d['permalink']}):**\n"
                        f"{d['definition'].replace('[', '').replace(']', '')}\n\n"
                    ),
                    color=Colors.random_color(),
                )
                .add_field(
                    "Example",
                    f"{d['example'].replace('[', '').replace(']', '')}\n\n",
                    inline=False,
                )
                .set_footer(
                    text=f"{d['thumbs_up']}👍 | {d['thumbs_down']}👎",
                )
                .set_thumbnail(
                    "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f0/Urban_Dictionary_logo.svg/512px-Urban_Dictionary_logo.svg.png"
                )
                for d in await Urban.fetch(ctx.options.word)
            ],
            compact=True,
            timeout=120,
        )
        await pag.start(ctx)
    except BotResponseError as e:
        await ctx.respond(e.bot_message)



def load(bot: lightbulb.BotApp):
    bot.add_plugin(plugin)



