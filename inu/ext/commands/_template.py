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
    crumble
)
from core import (
    BotResponseError, 
    Inu, 
    Table, 
    getLogger
)

log = getLogger(__name__)

plugin = lightbulb.Plugin("Name", "Description")
bot: Inu

@plugin.command
@lightbulb.command("testmodal", "test command for modal interactions")
@lightbulb.implements(commands.SlashCommand)
async def testmodal(ctx: context.Context):
    bot: Inu = ctx.bot
    answers, interaction, _ = await bot.shortcuts.ask_with_modal(
        "Tag", 
        ["Name:", "Value:"], 
        interaction=ctx.interaction,
        input_style_s=[TextInputStyle.SHORT, TextInputStyle.PARAGRAPH],
        placeholder_s=[None, "What you will see, when you do /tag get <name>"],
        is_required_s=[True, None],
        pre_value_s=[None, "Well idc"]

    )
    await interaction.create_initial_response(ResponseType.MESSAGE_CREATE, f"{answers}")




def load(inu: lightbulb.BotApp):
    global bot
    bot = inu
    inu.add_plugin(plugin)

