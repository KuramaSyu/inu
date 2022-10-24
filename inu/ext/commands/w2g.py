import asyncio
import logging
import typing
from datetime import datetime
from typing import *
from numpy import full, isin

import aiohttp
import hikari
import lightbulb
import lightbulb.utils as lightbulb_utils

from fuzzywuzzy import fuzz
from hikari import (
    ActionRowComponent, 
    Embed, 
    MessageCreateEvent, 
    embeds, 
    ResponseType, 
    TextInputStyle
)
from hikari.events import InteractionCreateEvent
from hikari.impl.special_endpoints import ActionRowBuilder, LinkButtonBuilder
from hikari.messages import ButtonStyle
from jikanpy import AioJikan
from lightbulb import OptionModifier as OM
from lightbulb import commands, context
from lightbulb.context import Context
from matplotlib.style import available
from typing_extensions import Self


from utils import (
    Colors, 
    Human, 
    Paginator, 
    Reddit, 
    Urban, 
    crumble,
    Watch2Gether
)
from core import (
    BotResponseError, 
    Inu, 
    Table, 
    getLogger
)

log = getLogger(__name__)
plugin = lightbulb.Plugin("API Stuff", "API commands")
bot: Inu

@plugin.command
@lightbulb.option(name="link", description="A optional YouTube video to add", default=None)
@lightbulb.command("watch2gether", "Create a W2G room")
@lightbulb.implements(commands.SlashCommand)
async def make_w2g_link(ctx: context.Context):
    resp = await Watch2Gether.fetch_link(ctx.options.link)
    await ctx.respond(
        component=(
            ActionRowBuilder()
            .add_button(ButtonStyle.LINK, f"{bot.conf.w2g.API_URL}/rooms/{resp['streamkey']}")
            .set_label("Watch2Gether Room") 
            .add_to_container()
        )
    )




def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)

